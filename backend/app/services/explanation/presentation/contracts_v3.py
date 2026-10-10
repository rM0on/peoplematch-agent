"""Independent V3 recruiter presentation contract; does not alter ExplanationPlanV1."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel
from app.services.explanation.presentation.contracts_v2 import FactId


ClaimTypeV3 = Literal[
    "evidence_statement", "capability_inference", "interview_validation", "uncertainty_statement",
]
DecisionV3 = Literal["prioritize_review", "needs_verification"]
DecisionTextV3 = Annotated[str, StringConstraints(min_length=8, max_length=260)]


class RecruiterClaimV3(ContractModel):
    text: DecisionTextV3
    claim_type: ClaimTypeV3
    fact_ids: list[FactId] = Field(min_length=1, max_length=6)


class RecruiterNarrativeV3(ContractModel):
    contract_version: Literal["recruiter_narrative_v3"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    decision: DecisionV3
    decision_summary: RecruiterClaimV3
    strengths: list[RecruiterClaimV3] = Field(min_length=1, max_length=3)
    risks: list[RecruiterClaimV3] = Field(min_length=1, max_length=2)
    interview_focus: list[RecruiterClaimV3] = Field(min_length=1, max_length=2)


__all__ = ["RecruiterClaimV3", "RecruiterNarrativeV3"]
