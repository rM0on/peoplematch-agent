from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.schemas.explanations import EvidenceId
from app.schemas.shared import ContractModel


NarrativeText = Annotated[str, StringConstraints(min_length=8, max_length=280)]


class NarrativeStatement(ContractModel):
    text: NarrativeText
    evidence_links: list[EvidenceId] = Field(min_length=1, max_length=6)


class RecruiterNarrativeV1(ContractModel):
    """A separate presentation artifact; never a ranking or Phase 9 contract."""

    contract_version: Literal["recruiter_narrative_v1"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    candidate_summary: NarrativeStatement
    recommendation_summary: NarrativeStatement
    strengths: list[NarrativeStatement] = Field(min_length=1, max_length=3)
    risks: list[NarrativeStatement] = Field(max_length=3)
    interview_focus: list[NarrativeStatement] = Field(max_length=3)
    evidence_links: list[EvidenceId] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def links_are_canonical_union(self) -> "RecruiterNarrativeV1":
        statements = [
            self.candidate_summary,
            self.recommendation_summary,
            *self.strengths,
            *self.risks,
            *self.interview_focus,
        ]
        for statement in statements:
            if statement.evidence_links != sorted(set(statement.evidence_links)):
                raise ValueError("narrative statement links must be sorted and unique")
        expected = sorted({ref for statement in statements for ref in statement.evidence_links})
        if self.evidence_links != expected:
            raise ValueError("narrative evidence links must equal statement link union")
        return self


__all__ = ["NarrativeStatement", "RecruiterNarrativeV1"]
