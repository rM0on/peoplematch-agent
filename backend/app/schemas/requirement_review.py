"""Read-only requirement inspection; no new candidate capability claims."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from app.schemas.explanations import (
    CANDIDATE_PROJECT_EVIDENCE_ID_PATTERN,
    CANDIDATE_PROJECT_RECORD_EVIDENCE_ID_PATTERN,
    CANDIDATE_SKILL_EVIDENCE_ID_PATTERN,
)
from app.schemas.shared import ContractModel
from app.services.explanation.presentation.contracts_proposition_v1 import RecruiterPropositionV1


class RequirementReviewRowV1(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str = Field(min_length=1)
    priority: Literal["must_have", "nice_to_have"]
    text: str = Field(min_length=1)
    diagnostic_status: Literal["matched", "partial", "missing", "not_assessed"]
    evidence_status: Literal["available", "claim_only", "absent", "not_assessed"]
    source_refs: tuple[str, ...] = Field(min_length=1)
    propositions: tuple[RecruiterPropositionV1, ...]


class RequirementSourceDescriptorV1(ContractModel):
    """Readable metadata copied only from the frozen historical Evidence Bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_ref: str = Field(min_length=1)
    source_kind: Literal["historical_skill_claim", "historical_project", "historical_project_record"]
    description: str = Field(min_length=1, max_length=500)

    @field_validator("evidence_ref")
    @classmethod
    def canonical_historical_ref(cls, value: str) -> str:
        if not any(re.fullmatch(pattern, value) for pattern in (
            CANDIDATE_SKILL_EVIDENCE_ID_PATTERN,
            CANDIDATE_PROJECT_EVIDENCE_ID_PATTERN,
            CANDIDATE_PROJECT_RECORD_EVIDENCE_ID_PATTERN,
        )):
            raise ValueError("invalid_historical_candidate_ref")
        return value


class RequirementReviewV1(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["requirement_review_v1"] = "requirement_review_v1"
    role_title: str = Field(min_length=1)
    match_run_id: str = Field(min_length=1)
    explanation_run_id: str = Field(min_length=1)
    source_explanation_id: int = Field(gt=0)
    candidate_id: str = Field(min_length=1)
    result_rank: int = Field(ge=1)
    ranking_fingerprint: str = Field(min_length=64, max_length=64)
    source_output_fingerprint: str = Field(min_length=64, max_length=64)
    source_bundle_fingerprint: str = Field(min_length=64, max_length=64)
    requirements: tuple[RequirementReviewRowV1, ...] = Field(min_length=1)
    source_descriptors: tuple[RequirementSourceDescriptorV1, ...]
    cross_requirement_propositions: tuple[RecruiterPropositionV1, ...] = ()


__all__ = ["RequirementReviewRowV1", "RequirementSourceDescriptorV1", "RequirementReviewV1"]
