from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, TypeVar

from pydantic import BaseModel

from app.schemas.explanations import (
    CandidateExplanationOutput,
    EvidenceFactKind,
    InternalEvidenceBundleV1,
    ProviderChannelEvidence,
    ProviderCandidateEvidence,
    ProviderCandidateEvidenceRecord,
    ProviderCandidateLocationEvidence,
    ProviderCandidateOverclaimEvidence,
    ProviderCandidateProjectEvidence,
    ProviderCandidateSkillEvidence,
    ProviderCountEvidence,
    ProviderDiagnosticEvidence,
    ProviderEvidenceV1,
    ProviderFeatureEvidence,
    ProviderJobEvidence,
    ProviderJobLocation,
    ProviderRankEvidence,
    ProviderRequirementEvidence,
    ProviderRankingEvidence,
    ProviderRelationEvidence,
    ProviderRequirementIdsEvidence,
    ProviderRetrievalEvidence,
    ProviderRequiredScoreEvidence,
    ProviderRiskLevelEvidence,
    ProviderScoreEvidence,
    ProviderTop1Comparison,
)
from app.services.match_runs.contracts import canonical_fingerprint


EVIDENCE_BUNDLE_VERSION = "evidence_bundle_v1"
PROVIDER_EVIDENCE_VERSION = "provider_evidence_v1"
EXPLANATION_OUTPUT_VERSION = "explanation_output_v1"

_T = TypeVar("_T", bound=BaseModel)


def _artifact_path(filename: str) -> Path:
    source = Path(__file__).resolve()
    candidates = (
        source.parents[4] / "data" / "contracts" / filename,
        source.parents[3] / "data" / "contracts" / filename,
    )
    return next((path for path in candidates if path.is_file()), candidates[0])


