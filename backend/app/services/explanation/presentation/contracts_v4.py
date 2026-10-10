"""Independent presentation contracts for claim-scoped recruiter language."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel


ClaimTypeV4 = Literal["technical_alignment", "project_depth_validation",
                      "skill_requirement_match", "interview_focus", "review_recommendation"]
RelationTypeV4 = Literal["observed_requirement_overlap", "verify_observed_scope",
                         "listed_skill_overlap", "open_requirement",
                         "alignment_plus_interview_focus"]
ScopeV4 = Literal["technical_direction", "project_verification", "skill_observation",
                  "open_question", "human_review"]


class RecruiterClaimV1(ContractModel):
    claim_id: str = Field(min_length=8, max_length=80)
    candidate_id: str = Field(min_length=1, max_length=80)
    claim_type: ClaimTypeV4
    source_fact_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    relation_type: RelationTypeV4
    allowed_expression_scope: ScopeV4
    forbidden_expression_scope: tuple[str, ...] = Field(min_length=1, max_length=8)
    concepts: tuple[str, ...] = Field(default=(), max_length=12)
    source_claim_ids: tuple[str, ...] = Field(default=(), max_length=6)


class NarrativeParagraphV4(ContractModel):
    text: Annotated[str, StringConstraints(min_length=8, max_length=300)]
    claim_refs: list[str] = Field(min_length=1, max_length=4)


class RecruiterNarrativeV4(ContractModel):
    contract_version: Literal["recruiter_narrative_v4"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    summary: NarrativeParagraphV4
    strengths: list[NarrativeParagraphV4] = Field(min_length=1, max_length=3)
    risks: list[NarrativeParagraphV4] = Field(min_length=1, max_length=2)
    interview_focus: list[NarrativeParagraphV4] = Field(min_length=1, max_length=2)


__all__ = ["RecruiterClaimV1", "RecruiterNarrativeV4", "NarrativeParagraphV4"]
