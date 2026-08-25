from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import (
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.schemas.explanations import EvidenceId
from app.schemas.shared import ContractModel


class GenerationContractModel(ContractModel):
    """Closed transport contracts for the untrusted provider boundary."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


ProviderReference = Annotated[
    StrictStr,
    StringConstraints(pattern=r"^ref_[0-9]{4}$"),
]
ProviderCandidateReference = Annotated[
    StrictStr,
    StringConstraints(pattern=r"^candidate_[0-9]{4}$"),
]
StrictPlanRank = Annotated[StrictInt, Field(ge=1, le=10)]
ProviderRefs = Annotated[list[ProviderReference], Field(min_length=1, max_length=6)]
InternalRefs = Annotated[list[EvidenceId], Field(min_length=1, max_length=6)]

ReasonCategory = Literal[
    "skill_fit",
    "project_evidence",
    "location",
    "seniority",
    "ranking_context",
]
ReasonTemplateKey = Literal[
    "skill_fit_recorded",
    "project_evidence_recorded",
    "location_recorded",
    "seniority_recorded",
    "ranking_context_recorded",
]
RiskCategory = Literal[
    "missing_requirement",
    "weak_evidence",
    "overclaim_signal",
]
RiskTemplateKey = Literal[
    "missing_requirement",
    "partial_requirement_evidence",
    "recorded_overclaim_signal",
]
RewriteOperation = Literal[
    "surface_existing_skill",
    "link_skill_to_project",
    "clarify_evidence_status",
    "reorder_existing_claim",
    "state_gap_explicitly",
]


class ProviderPromptRequirement(GenerationContractModel):
    requirement_ref: ProviderReference
    priority: Literal["must_have", "nice_to_have"]
    category: Literal[
        "skill",
        "responsibility",
        "domain",
        "constraint",
    ]


class ProviderPromptJob(GenerationContractModel):
    requirements: list[ProviderPromptRequirement] = Field(min_length=1, max_length=100)


class ProviderReferenceSelection(GenerationContractModel):
    """A provider may select only a canonical, duplicate-free ref sequence."""

    evidence_refs: ProviderRefs

    @field_validator("evidence_refs")
    @classmethod
    def references_are_unique_and_canonical(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("provider references must be unique and canonical")
        return value


class ProviderPromptMatchReason(ProviderReferenceSelection):
    category: ReasonCategory
    statement_key: Literal[
        "skill_fit_recorded",
        "project_evidence_recorded",
        "location_recorded",
        "seniority_recorded",
    ]


class ProviderPromptRankingContext(ProviderReferenceSelection):
    dimension: Literal[
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
        "result_rank",
        "ltr_rank",
        "ltr_score_raw",
        "cross_encoder_rank",
        "cross_encoder_score_raw",
    ]


class ProviderPromptRisk(ProviderReferenceSelection):
    category: RiskCategory
    statement_key: RiskTemplateKey

    @model_validator(mode="after")
    def category_matches_template(self) -> "ProviderPromptRisk":
        expected = {
            "missing_requirement": "missing_requirement",
            "weak_evidence": "partial_requirement_evidence",
            "overclaim_signal": "recorded_overclaim_signal",
        }
        if self.statement_key != expected[self.category]:
            raise ValueError("risk template key does not match its category")
        return self


class ProviderPromptMissingRequirement(ProviderReferenceSelection):
    requirement_ref: ProviderReference
    priority: Literal["must_have", "nice_to_have"]
    status: Literal["matched", "partial", "missing", "not_assessed"]
    evidence_status: Literal["available", "claim_only", "absent", "not_assessed"]


class ProviderPromptComparison(ProviderReferenceSelection):
    top1_candidate_ref: ProviderCandidateReference
    dimensions: list[
        Literal[
            "retrieval_rank",
            "skill_fit_score",
            "project_evidence_score",
            "role_direction_score",
            "ai_tool_score",
            "location_score",
            "seniority_score",
            "ltr_rank",
            "ltr_score_raw",
            "cross_encoder_rank",
            "cross_encoder_score_raw",
            "requirement_evidence_coverage",
        ]
    ] = Field(max_length=20)


class ProviderPromptFacts(GenerationContractModel):
    match_reasons: list[ProviderPromptMatchReason] = Field(max_length=20)
    ranking_context: list[ProviderPromptRankingContext] = Field(max_length=20)
    risks: list[ProviderPromptRisk] = Field(max_length=20)
    missing_requirements: list[ProviderPromptMissingRequirement] = Field(max_length=100)
    comparison: Optional[ProviderPromptComparison] = None


class ProviderPromptCandidate(GenerationContractModel):
    candidate_ref: ProviderCandidateReference
    result_rank: StrictPlanRank
    facts: ProviderPromptFacts


class ProviderPromptEvidenceV1(GenerationContractModel):
    contract_version: Literal["provider_prompt_evidence_v1"]
    job: ProviderPromptJob
    candidates: list[ProviderPromptCandidate] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def candidates_are_canonical(self) -> "ProviderPromptEvidenceV1":
        ranks = [candidate.result_rank for candidate in self.candidates]
        refs = [candidate.candidate_ref for candidate in self.candidates]
        if ranks != list(range(1, len(self.candidates) + 1)):
            raise ValueError("provider prompt Candidates must be the ordered top-k prefix")
        if len(refs) != len(set(refs)):
            raise ValueError("provider prompt Candidate references must be unique")
        return self


class PlanSummary(ProviderReferenceSelection):
    template_key: Literal["recorded_match_summary"]


class PlanMatchReason(ProviderReferenceSelection):
    category: ReasonCategory
    template_key: ReasonTemplateKey

    @model_validator(mode="after")
    def category_matches_template(self) -> "PlanMatchReason":
        expected = {
            "skill_fit": "skill_fit_recorded",
            "project_evidence": "project_evidence_recorded",
            "location": "location_recorded",
            "seniority": "seniority_recorded",
            "ranking_context": "ranking_context_recorded",
        }
        if self.template_key != expected[self.category]:
            raise ValueError("reason template key does not match its category")
        return self


class PlanRiskPoint(ProviderReferenceSelection):
    category: RiskCategory
    template_key: RiskTemplateKey

    @model_validator(mode="after")
    def category_matches_template(self) -> "PlanRiskPoint":
        expected = {
            "missing_requirement": "missing_requirement",
            "weak_evidence": "partial_requirement_evidence",
            "overclaim_signal": "recorded_overclaim_signal",
        }
        if self.template_key != expected[self.category]:
            raise ValueError("risk template key does not match its category")
        return self


class PlanInterviewQuestionOperation(ProviderReferenceSelection):
    operation: Literal["ask_evidence_clarification"]


class PlanWhyNotTop1(ProviderReferenceSelection):
    template_key: Literal["why_not_top1_recorded"]


class PlanRewriteOperation(ProviderReferenceSelection):
    operation: RewriteOperation


class ExplanationPlanCandidate(GenerationContractModel):
    candidate_ref: ProviderCandidateReference
    result_rank: StrictPlanRank
    summary: PlanSummary
    match_reasons: list[PlanMatchReason] = Field(min_length=1, max_length=4)
    risk_points: list[PlanRiskPoint] = Field(max_length=4)
    interview_question_operations: list[PlanInterviewQuestionOperation] = Field(max_length=3)
    why_not_top1: Optional[PlanWhyNotTop1] = None
    rewrite_operations: list[PlanRewriteOperation] = Field(max_length=3)

    @model_validator(mode="after")
    def rank_one_has_no_comparison(self) -> "ExplanationPlanCandidate":
        if self.result_rank == 1 and self.why_not_top1 is not None:
            raise ValueError("rank-one Explanation Plan cannot contain why_not_top1")
        if self.result_rank > 1 and self.why_not_top1 is None:
            raise ValueError("non-top-one Explanation Plan requires why_not_top1")
        category_order = {
            "skill_fit": 0,
            "project_evidence": 1,
            "location": 2,
            "seniority": 3,
            "ranking_context": 4,
        }
        order = [category_order[item.category] for item in self.match_reasons]
        if order != sorted(order) or len(order) != len(set(order)):
            raise ValueError("match reason selections must be unique and canonical")
        for label, selections in (
            ("risk selections", self.risk_points),
            ("interview selections", self.interview_question_operations),
            ("rewrite selections", self.rewrite_operations),
        ):
            keys = [item.model_dump_json() for item in selections]
            if keys != sorted(keys) or len(keys) != len(set(keys)):
                raise ValueError(f"{label} must be unique and canonical")
        return self


class ExplanationPlanV1(GenerationContractModel):
    contract_version: Literal["explanation_plan_v1"]
    candidates: list[ExplanationPlanCandidate] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def candidates_are_canonical(self) -> "ExplanationPlanV1":
        ranks = [candidate.result_rank for candidate in self.candidates]
        refs = [candidate.candidate_ref for candidate in self.candidates]
        if ranks != list(range(1, len(self.candidates) + 1)):
            raise ValueError("Explanation Plan Candidates must be the ordered top-k prefix")
        if len(refs) != len(set(refs)):
            raise ValueError("Explanation Plan Candidate references must be unique")
        return self


class ResolvedReferenceSelection(GenerationContractModel):
    evidence_refs: InternalRefs


class ResolvedSummary(ResolvedReferenceSelection):
    template_key: Literal["recorded_match_summary"]


class ResolvedMatchReason(ResolvedReferenceSelection):
    category: ReasonCategory
    template_key: ReasonTemplateKey


class ResolvedRiskPoint(ResolvedReferenceSelection):
    category: RiskCategory
    template_key: RiskTemplateKey


class ResolvedInterviewQuestionOperation(ResolvedReferenceSelection):
    operation: Literal["ask_evidence_clarification"]


class ResolvedWhyNotTop1(ResolvedReferenceSelection):
    template_key: Literal["why_not_top1_recorded"]


class ResolvedRewriteOperation(ResolvedReferenceSelection):
    operation: RewriteOperation


class ResolvedExplanationPlanCandidate(GenerationContractModel):
    candidate_id: Annotated[StrictStr, StringConstraints(min_length=1, max_length=80)]
    result_rank: StrictPlanRank
    summary: ResolvedSummary
    match_reasons: list[ResolvedMatchReason] = Field(min_length=1, max_length=4)
    risk_points: list[ResolvedRiskPoint] = Field(max_length=4)
    interview_question_operations: list[ResolvedInterviewQuestionOperation] = Field(max_length=3)
    why_not_top1: Optional[ResolvedWhyNotTop1] = None
    rewrite_operations: list[ResolvedRewriteOperation] = Field(max_length=3)


class ResolvedExplanationPlanV1(GenerationContractModel):
    contract_version: Literal["resolved_explanation_plan_v1"]
    candidates: list[ResolvedExplanationPlanCandidate] = Field(min_length=1, max_length=10)


__all__ = [
    "ExplanationPlanV1",
    "ProviderPromptEvidenceV1",
    "ResolvedExplanationPlanV1",
]
