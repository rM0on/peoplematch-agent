from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from app.schemas.retrieval import RetrievalFilters
from app.schemas.features import FeatureDiagnostics, FeatureVector
from app.schemas.retrieval import RetrievalDiagnostics, RetrievalResult
from app.schemas.shared import ContractModel


class RankingRequest(ContractModel):
    candidate_pool_k: int = Field(default=20, ge=1, le=50)
    top_k: int = Field(default=10, ge=1, le=50)
    filters: Optional[RetrievalFilters] = None

    @model_validator(mode="after")
    def top_k_must_fit_pool(self) -> "RankingRequest":
        if self.top_k > self.candidate_pool_k:
            raise ValueError("top_k must be less than or equal to candidate_pool_k")
        return self


class RankingResult(ContractModel):
    entity_id: str
    ltr_rank: int = Field(ge=1)
    ltr_score_raw: float
    retrieval: RetrievalResult
    feature_vector: FeatureVector
    feature_diagnostics: FeatureDiagnostics


class RankingResponseData(ContractModel):
    ranker_version: str
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    feature_version: str
    feature_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_pool_k: int = Field(ge=1, le=50)
    results: list[RankingResult]
    retrieval_diagnostics: RetrievalDiagnostics
