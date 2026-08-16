from __future__ import annotations

from typing import List, Optional

from app.schemas.retrieval import RetrievalDiagnostics, RetrievalResult
from pydantic import Field

from app.schemas.shared import ContractModel


class FeatureVector(ContractModel):
    semantic_score: Optional[float] = Field(ge=-1, le=1)
    sparse_score: Optional[float] = Field(ge=0)
    skill_fit_score: Optional[float] = Field(ge=0, le=1)
    project_evidence_score: Optional[float] = Field(ge=0, le=1)
    role_direction_score: Optional[float] = Field(ge=0, le=1)
    ai_tool_score: Optional[float] = Field(ge=0, le=1)
    location_score: Optional[float] = Field(ge=0, le=1)
    seniority_score: Optional[float] = Field(ge=0, le=1)
    missing_penalty: Optional[float] = Field(ge=0, le=1)
    overclaim_penalty: Optional[float] = Field(ge=0, le=1)


class FeatureAvailability(ContractModel):
    semantic_score: bool
    sparse_score: bool
    skill_fit_score: bool
    project_evidence_score: bool
    role_direction_score: bool
    ai_tool_score: bool
    location_score: bool
    seniority_score: bool
    missing_penalty: bool
    overclaim_penalty: bool


class FeatureDiagnostics(ContractModel):
    availability: FeatureAvailability
    matched_must_have_requirement_ids: List[str]
    weak_matched_must_have_requirement_ids: List[str]
    missing_must_have_requirement_ids: List[str]
    matched_nice_to_have_requirement_ids: List[str]
    evidence_supported_requirement_ids: List[str]
    matched_capabilities: List[str]
    matched_evidence_skills: List[str]
    matched_ai_tools: List[str]
    location_relation: str
    seniority_relation: str
    overclaim_level: Optional[str]
    overclaim_reason_count: int
    retrieval_rank: Optional[int]
    dense_rank: Optional[int]
    sparse_rank: Optional[int]
    fusion_score: Optional[float]


class PairFeatureExtraction(ContractModel):
    vector: FeatureVector
    diagnostics: FeatureDiagnostics


class FeatureResult(ContractModel):
    entity_id: str
    retrieval: RetrievalResult
    feature_vector: FeatureVector
    feature_diagnostics: FeatureDiagnostics


class FeatureResponseData(ContractModel):
    feature_version: str
    feature_fingerprint: str
    results: List[FeatureResult]
    retrieval_diagnostics: RetrievalDiagnostics
