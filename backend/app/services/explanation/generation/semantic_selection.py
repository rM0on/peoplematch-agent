"""Request-scoped semantic choices bound to the unchanged ExplanationPlanV1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Union

from pydantic import ConfigDict, Field, StrictStr, StringConstraints

from app.schemas.explanations import InternalEvidenceBundleV1
from app.services.explanation.evidence.contracts import EvidenceFactsV1
from app.services.explanation.evidence.normalization import normalize_label
from app.services.explanation.evidence.validation import validate_evidence_facts
from app.services.explanation.generation.contracts import (
    ExplanationPlanV1,
    GenerationContractModel,
    PlanInterviewQuestionOperation,
    PlanMatchReason,
    PlanRewriteOperation,
    PlanRiskPoint,
    PlanWhyNotTop1,
)
from app.services.explanation.generation.reference_projection import (
    ProjectedProviderEvidence,
    ProviderReferenceProjector,
)


OptionHandle = Annotated[StrictStr, StringConstraints(pattern=r"^opt_[0-9]{4}$")]
OptionKind = Literal["reason", "risk", "interview", "rewrite"]
OptionValue = Union[
    PlanMatchReason, PlanRiskPoint, PlanInterviewQuestionOperation, PlanRewriteOperation,
]
_REASON_ORDER = {
    "skill_fit": 0, "project_evidence": 1, "location": 2,
    "seniority": 3, "ranking_context": 4,
}


class ProviderCandidateSemanticSelection(GenerationContractModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    candidate_ref: Annotated[StrictStr, StringConstraints(pattern=r"^candidate_[0-9]{4}$")]
    match_reason_handles: list[OptionHandle] = Field(min_length=1, max_length=4)
    risk_handles: list[OptionHandle] = Field(max_length=4)
    interview_handles: list[OptionHandle] = Field(max_length=3)
    rewrite_handles: list[OptionHandle] = Field(max_length=3)
    summary_primary_reason_handle: OptionHandle


class ProviderExplanationSelectionV1(GenerationContractModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    contract_version: Literal["provider_explanation_selection_v1"]
    candidates: list[ProviderCandidateSemanticSelection] = Field(min_length=1, max_length=10)


class SemanticSelectionError(ValueError):
    """Closed diagnostic; never include a handle or source value in its message."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("Provider semantic selection does not match its catalog")