def _load_artifact(filename: str, expected_version: str) -> dict:
    try:
        artifact = json.loads(_artifact_path(filename).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Phase 9 contract {filename} is unavailable") from error
    if not isinstance(artifact, dict):
        raise RuntimeError(f"Phase 9 contract {filename} must be an object")
    if artifact.get("x-contract-version") != expected_version:
        raise RuntimeError(f"Phase 9 contract {filename} version mismatch")
    if artifact.get("additionalProperties") is not False:
        raise RuntimeError(f"Phase 9 contract {filename} must reject extra properties")
    return artifact


EVIDENCE_BUNDLE_CONTRACT = _load_artifact(
    "evidence_bundle_v1.json", EVIDENCE_BUNDLE_VERSION
)
PROVIDER_EVIDENCE_CONTRACT = _load_artifact(
    "provider_evidence_v1.json", PROVIDER_EVIDENCE_VERSION
)
EXPLANATION_OUTPUT_CONTRACT = _load_artifact(
    "explanation_output_v1.json", EXPLANATION_OUTPUT_VERSION
)


def _payload(value: _T) -> dict:
    return value.model_dump(mode="json", exclude_none=False)


def evidence_bundle_fingerprint(bundle: InternalEvidenceBundleV1) -> str:
    return canonical_fingerprint(_payload(bundle))


def provider_evidence_fingerprint(bundle: ProviderEvidenceV1) -> str:
    return canonical_fingerprint(_payload(bundle))


def project_provider_evidence(
    bundle: InternalEvidenceBundleV1,
) -> ProviderEvidenceV1:
    """Return the one closed, provider-safe projection of historical evidence."""

    provider_candidates = []
    for candidate in bundle.candidates:
        facts = {(fact.kind.value, fact.name): fact for fact in candidate.facts}

        def fact(kind: str, name: str):
            return facts.get((kind, name))

        def rank(kind: str, name: str, *, required: bool = False):
            source = fact(kind, name)
            if source is None:
                if required:
                    raise ValueError(f"required provider evidence {kind}:{name} is absent")
                return None
            return ProviderRankEvidence(evidence_id=source.evidence_id, value=source.value)

        def score(kind: str, name: str, *, required: bool = False, nullable: bool = True):
            source = fact(kind, name)
            if source is None:
                if required:
                    raise ValueError(f"required provider evidence {kind}:{name} is absent")
                return None
            model = ProviderScoreEvidence if nullable else ProviderRequiredScoreEvidence
            return model(evidence_id=source.evidence_id, value=source.value)

        matched_channels = fact("retrieval", "matched_channels")
        diagnostics = {}
        requirement_diagnostics = {
            "matched_must_have_requirement_ids", "weak_matched_must_have_requirement_ids",
            "missing_must_have_requirement_ids", "matched_nice_to_have_requirement_ids",
            "evidence_supported_requirement_ids",
        }
        relation_diagnostics = {"location_relation", "seniority_relation", "overclaim_level"}
        for name in requirement_diagnostics | relation_diagnostics | {"overclaim_reason_count"}:
            source = fact("diagnostic", name)
            if source is None:
                continue
            if name in requirement_diagnostics:
                model = ProviderRequirementIdsEvidence
            elif name in relation_diagnostics:
                model = ProviderRiskLevelEvidence if name == "overclaim_level" else ProviderRelationEvidence
            else:
                model = ProviderCountEvidence
            diagnostics[name] = model(evidence_id=source.evidence_id, value=source.value)

        comparison_sources = {
            name: source for (kind, name), source in facts.items()
            if kind == EvidenceFactKind.COMPARISON.value
        }
        top1_comparison = None
        if comparison_sources:
            owner = next(iter(comparison_sources.values())).comparison_candidate_id
            comparison_values = {}
            rank_names = {"result_rank", "ltr_rank", "cross_encoder_rank"}
            required_score_names = {"ltr_score_raw", "cross_encoder_score_raw"}
            for name, source in comparison_sources.items():
                if name in rank_names:
                    model = ProviderRankEvidence
                elif name in required_score_names:
                    model = ProviderRequiredScoreEvidence
                else:
                    model = ProviderScoreEvidence
                comparison_values[name] = model(
                    evidence_id=source.evidence_id, value=source.value
                )
            top1_comparison = ProviderTop1Comparison(
                top1_candidate_id=owner, top1_rank=1, **comparison_values
            )

        provider_candidates.append(
            ProviderCandidateEvidence(
                candidate_id=candidate.candidate_id,
                result_rank=candidate.result_rank,
                skills=[
                    ProviderCandidateSkillEvidence(
                        evidence_id=item.evidence_id,
                        category=item.category,
                    )
                    for item in candidate.skills
                ],
                projects=[
                    ProviderCandidateProjectEvidence(
                        evidence_id=item.evidence_id,
                        project_id=item.project_id,
                    )
                    for item in candidate.projects
                ],
                project_evidence=[
                    ProviderCandidateEvidenceRecord(
                        evidence_id=item.evidence_id,
                        source_evidence_id=item.source_evidence_id,
                        project_id=item.project_id,
                        verification_status=item.verification_status,
                        evidence_type=item.evidence_type,
                    )
                    for item in candidate.project_evidence
                ],
                preferred_locations=ProviderCandidateLocationEvidence(
                    remote_policy=candidate.preferred_locations.remote_policy,
                    relocation_open=candidate.preferred_locations.relocation_open,
                ),
                seniority=candidate.seniority,
                overclaim_risk=ProviderCandidateOverclaimEvidence(
                    level=candidate.overclaim_risk.level,
                    reason_count=candidate.overclaim_risk.reason_count,
                ),
                retrieval=ProviderRetrievalEvidence(
                    retrieval_rank=rank("retrieval", "retrieval_rank", required=True),
                    matched_channels=ProviderChannelEvidence(
                        evidence_id=matched_channels.evidence_id,
                        value=matched_channels.value,
                    ),
                    dense_rank=rank("retrieval", "dense_rank"),
                    dense_score=score("retrieval", "dense_score", required=True),
                    sparse_rank=rank("retrieval", "sparse_rank"),
                    sparse_score=score("retrieval", "sparse_score", required=True),
                    fusion_score=score("retrieval", "fusion_score", required=True, nullable=False),
                ),
                features=ProviderFeatureEvidence(**{
                    name: score("feature", name, required=True)
                    for name in (
                        "semantic_score", "sparse_score", "skill_fit_score",
                        "project_evidence_score", "role_direction_score", "ai_tool_score",
                        "location_score", "seniority_score", "missing_penalty",
                        "overclaim_penalty",
                    )
                }),
                ranking=ProviderRankingEvidence(
                    result_rank=rank("ranking", "result_rank", required=True),
                    ltr_rank=rank("ranking", "ltr_rank", required=True),
                    ltr_score_raw=score("ranking", "ltr_score_raw", required=True, nullable=False),
                    cross_encoder_rank=rank("ranking", "cross_encoder_rank"),
                    cross_encoder_score_raw=score("ranking", "cross_encoder_score_raw", nullable=False),
                ),
                diagnostics=ProviderDiagnosticEvidence(**diagnostics),
                top1_comparison=top1_comparison,
            )
        )
    return ProviderEvidenceV1(
        contract_version=PROVIDER_EVIDENCE_VERSION,
        job=ProviderJobEvidence(
            requirements=[
                ProviderRequirementEvidence(
                    evidence_id=item.evidence_id,
                    requirement_id=item.requirement_id,
                    priority=item.priority,
                    category=item.category,
                )
                for item in bundle.job.requirements
            ],
            location=ProviderJobLocation(
                remote_policy=bundle.job.location.remote_policy,
                relocation_supported=bundle.job.location.relocation_supported,
            ),
            seniority_requirement=list(bundle.job.seniority_requirement),
            product_stage=bundle.job.product_stage,
        ),
        candidates=provider_candidates,
    )


def candidate_output_fingerprint(output: CandidateExplanationOutput) -> str:
    return canonical_fingerprint(_payload(output))


def explanation_result_fingerprint(
    outputs: Iterable[CandidateExplanationOutput],
) -> str:
    ordered = sorted(outputs, key=lambda item: item.result_rank)
    ranks = [item.result_rank for item in ordered]
    if not ordered or len(ranks) != len(set(ranks)):
        raise ValueError("Candidate outputs must be non-empty with unique ranks")
    return canonical_fingerprint(
        {
            "output_schema_version": EXPLANATION_OUTPUT_VERSION,
            "candidates": [_payload(item) for item in ordered],
        }
    )


def _bundle_evidence_index(bundle: InternalEvidenceBundleV1) -> dict[str, tuple[str, str | None, int | None]]:
    """Index persisted Evidence Bundle references by kind, owner and rank."""
    index: dict[str, tuple[str, str | None, int | None]] = {}
    for requirement in bundle.job.requirements:
        index[requirement.evidence_id] = ("job_requirement", None, None)
    for candidate in bundle.candidates:
        for item, kind in (
            (candidate.skills, "skill"),
            (candidate.projects, "project"),
            (candidate.project_evidence, "project_evidence"),
        ):
            for evidence in item:
                index[evidence.evidence_id] = (kind, candidate.candidate_id, candidate.result_rank)
        for fact in candidate.facts:
            index[fact.evidence_id] = (fact.kind.value, candidate.candidate_id, candidate.result_rank)
    return index


def validate_explanation_output_references(
    output: CandidateExplanationOutput,
    bundle: InternalEvidenceBundleV1,
) -> None:
    """Fail closed unless every output reference is present and owner-compatible."""
    index = _bundle_evidence_index(bundle)
    owner = next((candidate for candidate in bundle.candidates if candidate.result_rank == output.result_rank), None)
    if owner is None or owner.candidate_id != output.candidate_id:
        raise ValueError("Explanation output Candidate owner does not match Evidence Bundle")

    def check(ref: str, allowed: set[str], *, section: str) -> None:
        metadata = index.get(ref)
        if metadata is None:
            raise ValueError(f"Evidence reference {ref} does not exist in Evidence Bundle")
        kind, candidate_id, rank = metadata
        if kind not in allowed:
            raise ValueError(f"Evidence reference {ref} is incompatible with {section}")
        if candidate_id is not None and (candidate_id != output.candidate_id or rank != output.result_rank):
            raise ValueError(f"Evidence reference {ref} owner does not match output Candidate")

    general = {"job_requirement", "skill", "project", "project_evidence", "retrieval", "feature", "ranking", "diagnostic"}
    for ref in output.summary.evidence_refs:
        check(ref, general, section="summary")
    for item in output.match_reasons:
        reason_kinds = {
            "skill_alignment": {"job_requirement", "skill", "project", "project_evidence", "feature", "diagnostic"},
            "project_evidence": {"job_requirement", "skill", "project", "project_evidence", "diagnostic"},
            "role_direction": {"job_requirement", "feature", "diagnostic"},
            "ai_tooling": {"skill", "project", "project_evidence", "feature", "diagnostic"},
            "location": {"job_requirement", "feature", "diagnostic"},
            "seniority": {"job_requirement", "feature", "diagnostic"},
            "ranking_context": {"retrieval", "ranking", "feature"},
        }[item.category.value]
        for ref in item.evidence_refs:
            check(ref, reason_kinds, section="match reason")
    for item in output.risk_points:
        allowed = {
            "missing_requirement": {"job_requirement", "diagnostic"},
            "weak_evidence": {"skill", "project", "project_evidence", "diagnostic"},
            "role_direction_mismatch": {"job_requirement", "feature", "diagnostic"},
            "location_mismatch": {"job_requirement", "feature", "diagnostic"},
            "seniority_mismatch": {"job_requirement", "feature", "diagnostic"},
            "overclaim_signal": {"project_evidence", "diagnostic"},
            "ranking_comparison": {"comparison", "ranking", "feature", "diagnostic"},
        }[item.category.value]
        for ref in item.evidence_refs:
            check(ref, allowed, section="risk point")
    for item in output.missing_skills:
        for ref in item.evidence_refs:
            check(ref, {"job_requirement", "diagnostic", "skill", "project_evidence"}, section="missing skill")
    for item in output.interview_questions:
        for ref in item.evidence_refs:
            check(ref, {"job_requirement", "skill", "project", "project_evidence", "diagnostic"}, section="interview question")
    if output.why_not_top1 is not None:
        for ref in output.why_not_top1.evidence_refs:
            check(ref, {"comparison", "ranking", "feature", "diagnostic"}, section="top-1 comparison")

    if output.profile_rewrite_suggestion is not None:
        for operation in output.profile_rewrite_suggestion.operations:
            primary_names = (
                "skill_evidence_id", "project_evidence_id", "evidence_record_id",
                "claim_evidence_id", "requirement_evidence_id",
            )
            for name in primary_names:
                ref = getattr(operation, name, None)
                if ref is None:
                    continue
                allowed = {"job_requirement"} if name == "requirement_evidence_id" else {"skill", "project", "project_evidence"}
                check(ref, allowed, section="rewrite primary reference")
            for ref in operation.evidence_refs:
                check(ref, {"job_requirement", "skill", "project", "project_evidence", "diagnostic"}, section="rewrite support")


__all__ = [
    "EVIDENCE_BUNDLE_VERSION",
    "EXPLANATION_OUTPUT_VERSION",
    "PROVIDER_EVIDENCE_VERSION",
    "candidate_output_fingerprint",
    "evidence_bundle_fingerprint",
    "explanation_result_fingerprint",
    "provider_evidence_fingerprint",
    "project_provider_evidence",
    "validate_explanation_output_references",
]
