"""Read-only recruiter-facing projection of canonical source-backed propositions."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import ConfigDict, Field

from app.schemas.shared import ContractModel
from app.services.explanation.presentation.contracts_proposition_v1 import RecruiterPropositionV1


class StructuredRecruiterBriefV1(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["structured_recruiter_brief_v1"] = "structured_recruiter_brief_v1"
    review_status: Literal["TRUSTED_STRUCTURED"] = "TRUSTED_STRUCTURED"
    match_run_id: str = Field(min_length=1)
    explanation_run_id: str = Field(min_length=1)
    source_explanation_id: int = Field(gt=0)
    candidate_id: str = Field(min_length=1)
    result_rank: int = Field(ge=1)
    ranking_fingerprint: str = Field(min_length=64, max_length=64)
    source_output_fingerprint: str = Field(min_length=64, max_length=64)
    source_bundle_fingerprint: str = Field(min_length=64, max_length=64)
    review_action: Optional[RecruiterPropositionV1]
    why_review: tuple[RecruiterPropositionV1, ...]
    technical_signals: tuple[RecruiterPropositionV1, ...]
    unknowns: tuple[RecruiterPropositionV1, ...]
    verification_targets: tuple[RecruiterPropositionV1, ...]

    def all_propositions(self) -> tuple[RecruiterPropositionV1, ...]:
        return (
            ((self.review_action,) if self.review_action is not None else ())
            + self.why_review + self.technical_signals + self.unknowns
            + self.verification_targets
        )


__all__ = ["StructuredRecruiterBriefV1"]
