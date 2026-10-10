from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel
from app.services.explanation.presentation.contracts_v2 import (
    NarrativeConcernV2, NarrativeInterviewFocusV2, NarrativePassageV2, NarrativeStrengthV2,
)


class RecruiterNarrativeV2_2(ContractModel):
    contract_version: Literal["recruiter_narrative_v2_2"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    candidate_snapshot: NarrativePassageV2
    why_consider: NarrativePassageV2
    key_strengths: list[NarrativeStrengthV2] = Field(min_length=1, max_length=3)
    trade_offs: list[NarrativeConcernV2] = Field(max_length=3)
    interview_focus: list[NarrativeInterviewFocusV2] = Field(min_length=1, max_length=3)


__all__ = ["RecruiterNarrativeV2_2"]
