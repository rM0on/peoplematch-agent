from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from app.schemas.retrieval import RetrievalFilters
from app.schemas.shared import ContractModel


class CrossEncoderRerankingRequest(ContractModel):
    retrieval_pool_k: int = Field(default=20, ge=1, le=50)
    cross_encoder_pool_k: int = Field(default=10, ge=1, le=50)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: Optional[RetrievalFilters] = None

    @model_validator(mode="after")
    def cascade_order_is_valid(self) -> "CrossEncoderRerankingRequest":
        if self.cross_encoder_pool_k > self.retrieval_pool_k:
            raise ValueError(
                "cross_encoder_pool_k must be less than or equal to retrieval_pool_k"
            )
        if self.top_k > self.cross_encoder_pool_k:
            raise ValueError(
                "top_k must be less than or equal to cross_encoder_pool_k"
            )
        return self


class CrossEncoderRerankingResult(ContractModel):
    entity_id: str
    retrieval_rank: int = Field(ge=1)
    ltr_rank: int = Field(ge=1)
    ltr_score_raw: float
    cross_encoder_rank: int = Field(ge=1)
    cross_encoder_score_raw: float
    ranker_version: str
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    feature_version: str
    feature_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class CrossEncoderRerankingResponseData(ContractModel):
    reranker_version: str
    model_id: str
    model_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    snapshot_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    text_schema_version: str
    text_contract_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    pair_order: str
    retrieval_pool_k: int = Field(ge=1, le=50)
    cross_encoder_pool_k: int = Field(ge=1, le=50)
    top_k: int = Field(ge=1, le=50)
    results: list[CrossEncoderRerankingResult]
