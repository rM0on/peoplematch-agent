from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.schemas.explanations import InternalEvidenceBundleV1, ProviderEvidenceV1
from app.services.explanation.evidence.contracts import EvidenceFactsV1
from app.services.explanation.evidence.validation import validate_evidence_facts, validate_fact_references
from app.services.explanation.contracts import project_provider_evidence
from app.services.explanation.generation.contracts import (
    ExplanationPlanV1,
    ProviderPromptCandidate,
    ProviderPromptComparison,
    ProviderPromptEvidenceV1,
    ProviderPromptFacts,
    ProviderPromptJob,
    ProviderPromptMatchReason,
    ProviderPromptMissingRequirement,
    ProviderPromptRankingContext,
    ProviderPromptRequirement,
    ProviderPromptRisk,
    ResolvedExplanationPlanCandidate,
    ResolvedExplanationPlanV1,
    ResolvedInterviewQuestionOperation,
    ResolvedMatchReason,
    ResolvedRiskPoint,
    ResolvedRewriteOperation,
    ResolvedSummary,
    ResolvedWhyNotTop1,
)


@dataclass(frozen=True)
class ProviderReferenceMap:
    """Ephemeral mapping; it is deliberately never a persistence contract."""

    internal_to_provider: Mapping[str, str]
    provider_to_internal: Mapping[str, str]
    candidate_to_provider: Mapping[str, str]
    provider_to_candidate: Mapping[str, str]


@dataclass(frozen=True)
class ProjectedProviderEvidence:
    payload: ProviderPromptEvidenceV1
    reference_map: ProviderReferenceMap


def _provider_ref(mapping: dict[str, str], evidence_id: str) -> str:
    try:
        return mapping[evidence_id]
    except KeyError as error:
        raise ValueError("provider prompt refers to evidence outside the historical bundle") from error


