from __future__ import annotations

from enum import Enum, IntEnum
from typing import List, Literal

from pydantic import Field, model_validator

from app.schemas.shared import ContractModel, SchemaVersion


class DatasetSplit(str, Enum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"


class RelevanceGrade(IntEnum):
    NON_MATCH = 0
    WEAK_OR_MISLEADING = 1
    PLAUSIBLE_MATCH = 2
    STRONG_MATCH = 3


class MismatchCode(str, Enum):
    DIRECTION_MISMATCH = "DIRECTION_MISMATCH"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    KEYWORD_FALSE_POSITIVE = "KEYWORD_FALSE_POSITIVE"
    MUST_HAVE_MISSING = "MUST_HAVE_MISSING"
    LOCATION_MISMATCH = "LOCATION_MISMATCH"
    SENIORITY_MISMATCH = "SENIORITY_MISMATCH"
    WORK_STYLE_MISMATCH = "WORK_STYLE_MISMATCH"
    OVERCLAIM_RISK = "OVERCLAIM_RISK"
    AI_TOOLING_GAP = "AI_TOOLING_GAP"
    PROJECT_DEPTH_GAP = "PROJECT_DEPTH_GAP"


AnnotationSource = Literal["synthetic_curated"]
QueryType = Literal["job_to_candidate"]


class RelevanceLabel(ContractModel):
    label_id: str = Field(pattern=r"^lbl_[a-z0-9_]+$")
    query_type: QueryType
    job_id: str = Field(pattern=r"^job_[a-z0-9_]+$")
    candidate_id: str = Field(pattern=r"^cand_[a-z0-9_]+$")
    relevance_grade: RelevanceGrade
    hard_negative: bool
    mismatch_reasons: List[MismatchCode]
    rationale: str = Field(min_length=20, max_length=800)
    supporting_evidence_ids: List[str]
    affected_requirement_ids: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    annotation_source: AnnotationSource
    split: DatasetSplit
    schema_version: SchemaVersion

    @model_validator(mode="after")
    def label_semantics_are_consistent(self) -> "RelevanceLabel":
        if self.relevance_grade <= RelevanceGrade.WEAK_OR_MISLEADING:
            if not self.mismatch_reasons:
                raise ValueError("grade 0 or 1 requires at least one mismatch reason")
        if self.hard_negative and self.relevance_grade > RelevanceGrade.WEAK_OR_MISLEADING:
            raise ValueError("hard negatives must use relevance grade 0 or 1")
        if len(set(self.supporting_evidence_ids)) != len(
            self.supporting_evidence_ids
        ):
            raise ValueError("supporting_evidence_ids must be unique")
        if len(set(self.affected_requirement_ids)) != len(
            self.affected_requirement_ids
        ):
            raise ValueError("affected_requirement_ids must be unique")
        return self


class PairwisePreference(ContractModel):
    preference_id: str = Field(pattern=r"^pref_[a-z0-9_]+$")
    job_id: str = Field(pattern=r"^job_[a-z0-9_]+$")
    winner_candidate_id: str = Field(pattern=r"^cand_[a-z0-9_]+$")
    loser_candidate_id: str = Field(pattern=r"^cand_[a-z0-9_]+$")
    reason_codes: List[MismatchCode] = Field(min_length=1)
    rationale: str = Field(min_length=20, max_length=800)
    confidence: float = Field(ge=0.0, le=1.0)
    annotation_source: AnnotationSource
    split: DatasetSplit
    schema_version: SchemaVersion

    @model_validator(mode="after")
    def candidates_must_differ(self) -> "PairwisePreference":
        if self.winner_candidate_id == self.loser_candidate_id:
            raise ValueError("winner and loser must differ")
        return self
