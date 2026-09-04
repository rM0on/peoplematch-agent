from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from app.schemas.explanations import (
    CandidateEvidenceRecord,
    CandidateLocationEvidence,
    CandidateOverclaimEvidence,
    CandidateProjectEvidence,
    CandidateSkillEvidence,
    CrossEncoderRuntimeProvenance,
    EvidenceFact,
    EvidenceFactKind,
    HistoricalCandidateEvidence,
    HistoricalJobEvidence,
    HistoricalJobLocation,
    HistoricalRequirementEvidence,
    InternalEvidenceBundleV1,
    MatchRunEvidenceSource,
    RuntimeProvenance,
)
from app.services.explanation.evidence.diagnostics import build_diagnostic_facts
from app.services.explanation.evidence.historical_integrity import (
    validate_historical_results,
    validate_historical_workflow,
)
from app.services.explanation.evidence.normalization import (
    NORMALIZER_VERSION,
    canonicalize_historical_text_labels,
    canonicalize_labels,
    normalize_label,
)
from app.services.match_runs.contracts import (
    CANDIDATE_INPUT_CONTRACT_VERSION,
    RANKING_INPUT_CONTRACT_VERSION,
    canonical_fingerprint,
)


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
_FEATURE_NAMES = (
    "semantic_score",
    "sparse_score",
    "skill_fit_score",
    "project_evidence_score",
    "role_direction_score",
    "ai_tool_score",
    "location_score",
    "seniority_score",
    "missing_penalty",
    "overclaim_penalty",
)


def _safe_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded historical identifier")
    return value