_RETRIEVAL_FIELDS = (
    "retrieval_rank",
    "matched_channels",
    "dense_rank",
    "dense_score",
    "sparse_rank",
    "sparse_score",
    "fusion_score",
)
_FEATURE_FIELDS = (
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
_RANKING_FIELDS = (
    "result_rank",
    "ltr_rank",
    "ltr_score_raw",
    "cross_encoder_rank",
    "cross_encoder_score_raw",
)
_DIAGNOSTIC_FIELDS = (
    "matched_must_have_requirement_ids",
    "weak_matched_must_have_requirement_ids",
    "missing_must_have_requirement_ids",
    "matched_nice_to_have_requirement_ids",
    "evidence_supported_requirement_ids",
    "location_relation",
    "seniority_relation",
    "overclaim_level",
    "overclaim_reason_count",
)
_COMPARISON_FIELDS = (
    "result_rank",
    "ltr_rank",
    "ltr_score_raw",
    "cross_encoder_rank",
    "cross_encoder_score_raw",
    "skill_fit_score",
    "project_evidence_score",
    "role_direction_score",
    "ai_tool_score",
    "location_score",
    "seniority_score",
    "missing_penalty",
    "overclaim_penalty",
)


def _aggregate_evidence_ids(group: object, field_names: tuple[str, ...]) -> set[str]:
    identifiers: set[str] = set()
    for field_name in field_names:
        item = getattr(group, field_name)
        if item is not None:
            identifiers.add(item.evidence_id)
    return identifiers


def _provider_safe_evidence_ids(provider_evidence: ProviderEvidenceV1) -> set[str]:
    """Enumerate only actual Evidence ID fields in the closed provider contract."""

    identifiers = {
        requirement.evidence_id for requirement in provider_evidence.job.requirements
    }
    for candidate in provider_evidence.candidates:
        identifiers.update(item.evidence_id for item in candidate.skills)
        identifiers.update(item.evidence_id for item in candidate.projects)
        identifiers.update(item.evidence_id for item in candidate.project_evidence)
        identifiers.update(
            _aggregate_evidence_ids(candidate.retrieval, _RETRIEVAL_FIELDS)
        )
        identifiers.update(_aggregate_evidence_ids(candidate.features, _FEATURE_FIELDS))
        identifiers.update(_aggregate_evidence_ids(candidate.ranking, _RANKING_FIELDS))
        identifiers.update(
            _aggregate_evidence_ids(candidate.diagnostics, _DIAGNOSTIC_FIELDS)
        )
        if candidate.top1_comparison is not None:
            identifiers.update(
                _aggregate_evidence_ids(
                    candidate.top1_comparison,
                    _COMPARISON_FIELDS,
                )
            )
    return identifiers


def _prompt_internal_evidence_ids(
    provider_evidence: ProviderEvidenceV1,
    evidence_facts: EvidenceFactsV1,
) -> set[str]:
    """Collect the exact internal references that the prompt will expose."""

    identifiers = {
        requirement.evidence_id for requirement in provider_evidence.job.requirements
    }
    for candidate in evidence_facts.candidates:
        for item in (
            *candidate.match_reasons,
            *candidate.ranking_context,
            *candidate.risks,
            *candidate.missing_requirements,
        ):
            identifiers.update(item.evidence_refs)
        if candidate.comparison is not None:
            identifiers.update(_comparison_internal_refs(candidate))
    safe_identifiers = _provider_safe_evidence_ids(provider_evidence)
    if not identifiers <= safe_identifiers:
        raise ValueError("provider prompt facts contain evidence outside the safe projection")
    return identifiers


def _prompt_provider_references(payload: ProviderPromptEvidenceV1) -> set[str]:
    """Enumerate every opaque evidence reference serialized to the provider."""

    references = {
        requirement.requirement_ref for requirement in payload.job.requirements
    }
    for candidate in payload.candidates:
        facts = candidate.facts
        for item in (
            *facts.match_reasons,
            *facts.ranking_context,
            *facts.risks,
            *facts.missing_requirements,
        ):
            references.update(item.evidence_refs)
        references.update(
            item.requirement_ref for item in facts.missing_requirements
        )
        if facts.comparison is not None:
            references.update(facts.comparison.evidence_refs)
    return references


class ProviderReferenceProjector:
    """Project deterministic fact selections with opaque, in-memory references."""

    def project(
        self,
        *,
        bundle: InternalEvidenceBundleV1,
        evidence_facts: EvidenceFactsV1,
    ) -> ProjectedProviderEvidence:
        """Build a prompt projection from the validated historical source only.

        The provider projection is reconstructed here rather than accepted from
        a caller, so an upstream object cannot replace the frozen allowlist.
        """

        validate_evidence_facts(bundle, evidence_facts)
        provider_evidence = project_provider_evidence(bundle)
        provider_candidates = list(provider_evidence.candidates)
        fact_candidates = list(evidence_facts.candidates)
        provider_identity = [
            (candidate.candidate_id, candidate.result_rank)
            for candidate in provider_candidates
        ]
        fact_identity = [
            (candidate.candidate_id, candidate.result_rank)
            for candidate in fact_candidates
        ]
        if provider_identity != fact_identity:
            raise ValueError("provider evidence and evidence facts Candidate coverage differs")

        # Allocate opaque references only for values serialized into the prompt.
        # The broader provider-safe persistence projection is not a selectable
        # reference universe.
        evidence_ids = _prompt_internal_evidence_ids(
            provider_evidence,
            evidence_facts,
        )
        internal_to_provider = {
            evidence_id: f"ref_{index:04d}"
            for index, evidence_id in enumerate(sorted(evidence_ids), start=1)
        }
        candidate_to_provider = {
            candidate.candidate_id: f"candidate_{candidate.result_rank:04d}"
            for candidate in provider_candidates
        }
        reference_map = _immutable_reference_map(
            internal_to_provider=internal_to_provider,
            candidate_to_provider=candidate_to_provider,
        )

        prompt_candidates = []
        for candidate in fact_candidates:
            comparison = candidate.comparison
            prompt_candidates.append(
                ProviderPromptCandidate(
                    candidate_ref=candidate_to_provider[candidate.candidate_id],
                    result_rank=candidate.result_rank,
                    facts=ProviderPromptFacts(
                        match_reasons=[
                            ProviderPromptMatchReason(
                                category=reason.category,
                                statement_key=reason.statement_key,
                                evidence_refs=_canonical_refs([
                                    _provider_ref(internal_to_provider, ref)
                                    for ref in reason.evidence_refs
                                ]),
                            )
                            for reason in candidate.match_reasons
                        ],
                        ranking_context=[
                            ProviderPromptRankingContext(
                                dimension=context.dimension,
                                evidence_refs=_canonical_refs([
                                    _provider_ref(internal_to_provider, ref)
                                    for ref in context.evidence_refs
                                ]),
                            )
                            for context in candidate.ranking_context
                        ],
                        risks=[
                            ProviderPromptRisk(
                                category=risk.category,
                                statement_key=risk.statement_key,
                                evidence_refs=_canonical_refs([
                                    _provider_ref(internal_to_provider, ref)
                                    for ref in risk.evidence_refs
                                ]),
                            )
                            for risk in candidate.risks
                        ],
                        missing_requirements=[
                            ProviderPromptMissingRequirement(
                                requirement_ref=_provider_ref(
                                    internal_to_provider,
                                    next(
                                        ref
                                        for ref in requirement.evidence_refs
                                        if ref.startswith("job_requirement:")
                                    ),
                                ),
                                priority=requirement.priority,
                                status=requirement.status,
                                evidence_status=requirement.evidence_status,
                                evidence_refs=_canonical_refs([
                                    _provider_ref(internal_to_provider, ref)
                                    for ref in requirement.evidence_refs
                                ]),
                            )
                            for requirement in candidate.missing_requirements
                        ],
                        comparison=(
                            None
                            if comparison is None
                            else ProviderPromptComparison(
                                top1_candidate_ref=candidate_to_provider[
                                    comparison.top1_candidate_id
                                ],
                                dimensions=[item.dimension for item in comparison.comparisons],
                                evidence_refs=_canonical_refs([
                                    _provider_ref(internal_to_provider, ref)
                                    for ref in _comparison_internal_refs(candidate)
                                ]),
                            )
                        ),
                    ),
                )
            )

        payload = ProviderPromptEvidenceV1(
                contract_version="provider_prompt_evidence_v1",
                job=ProviderPromptJob(
                    requirements=[
                        ProviderPromptRequirement(
                            requirement_ref=_provider_ref(
                                internal_to_provider, requirement.evidence_id
                            ),
                            priority=requirement.priority,
                            category=requirement.category,
                        )
                        for requirement in provider_evidence.job.requirements
                    ]
                ),
                candidates=prompt_candidates,
            )
        if set(reference_map.provider_to_internal) != _prompt_provider_references(payload):
            raise ValueError("provider reference map exceeds the serialized prompt")
        return ProjectedProviderEvidence(
            payload=payload,
            reference_map=reference_map,
        )


def _resolve_refs(reference_map: ProviderReferenceMap, refs: list[str]) -> list[str]:
    resolved = []
    for ref in refs:
        try:
            resolved.append(reference_map.provider_to_internal[ref])
        except KeyError as error:
            raise ValueError(f"unknown provider reference: {ref}") from error
    return resolved


def _canonical_refs(refs: list[str]) -> list[str]:
    """Preserve one canonical selection representation at every boundary."""

    return sorted(set(refs))


def _comparison_internal_refs(candidate) -> list[str]:
    if candidate.comparison is None:
        return []
    return _canonical_refs([
        ref
        for item in candidate.comparison.comparisons
        for ref in item.evidence_refs
    ])[:6]


def _immutable_reference_map(
    *,
    internal_to_provider: dict[str, str],
    candidate_to_provider: dict[str, str],
) -> ProviderReferenceMap:
    provider_to_internal = {value: key for key, value in internal_to_provider.items()}
    provider_to_candidate = {value: key for key, value in candidate_to_provider.items()}
    if len(provider_to_internal) != len(internal_to_provider):
        raise ValueError("provider reference mapping is not bijective")
    if len(provider_to_candidate) != len(candidate_to_provider):
        raise ValueError("provider Candidate mapping is not bijective")
    return ProviderReferenceMap(
        internal_to_provider=MappingProxyType(dict(internal_to_provider)),
        provider_to_internal=MappingProxyType(provider_to_internal),
        candidate_to_provider=MappingProxyType(dict(candidate_to_provider)),
        provider_to_candidate=MappingProxyType(provider_to_candidate),
    )


def _verify_reference_map_binding(
    reference_map: ProviderReferenceMap,
    *,
    bundle: InternalEvidenceBundleV1,
    evidence_facts: EvidenceFactsV1,
) -> None:
    """Reject substituted maps even when their forward/reverse dicts agree."""

    expected = ProviderReferenceProjector().project(
        bundle=bundle,
        evidence_facts=evidence_facts,
    ).reference_map
    if (
        dict(reference_map.internal_to_provider) != dict(expected.internal_to_provider)
        or dict(reference_map.provider_to_internal) != dict(expected.provider_to_internal)
        or dict(reference_map.candidate_to_provider) != dict(expected.candidate_to_provider)
        or dict(reference_map.provider_to_candidate) != dict(expected.provider_to_candidate)
    ):
        raise ValueError("provider reference mapping does not match its deterministic projection binding")


def _validate_owner(
    bundle: InternalEvidenceBundleV1,
    *,
    candidate_id: str,
    result_rank: int,
    refs: list[str],
) -> None:
    validate_fact_references(
        bundle,
        candidate_id=candidate_id,
        result_rank=result_rank,
        evidence_refs=refs,
    )


def resolve_explanation_plan(
    plan: ExplanationPlanV1,
    *,
    reference_map: ProviderReferenceMap,
    bundle: InternalEvidenceBundleV1,
    evidence_facts: EvidenceFactsV1,
) -> ResolvedExplanationPlanV1:
    """Resolve opaque selections and fail closed before anything is persisted."""

    validate_evidence_facts(bundle, evidence_facts)
    _verify_reference_map_binding(
        reference_map,
        bundle=bundle,
        evidence_facts=evidence_facts,
    )
    expected_candidates = [
        reference_map.candidate_to_provider[candidate.candidate_id]
        for candidate in evidence_facts.candidates
    ]
    actual_candidates = [candidate.candidate_ref for candidate in plan.candidates]
    if actual_candidates != expected_candidates:
        raise ValueError("Explanation Plan Candidate coverage does not match evidence facts")

    resolved_candidates = []
    for item in plan.candidates:
        try:
            candidate_id = reference_map.provider_to_candidate[item.candidate_ref]
        except KeyError as error:
            raise ValueError(f"unknown provider Candidate reference: {item.candidate_ref}") from error
        evidence_candidate = next(
            candidate
            for candidate in evidence_facts.candidates
            if candidate.candidate_id == candidate_id
        )
        if item.result_rank != evidence_candidate.result_rank:
            raise ValueError("Explanation Plan rank does not match provider Candidate reference")

        def resolve_checked(refs: list[str]) -> list[str]:
            resolved = _resolve_refs(reference_map, refs)
            _validate_owner(
                bundle,
                candidate_id=candidate_id,
                result_rank=item.result_rank,
                refs=resolved,
            )
            return resolved

        resolved_candidates.append(
            ResolvedExplanationPlanCandidate(
                candidate_id=candidate_id,
                result_rank=item.result_rank,
                summary=ResolvedSummary(
                    template_key=item.summary.template_key,
                    evidence_refs=resolve_checked(item.summary.evidence_refs),
                ),
                match_reasons=[
                    ResolvedMatchReason(
                        category=reason.category,
                        template_key=reason.template_key,
                        evidence_refs=resolve_checked(reason.evidence_refs),
                    )
                    for reason in item.match_reasons
                ],
                risk_points=[
                    ResolvedRiskPoint(
                        category=risk.category,
                        template_key=risk.template_key,
                        evidence_refs=resolve_checked(risk.evidence_refs),
                    )
                    for risk in item.risk_points
                ],
                interview_question_operations=[
                    ResolvedInterviewQuestionOperation(
                        operation=operation.operation,
                        evidence_refs=resolve_checked(operation.evidence_refs),
                    )
                    for operation in item.interview_question_operations
                ],
                why_not_top1=(
                    None
                    if item.why_not_top1 is None
                    else ResolvedWhyNotTop1(
                        template_key=item.why_not_top1.template_key,
                        evidence_refs=resolve_checked(item.why_not_top1.evidence_refs),
                    )
                ),
                rewrite_operations=[
                    ResolvedRewriteOperation(
                        operation=operation.operation,
                        evidence_refs=resolve_checked(operation.evidence_refs),
                    )
                    for operation in item.rewrite_operations
                ],
            )
        )
    return ResolvedExplanationPlanV1(
        contract_version="resolved_explanation_plan_v1",
        candidates=resolved_candidates,
    )


__all__ = [
    "ProjectedProviderEvidence",
    "ProviderReferenceMap",
    "ProviderReferenceProjector",
    "resolve_explanation_plan",
]