@dataclass(frozen=True)
class SemanticOption:
    handle: str
    candidate_ref: str
    kind: OptionKind
    value: OptionValue
    metadata: tuple[tuple[str, str], ...] = ()

    def provider_payload(self) -> dict:
        return {
            "handle": self.handle,
            "kind": self.kind,
            "category": getattr(self.value, "category", getattr(self.value, "operation", None)),
            "evidence_refs": list(self.value.evidence_refs),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CandidateSemanticOptions:
    candidate_ref: str
    result_rank: int
    options: tuple[SemanticOption, ...]
    comparison: PlanWhyNotTop1 | None


@dataclass(frozen=True)
class SemanticOptionCatalog:
    candidates: tuple[CandidateSemanticOptions, ...]

    def provider_payload(self) -> dict:
        return {
            "contract_version": "provider_semantic_option_catalog_v1",
            "candidates": [
                {
                    "candidate_ref": candidate.candidate_ref,
                    "options": [option.provider_payload() for option in candidate.options],
                }
                for candidate in self.candidates
            ],
        }


def _canonical(refs: list[str]) -> list[str]:
    return sorted(set(refs))


def _rewrite_options(candidate, prompt_candidate, internal_to_provider):
    """Offer only bounded combinations accepted by the existing rewrite policy."""

    def provider_ref(internal_id: str) -> str:
        return internal_to_provider[internal_id]

    values: list[PlanRewriteOperation] = []
    # Rewrite is optional. Only source objects already admitted by the closed
    # request projection can become provider-visible options; do not enlarge
    # that projection to make a rewrite option possible.
    skills = [item for item in candidate.skills if item.evidence_id in internal_to_provider]
    projects = [item for item in candidate.projects if item.evidence_id in internal_to_provider]
    records = [item for item in candidate.project_evidence if item.evidence_id in internal_to_provider]
    for skill in skills:
        ref = provider_ref(skill.evidence_id)
        values.append(PlanRewriteOperation(operation="surface_existing_skill", evidence_refs=[ref]))
        values.append(PlanRewriteOperation(operation="reorder_existing_claim", evidence_refs=[ref]))
    for project in projects:
        ref = provider_ref(project.evidence_id)
        values.append(PlanRewriteOperation(operation="reorder_existing_claim", evidence_refs=[ref]))
    for record in records:
        ref = provider_ref(record.evidence_id)
        values.append(PlanRewriteOperation(operation="clarify_evidence_status", evidence_refs=[ref]))
        values.append(PlanRewriteOperation(operation="reorder_existing_claim", evidence_refs=[ref]))
    for skill in skills:
        skill_name = normalize_label(skill.name, "rewrite skill")
        for project in projects:
            related = (*project.technologies, *project.skills_demonstrated)
            if skill_name in {normalize_label(label, "rewrite project skill") for label in related}:
                values.append(PlanRewriteOperation(
                    operation="link_skill_to_project",
                    evidence_refs=_canonical([provider_ref(skill.evidence_id), provider_ref(project.evidence_id)]),
                ))
        for record in records:
            owner = next((item for item in projects if item.project_id == record.project_id), None)
            related = list(record.supports_skills)
            if owner is not None:
                related.extend((*owner.technologies, *owner.skills_demonstrated))
            if skill_name in {normalize_label(label, "rewrite project skill") for label in related}:
                values.append(PlanRewriteOperation(
                    operation="link_skill_to_project",
                    evidence_refs=_canonical([provider_ref(skill.evidence_id), provider_ref(record.evidence_id)]),
                ))
    for gap in prompt_candidate.facts.missing_requirements:
        if gap.status in {"missing", "partial"} and gap.evidence_status != "available":
            values.append(PlanRewriteOperation(
                operation="state_gap_explicitly", evidence_refs=list(gap.evidence_refs),
            ))
    by_key = {value.model_dump_json(): value for value in values}
    return [by_key[key] for key in sorted(by_key)]


def build_semantic_option_catalog(
    *,
    bundle: InternalEvidenceBundleV1,
    evidence_facts: EvidenceFactsV1,
    projected: ProjectedProviderEvidence,
) -> SemanticOptionCatalog:
    """Rebuild the trusted projection before exposing any selectable option."""

    validate_evidence_facts(bundle, evidence_facts)
    expected = ProviderReferenceProjector().project(bundle=bundle, evidence_facts=evidence_facts)
    if projected != expected:
        raise ValueError("semantic option catalog source projection mismatch")
    internal_to_provider = projected.reference_map.internal_to_provider
    built = []
    next_handle = 1
    for source, prompt_candidate in zip(bundle.candidates, projected.payload.candidates):
        options: list[SemanticOption] = []

        def append(kind: OptionKind, value: OptionValue, metadata=()) -> None:
            nonlocal next_handle
            if next_handle > 9999:
                raise ValueError("semantic option catalog exceeds handle capacity")
            if not set(value.evidence_refs) <= set(projected.reference_map.provider_to_internal):
                raise ValueError("semantic option references evidence outside the safe projection")
            options.append(SemanticOption(
                handle=f"opt_{next_handle:04d}",
                candidate_ref=prompt_candidate.candidate_ref,
                kind=kind,
                value=value,
                metadata=tuple(metadata),
            ))
            next_handle += 1

        facts = prompt_candidate.facts
        reasons = [
            PlanMatchReason(
                category=item.category, template_key=item.statement_key,
                evidence_refs=list(item.evidence_refs),
            ) for item in facts.match_reasons
        ]
        reasons.extend(
            PlanMatchReason(
                category="ranking_context", template_key="ranking_context_recorded",
                evidence_refs=list(item.evidence_refs),
            ) for item in facts.ranking_context
        )
        for value in sorted(reasons, key=lambda item: (_REASON_ORDER[item.category], item.model_dump_json())):
            append("reason", value)
        for item in sorted(facts.risks, key=lambda value: value.model_dump_json()):
            append("risk", PlanRiskPoint(
                category=item.category, template_key=item.statement_key,
                evidence_refs=list(item.evidence_refs),
            ))
        for item in sorted(facts.missing_requirements, key=lambda value: value.model_dump_json()):
            if item.status in {"missing", "partial"}:
                append("interview", PlanInterviewQuestionOperation(
                    operation="ask_evidence_clarification", evidence_refs=list(item.evidence_refs),
                ), (("priority", item.priority), ("status", item.status),
                    ("evidence_status", item.evidence_status)))
        for value in _rewrite_options(source, prompt_candidate, internal_to_provider):
            append("rewrite", value)
        comparison = None if facts.comparison is None else PlanWhyNotTop1(
            template_key="why_not_top1_recorded",
            evidence_refs=list(facts.comparison.evidence_refs),
        )
        built.append(CandidateSemanticOptions(
            candidate_ref=prompt_candidate.candidate_ref,
            result_rank=prompt_candidate.result_rank,
            options=tuple(options),
            comparison=comparison,
        ))
    return SemanticOptionCatalog(candidates=tuple(built))


def bind_semantic_selection(
    selection: ProviderExplanationSelectionV1,
    *, catalog: SemanticOptionCatalog,
) -> ExplanationPlanV1:
    """Reject bad selections, then assemble an unchanged canonical internal plan."""

    by_candidate = {candidate.candidate_ref: candidate for candidate in catalog.candidates}
    actual_refs = [candidate.candidate_ref for candidate in selection.candidates]
    if len(actual_refs) != len(set(actual_refs)):
        raise SemanticSelectionError("selection_duplicate_candidate")
    if set(actual_refs) != set(by_candidate):
        raise SemanticSelectionError("selection_candidate_coverage")
    selected = {candidate.candidate_ref: candidate for candidate in selection.candidates}
    output = []
    for source in catalog.candidates:
        item = selected[source.candidate_ref]
        options = {option.handle: option for option in source.options}

        def resolve(handles: list[str], kind: OptionKind) -> list[OptionValue]:
            if len(handles) != len(set(handles)):
                raise SemanticSelectionError("selection_duplicate_handle")
            values = []
            for handle in handles:
                option = options.get(handle)
                if option is None:
                    raise SemanticSelectionError("selection_unknown_or_cross_candidate_handle")
                if option.kind != kind:
                    raise SemanticSelectionError("selection_wrong_option_type")
                values.append(option.value)
            return values

        reasons = resolve(item.match_reason_handles, "reason")
        risks = resolve(item.risk_handles, "risk")
        interviews = resolve(item.interview_handles, "interview")
        rewrites = resolve(item.rewrite_handles, "rewrite")
        if item.summary_primary_reason_handle not in item.match_reason_handles:
            raise SemanticSelectionError("selection_summary_reason_not_selected")
        primary = options[item.summary_primary_reason_handle]
        if primary.kind != "reason":
            raise SemanticSelectionError("selection_wrong_option_type")
        reasons.sort(key=lambda value: (_REASON_ORDER[value.category], value.model_dump_json()))
        if len({value.category for value in reasons}) != len(reasons):
            raise SemanticSelectionError("selection_incompatible_reasons")
        output.append({
            "candidate_ref": source.candidate_ref,
            "result_rank": source.result_rank,
            "summary": {
                "template_key": "recorded_match_summary",
                "evidence_refs": list(primary.value.evidence_refs),
            },
            "match_reasons": reasons,
            "risk_points": sorted(risks, key=lambda value: value.model_dump_json()),
            "interview_question_operations": sorted(
                interviews, key=lambda value: value.model_dump_json(),
            ),
            "why_not_top1": source.comparison,
            "rewrite_operations": sorted(rewrites, key=lambda value: value.model_dump_json()),
        })
    return ExplanationPlanV1.model_validate({
        "contract_version": "explanation_plan_v1", "candidates": output,
    })


__all__ = [
    "ProviderExplanationSelectionV1", "SemanticOptionCatalog", "SemanticSelectionError",
    "bind_semantic_selection", "build_semantic_option_catalog",
]
