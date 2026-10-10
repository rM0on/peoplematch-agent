"""Independent recruiter-facing V5 prose contract; all paragraphs cite claims."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel
from app.services.explanation.presentation.contracts_v4 import NarrativeParagraphV4


class RecruiterNarrativeV5(ContractModel):
    contract_version: Literal["recruiter_narrative_v5"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    decision_summary: NarrativeParagraphV4
    why_consider: list[NarrativeParagraphV4] = Field(min_length=1, max_length=2)
    technical_signal: list[NarrativeParagraphV4] = Field(min_length=1, max_length=2)
    interview_focus: list[NarrativeParagraphV4] = Field(min_length=1, max_length=2)
    uncertainty: list[NarrativeParagraphV4] = Field(min_length=1, max_length=2)


__all__ = ["RecruiterNarrativeV5"]
