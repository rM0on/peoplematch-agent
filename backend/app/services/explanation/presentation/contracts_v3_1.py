"""Independent V3.1 hiring-review contract; V3 and ExplanationPlanV1 stay intact."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel
from app.services.explanation.presentation.contracts_v2 import FactId


ClaimTypeV3_1 = Literal[
    "evidence_summary", "job_alignment_observation", "interview_validation",
    "review_recommendation",
]
DecisionV3_1 = Literal["prioritize_review", "needs_verification"]
DecisionTextV3_1 = Annotated[str, StringConstraints(min_length=8, max_length=260)]


class RecruiterClaimV3_1(ContractModel):
    text: DecisionTextV3_1
    claim_type: ClaimTypeV3_1
    fact_ids: list[FactId] = Field(min_length=1, max_length=6)


class RecruiterNarrativeV3_1(ContractModel):
    contract_version: Literal["recruiter_narrative_v3_1"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    decision: DecisionV3_1
    decision_summary: RecruiterClaimV3_1
    strengths: list[RecruiterClaimV3_1] = Field(min_length=1, max_length=3)
    risks: list[RecruiterClaimV3_1] = Field(min_length=1, max_length=2)
    interview_focus: list[RecruiterClaimV3_1] = Field(min_length=1, max_length=2)


__all__ = ["RecruiterClaimV3_1", "RecruiterNarrativeV3_1"]
