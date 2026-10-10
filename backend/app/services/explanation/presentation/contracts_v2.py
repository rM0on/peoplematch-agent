from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel


RecruiterText = Annotated[str, StringConstraints(min_length=8, max_length=360)]
FactId = Annotated[str, StringConstraints(pattern=r"^fact:[0-9a-f]{32}$")]


class NarrativePassageV2(ContractModel):
    text: RecruiterText
    fact_ids: list[FactId] = Field(min_length=1, max_length=8)


class NarrativeStrengthV2(ContractModel):
    title: Annotated[str, StringConstraints(min_length=2, max_length=80)]
    explanation: RecruiterText
    fact_ids: list[FactId] = Field(min_length=1, max_length=8)


class NarrativeConcernV2(ContractModel):
    title: Annotated[str, StringConstraints(min_length=2, max_length=80)]
    explanation: RecruiterText
    validation_question: RecruiterText
    fact_ids: list[FactId] = Field(min_length=1, max_length=8)


class NarrativeInterviewFocusV2(ContractModel):
    topic: Annotated[str, StringConstraints(min_length=2, max_length=80)]
    question: RecruiterText
    reason: RecruiterText
    fact_ids: list[FactId] = Field(min_length=1, max_length=8)


class RecruiterNarrativeV2(ContractModel):
    contract_version: Literal["recruiter_narrative_v2"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    decision_summary: NarrativePassageV2
    why_review: NarrativePassageV2
    strengths: list[NarrativeStrengthV2] = Field(min_length=1, max_length=3)
    concerns: list[NarrativeConcernV2] = Field(max_length=3)
    interview_focus: list[NarrativeInterviewFocusV2] = Field(min_length=1, max_length=3)


__all__ = ["RecruiterNarrativeV2"]