def _strict_rank(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 50:
        raise ValueError(f"{label} must be a strict positive historical rank")
    return value


def _score(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("historical score must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError("historical score must be finite")
    return converted


def _fact(evidence_id: str, kind: str, candidate_id: str, name: str, value: Any) -> dict:
    return {
        "evidence_id": evidence_id,
        "kind": kind,
        "candidate_id": candidate_id,
        "name": name,
        "value": value,
    }


def _skill_evidence_id(candidate_id: str, rank: int, name: str, category: str) -> str:
    digest = hashlib.sha256(
        f"{NORMALIZER_VERSION}|{candidate_id}|{rank}|{name}|{category}".encode(
            "utf-8"
        )
    ).hexdigest()
    return f"candidate:{rank}:skill:{digest}"


def _validate_ranking_snapshot(run) -> None:
    snapshot = run.ranking_input_snapshot
    if (
        getattr(run, "ranking_input_contract_version", None)
        != RANKING_INPUT_CONTRACT_VERSION
        or snapshot.get("contract_version") != RANKING_INPUT_CONTRACT_VERSION
    ):
        raise ValueError("unsupported ranking input snapshot contract version")
    expected = canonical_fingerprint(
        {
            "job_snapshot": snapshot,
            "ranking_variant": run.ranking_variant,
            "request_parameters": run.request_parameters,
            "workflow_version": run.workflow_version,
            "workflow_fingerprint": run.workflow_fingerprint,
            "provenance": {
                "retrieval_document_version": run.retrieval_document_version,
                "retrieval_configuration_fingerprint": (
                    run.retrieval_configuration_fingerprint
                ),
                "feature_version": run.feature_version,
                "feature_fingerprint": run.feature_fingerprint,
                "ranker_version": run.ranker_version,
                "ranker_model_sha256": run.ranker_model_sha256,
            },
        }
    )
    if expected != run.ranking_input_fingerprint:
        raise ValueError("ranking input snapshot fingerprint does not match persisted history")


def _validate_candidate_snapshot(result) -> None:
    snapshot = result.candidate_input_snapshot
    if not isinstance(snapshot, dict) or not snapshot:
        raise ValueError("MatchResult has no historical Candidate snapshot")
    if (
        getattr(result, "candidate_input_contract_version", None)
        != CANDIDATE_INPUT_CONTRACT_VERSION
        or snapshot.get("contract_version") != CANDIDATE_INPUT_CONTRACT_VERSION
    ):
        raise ValueError("unsupported Candidate snapshot contract version")
    if canonical_fingerprint(snapshot) != result.candidate_input_fingerprint:
        raise ValueError("Candidate snapshot fingerprint does not match persisted history")


def _project_evidence_id(rank: int, project_id: str) -> str:
    return f"candidate:{rank}:project:{_safe_identifier(project_id, 'project_id')}"


def _project_record_evidence_id(rank: int, evidence_id: str) -> str:
    safe = _safe_identifier(evidence_id, "project evidence id")
    return f"candidate:{rank}:project_evidence:{safe}"


def _job_from_snapshot(snapshot: dict[str, Any]) -> HistoricalJobEvidence:
    requirements = []
    for priority, values in (("must_have", snapshot.get("must_have", [])), ("nice_to_have", snapshot.get("nice_to_have", []))):
        for item in values:
            requirement_id = _safe_identifier(item.get("requirement_id"), "requirement_id")
            requirements.append(
                HistoricalRequirementEvidence(
                    evidence_id=f"job_requirement:{requirement_id}",
                    requirement_id=requirement_id,
                    priority=priority,
                    category=item["category"],
                    text=item["text"],
                    evidence_expectation=item["evidence_expectation"],
                )
            )
    requirements.sort(key=lambda item: (0 if item.priority.value == "must_have" else 1, item.requirement_id))
    location = snapshot["location"]
    return HistoricalJobEvidence(
        job_id=_safe_identifier(snapshot["job_id"], "job_id"),
        role_title=snapshot["role_title"],
        role_direction=canonicalize_labels(snapshot.get("role_direction", []), "role_direction"),
        requirements=requirements,
        location=HistoricalJobLocation(
            cities=canonicalize_historical_text_labels(
                location.get("cities", []), "job location cities"
            ),
            remote_policy=location["remote_policy"],
            relocation_supported=location["relocation_supported"],
        ),
        seniority_requirement=sorted(snapshot.get("seniority_requirement", [])),
        product_stage=snapshot["product_stage"],
    )


def _candidate_from_result(
    result, *, historical_requirement_ids: set[str]
) -> HistoricalCandidateEvidence:
    snapshot = result.candidate_input_snapshot
    candidate_id = _safe_identifier(snapshot["candidate_id"], "candidate_id")
    if getattr(result, "candidate_id", candidate_id) != candidate_id:
        raise ValueError("MatchResult candidate identity does not match its historical snapshot")
    rank = _strict_rank(result.result_rank, "result_rank")
    skills_by_id: dict[str, CandidateSkillEvidence] = {}
    for item in snapshot.get("skills", []):
        normalized_name = normalize_label(item["name"], "skill name")
        evidence_id = _skill_evidence_id(
            candidate_id, rank, normalized_name, item["category"]
        )
        skills_by_id[evidence_id] = CandidateSkillEvidence(
            evidence_id=evidence_id,
            name=normalized_name,
            category=item["category"],
        )
    skills = list(skills_by_id.values())
    skill_names = {item.name for item in skills}
    skills.sort(key=lambda item: (item.name.casefold(), item.category.value))
    project_ids: set[str] = set()
    projects = [
        CandidateProjectEvidence(
            evidence_id=_project_evidence_id(rank, item["project_id"]),
            project_id=_safe_identifier(item["project_id"], "project_id"),
            technologies=canonicalize_labels(
                item.get("technologies", []), "project technologies"
            ),
            skills_demonstrated=canonicalize_labels(
                item.get("skills_demonstrated", []), "project demonstrated skills"
            ),
        )
        for item in snapshot.get("projects", [])
    ]
    project_ids = {item.project_id for item in projects}
    if len(project_ids) != len(projects):
        raise ValueError("historical project IDs must be unique within a Candidate")
    projects.sort(key=lambda item: item.project_id)
    project_evidence = [
        CandidateEvidenceRecord(
            evidence_id=_project_record_evidence_id(rank, item["evidence_id"]),
            source_evidence_id=_safe_identifier(item["evidence_id"], "source_evidence_id"),
            project_id=_safe_identifier(item["project_id"], "project_id"),
            supports_skills=canonicalize_labels(
                item.get("supports_skills", []),
                "project evidence supported skills",
            ),
            verification_status=item["verification_status"],
            evidence_type=item["evidence_type"],
        )
        for item in snapshot.get("project_evidence", [])
    ]
    if any(item.project_id not in project_ids for item in project_evidence):
        raise ValueError("project evidence references a project owned by another or unknown Candidate")
    if any(set(item.supports_skills) - skill_names for item in project_evidence):
        raise ValueError("project evidence supports a skill not owned by the Candidate")
    if len({item.evidence_id for item in project_evidence}) != len(project_evidence):
        raise ValueError("historical project evidence IDs must be unique within a Candidate")
    project_evidence.sort(key=lambda item: item.evidence_id)
    facts = [
        _fact(
            f"retrieval:{rank}:retrieval_rank",
            EvidenceFactKind.RETRIEVAL.value,
            candidate_id,
            "retrieval_rank",
            _strict_rank(result.retrieval_rank, "retrieval_rank"),
        ),
        _fact(
            f"retrieval:{rank}:matched_channels",
            EvidenceFactKind.RETRIEVAL.value,
            candidate_id,
            "matched_channels",
            sorted(result.matched_channels),
        ),
    ]
    for name, value in (
        ("dense_rank", result.dense_rank),
        ("sparse_rank", result.sparse_rank),
    ):
        if value is not None:
            facts.append(_fact(f"retrieval:{rank}:{name}", "retrieval", candidate_id, name, _strict_rank(value, name)))
    for name, value in (
        ("dense_score", result.dense_score),
        ("sparse_score", result.sparse_score),
        ("fusion_score", result.fusion_score),
    ):
        facts.append(_fact(f"retrieval:{rank}:{name}", "retrieval", candidate_id, name, _score(value)))
    for name in _FEATURE_NAMES:
        facts.append(
            _fact(
                f"feature:{rank}:{name}",
                "feature",
                candidate_id,
                name,
                _score(getattr(result, name)),
            )
        )
    for name, value in (
        ("result_rank", result.result_rank),
        ("ltr_rank", result.ltr_rank),
    ):
        facts.append(_fact(f"ranking:{rank}:{name}", "ranking", candidate_id, name, _strict_rank(value, name)))
    ltr_score = _score(result.ltr_score_raw)
    if ltr_score is None:
        raise ValueError("ltr_score_raw is required for historical ranking evidence")
    facts.append(_fact(f"ranking:{rank}:ltr_score_raw", "ranking", candidate_id, "ltr_score_raw", ltr_score))
    if result.cross_encoder_rank is not None:
        ce_rank = _strict_rank(result.cross_encoder_rank, "cross_encoder_rank")
        ce_score = _score(result.cross_encoder_score_raw)
        if ce_score is None:
            raise ValueError("cross_encoder_score_raw is required with cross_encoder_rank")
        facts.append(_fact(f"ranking:{rank}:cross_encoder_rank", "ranking", candidate_id, "cross_encoder_rank", ce_rank))
        facts.append(_fact(f"ranking:{rank}:cross_encoder_score_raw", "ranking", candidate_id, "cross_encoder_score_raw", ce_score))
    elif result.cross_encoder_score_raw is not None:
        raise ValueError("cross_encoder_score_raw cannot exist without cross_encoder_rank")
    facts.extend(
        build_diagnostic_facts(
            result,
            historical_requirement_ids=historical_requirement_ids,
        )
    )
    candidate = HistoricalCandidateEvidence(
        candidate_id=candidate_id,
        result_rank=rank,
        target_roles=canonicalize_historical_text_labels(
            snapshot.get("target_roles", []), "target roles"
        ),
        skills=skills,
        projects=projects,
        project_evidence=project_evidence,
        ai_tools=canonicalize_labels(snapshot.get("ai_tools", []), "AI tools"),
        preferred_locations=CandidateLocationEvidence(
            cities=canonicalize_historical_text_labels(
                snapshot["preferred_locations"].get("cities", []),
                "candidate location cities",
            ),
            remote_policy=snapshot["preferred_locations"]["remote_policy"],
            relocation_open=snapshot["preferred_locations"]["relocation_open"],
        ),
        seniority=snapshot["seniority"],
        team_stage_preference=canonicalize_labels(
            snapshot.get("team_stage_preference", []), "team stage preference"
        ),
        overclaim_risk=CandidateOverclaimEvidence(**snapshot["overclaim_risk"]),
        facts=facts,
    )
    return candidate


def _comparison_facts(candidates: list[HistoricalCandidateEvidence], ranking_variant: str) -> None:
    if not candidates:
        return
    top1 = candidates[0]
    top1_facts = {fact.name: fact for fact in top1.facts}
    names = (
        "skill_fit_score",
        "project_evidence_score",
        "role_direction_score",
        "ai_tool_score",
        "location_score",
        "seniority_score",
        "ltr_rank",
        "ltr_score_raw",
    )
    if ranking_variant == "cross_encoder_experiment":
        names += ("cross_encoder_rank", "cross_encoder_score_raw")
    for candidate in candidates[1:]:
        source = {fact.name: fact for fact in candidate.facts}
        for name in names:
            value = source.get(name)
            top_value = top1_facts.get(name)
            if (
                value is None
                or top_value is None
                or value.value is None
                or top_value.value is None
            ):
                continue
            candidate.facts.append(
                EvidenceFact.model_validate({
                    "evidence_id": f"comparison:{candidate.result_rank}:top1:{name}",
                    "kind": EvidenceFactKind.COMPARISON.value,
                    "candidate_id": candidate.candidate_id,
                    "name": name,
                    "value": value.value,
                    "comparison_candidate_id": top1.candidate_id,
                })
            )


class EvidenceBundleBuilder:
    def build(self, run) -> InternalEvidenceBundleV1:
        if getattr(run, "status", None) != "COMPLETED":
            raise ValueError("Evidence Bundle requires a completed MatchRun")
        if not isinstance(run.ranking_input_snapshot, dict) or not run.ranking_input_snapshot:
            raise ValueError("completed MatchRun has no historical Job snapshot")
        _validate_ranking_snapshot(run)
        requested_job_id = getattr(run, "requested_job_id", None)
        resolved_job_id = getattr(run, "job_id", None)
        snapshot_job_id = run.ranking_input_snapshot.get("job_id")
        if (
            not isinstance(requested_job_id, str)
            or not isinstance(resolved_job_id, str)
            or requested_job_id != resolved_job_id
            or resolved_job_id != snapshot_job_id
        ):
            raise ValueError(
                "Job identity lineage mismatch: requested, resolved, and historical "
                "Job identities must match"
            )
        steps = validate_historical_workflow(run, getattr(run, "steps", ()))
        results = sorted(list(run.results), key=lambda item: item.result_rank)
        if run.result_count != len(results) or not results:
            raise ValueError("completed MatchRun result count is inconsistent")
        validate_historical_results(run, results)
        for result in results:
            persisted_run_id = getattr(result, "run_id", run.run_id)
            if persisted_run_id != run.run_id:
                raise ValueError("MatchResult belongs to another MatchRun")
            _validate_candidate_snapshot(result)
        job = _job_from_snapshot(run.ranking_input_snapshot)
        historical_requirement_ids = {
            requirement.requirement_id for requirement in job.requirements
        }
        candidates = [
            _candidate_from_result(
                result,
                historical_requirement_ids=historical_requirement_ids,
            )
            for result in results
        ]
        _comparison_facts(candidates, run.ranking_variant)
        for candidate in candidates:
            candidate.facts.sort(key=lambda fact: fact.evidence_id)
        provenance = RuntimeProvenance(
            retrieval_document_version=run.retrieval_document_version,
            retrieval_configuration_fingerprint=run.retrieval_configuration_fingerprint,
            feature_version=run.feature_version,
            feature_fingerprint=run.feature_fingerprint,
            ranker_version=run.ranker_version,
            ranker_model_sha256=run.ranker_model_sha256,
            cross_encoder=(
                CrossEncoderRuntimeProvenance(**run.ce_provenance)
                if run.ce_provenance is not None
                else None
            ),
        )
        workflow_trace = [
            {
                "sequence": step.sequence,
                "step_name": step.step_name,
                "status": "COMPLETED",
            }
            for step in steps
        ]
        source = MatchRunEvidenceSource(
            match_run_id=run.run_id,
            ranking_variant=run.ranking_variant,
            workflow_version=run.workflow_version,
            workflow_fingerprint=run.workflow_fingerprint,
            ranking_input_fingerprint=run.ranking_input_fingerprint,
            result_fingerprint=run.result_fingerprint,
        )
        return InternalEvidenceBundleV1(
            contract_version="evidence_bundle_v1",
            source=source,
            job=job,
            runtime_provenance=provenance,
            workflow_trace=workflow_trace,
            candidates=candidates,
        )


def build_evidence_bundle(run) -> InternalEvidenceBundleV1:
    return EvidenceBundleBuilder().build(run)


__all__ = ["EvidenceBundleBuilder", "build_evidence_bundle"]
