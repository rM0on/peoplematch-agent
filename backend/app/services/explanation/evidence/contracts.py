from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import ConfigDict, Field, StrictInt, StringConstraints, model_validator

from app.schemas.explanations import EvidenceId, Fingerprint
from app.schemas.shared import ContractModel


class EvidenceFactContractModel(ContractModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


EVIDENCE_FACTS_VERSION = "evidence_facts_v1"
StrictFactRank = Annotated[StrictInt, Field(ge=1, le=50)]
StrictNonTop1Rank = Annotated[StrictInt, Field(ge=2, le=50)]
ReasonStatementKey = Literal[
    "skill_fit_recorded",
    "project_evidence_recorded",
    "location_recorded",
    "seniority_recorded",
]
RiskStatementKey = Literal[
    "missing_requirement",
    "partial_requirement_evidence",
    "recorded_overclaim_signal",
]
FactCategory = Literal[
    "skill_fit",
    "project_evidence",
    "location",
    "seniority",
]
RiskCategory = Literal[
    "missing_requirement",
    "weak_evidence",
    "overclaim_signal",
]
ComparisonDirection = Literal["higher", "lower", "equal", "unavailable"]
ComparisonDimension = Literal[
    "retrieval_rank",
    "skill_fit_score",
    "project_evidence_score",
    "role_direction_score",
    "ai_tool_score",
    "location_score",
    "seniority_score",
    "ltr_rank",
    "ltr_score_raw",
    "cross_encoder_rank",
    "cross_encoder_score_raw",
    "requirement_evidence_coverage",
]
RequirementStatus = Literal["matched", "partial", "missing", "not_assessed"]
RequirementPriority = Literal["must_have", "nice_to_have"]
RequirementEvidenceStatus = Literal[
    "available", "claim_only", "absent", "not_assessed"
]
RankingContextDimension = Literal[
    "semantic_score",
    "sparse_score",
    "skill_fit_score",
    "project_evidence_score",
    "role_direction_score",
    "ai_tool_score",
    "location_score",
    "seniority_score",
    "missing_penalty",
    "overclaim_penalty",
    "result_rank",
    "ltr_rank",
    "ltr_score_raw",
    "cross_encoder_rank",
    "cross_encoder_score_raw",
]


class MatchReasonFact(EvidenceFactContractModel):
    category: FactCategory
    evidence_refs: list[EvidenceId] = Field(min_length=1, max_length=6)
    statement_key: ReasonStatementKey

    @model_validator(mode="after")
    def category_matches_statement(self) -> "MatchReasonFact":
        expected = {
            "skill_fit": "skill_fit_recorded",
            "project_evidence": "project_evidence_recorded",
            "location": "location_recorded",
            "seniority": "seniority_recorded",
        }
        if self.statement_key != expected[self.category]:
            raise ValueError("reason statement key does not match its category")
        return self


class RiskFact(EvidenceFactContractModel):
    category: RiskCategory
    evidence_refs: list[EvidenceId] = Field(min_length=1, max_length=6)
    statement_key: RiskStatementKey

    @model_validator(mode="after")
    def category_matches_statement(self) -> "RiskFact":
        expected = {
            "missing_requirement": "missing_requirement",
            "weak_evidence": "partial_requirement_evidence",
            "overclaim_signal": "recorded_overclaim_signal",
        }
        if self.statement_key != expected[self.category]:
            raise ValueError("risk statement key does not match its category")
        return self


class RankingContextFact(EvidenceFactContractModel):
    dimension: RankingContextDimension
    evidence_refs: list[EvidenceId] = Field(min_length=1, max_length=1)


class MissingRequirementFact(EvidenceFactContractModel):
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: StrictFactRank
    requirement_id: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=100,
            pattern=r"^[A-Za-z0-9_.-]+$",
        ),
    ]
    priority: RequirementPriority
    status: RequirementStatus
    evidence_status: RequirementEvidenceStatus
    evidence_refs: list[EvidenceId] = Field(min_length=1, max_length=6)


class ComparisonItem(EvidenceFactContractModel):
    dimension: ComparisonDimension
    direction: ComparisonDirection
    evidence_refs: list[EvidenceId] = Field(min_length=1, max_length=6)


class Top1ComparisonFact(EvidenceFactContractModel):
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: StrictNonTop1Rank
    top1_candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    comparisons: list[ComparisonItem] = Field(min_length=1, max_length=20)


class CandidateFactSet(EvidenceFactContractModel):
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: StrictFactRank
    match_reasons: list[MatchReasonFact] = Field(max_length=20)
    ranking_context: list[RankingContextFact] = Field(max_length=20)
    risks: list[RiskFact] = Field(max_length=20)
    missing_requirements: list[MissingRequirementFact] = Field(max_length=100)
    comparison: Optional[Top1ComparisonFact] = None

    @model_validator(mode="after")
    def nested_owners_and_comparison_are_consistent(self) -> "CandidateFactSet":
        for requirement in self.missing_requirements:
            if (
                requirement.candidate_id != self.candidate_id
                or requirement.result_rank != self.result_rank
            ):
                raise ValueError("missing requirement owner does not match Candidate fact set")
        if self.result_rank == 1:
            if self.comparison is not None:
                raise ValueError("rank-1 Candidate cannot contain a top-1 comparison")
        elif self.comparison is None:
            raise ValueError("non-top-one Candidate requires top-1 comparison facts")
        elif (
            self.comparison.candidate_id != self.candidate_id
            or self.comparison.result_rank != self.result_rank
        ):
            raise ValueError("top-1 comparison owner does not match Candidate fact set")
        return self


class EvidenceFactsV1(EvidenceFactContractModel):
    contract_version: Literal["evidence_facts_v1"]
    bundle_fingerprint: Fingerprint
    normalized_content_fingerprint: Fingerprint
    candidates: list[CandidateFactSet] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def candidates_are_unique_and_canonical(self) -> "EvidenceFactsV1":
        candidate_ids = [item.candidate_id for item in self.candidates]
        ranks = [item.result_rank for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Candidate fact IDs must be unique")
        if ranks != list(range(1, len(self.candidates) + 1)):
            raise ValueError("Candidate fact ranks must be the ordered top-k prefix")
        top1_candidate_id = self.candidates[0].candidate_id
        if any(
            item.comparison is not None
            and item.comparison.top1_candidate_id != top1_candidate_id
            for item in self.candidates
        ):
            raise ValueError("Candidate comparisons must reference the rank-1 Candidate")
        return self


class EvidenceReferenceOwner(str, Enum):
    JOB = "job"
    CANDIDATE = "candidate"


__all__ = [
    "CandidateFactSet",
    "ComparisonDimension",
    "ComparisonDirection",
    "ComparisonItem",
    "EVIDENCE_FACTS_VERSION",
    "EvidenceFactsV1",
    "MatchReasonFact",
    "MissingRequirementFact",
    "RankingContextDimension",
    "RankingContextFact",
    "RiskFact",
    "Top1ComparisonFact",
]
