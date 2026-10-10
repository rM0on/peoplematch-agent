from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel
from app.services.explanation.presentation.contracts_v2 import FactId


DecisionText = Annotated[str, StringConstraints(min_length=8, max_length=260)]


class HiringRationaleV2_3(ContractModel):
    statement: DecisionText
    supporting_facts: list[FactId] = Field(min_length=2, max_length=8)
    verification_focus: DecisionText


class HiringDecisionSummaryV2_3(ContractModel):
    decision: Literal["prioritize_review", "needs_verification"]
    rationale: list[HiringRationaleV2_3] = Field(min_length=1, max_length=3)


class RecruiterNarrativeV2_3(ContractModel):
    contract_version: Literal["recruiter_narrative_v2_3"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    decision_summary: HiringDecisionSummaryV2_3


__all__ = ["RecruiterNarrativeV2_3", "HiringDecisionSummaryV2_3", "HiringRationaleV2_3"]
