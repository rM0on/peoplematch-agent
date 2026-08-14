from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import Field

from app.schemas.shared import ContractModel, Seniority


class RetrievalEntityType(str, Enum):
    CANDIDATE = "candidate"
    JOB = "job"


class RetrievalStrategy(str, Enum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


class RetrievalFilters(ContractModel):
    cities: Optional[List[str]] = None
    seniorities: Optional[List[Seniority]] = None


class RetrievalRequest(ContractModel):
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    top_k: int = Field(default=10, ge=1, le=50)
    filters: Optional[RetrievalFilters] = None


class RetrievalDocument(ContractModel):
    entity_id: str
    entity_type: RetrievalEntityType
    document_version: str
    document_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    text: str = Field(min_length=1)
    cities: List[str]
    seniorities: List[Seniority]


class CandidateRetrievalDocument(RetrievalDocument):
    entity_type: RetrievalEntityType = RetrievalEntityType.CANDIDATE


class JobRetrievalDocument(RetrievalDocument):
    entity_type: RetrievalEntityType = RetrievalEntityType.JOB


class ChannelResult(ContractModel):
    entity_id: str
    rank: int = Field(ge=1)
    score: float


class FusedResult(ContractModel):
    entity_id: str
    fusion_score: float
    dense_rank: Optional[int] = None
    dense_score: Optional[float] = None
    sparse_rank: Optional[int] = None
    sparse_score: Optional[float] = None


class RetrievalResult(ContractModel):
    entity_id: str
    rank: int = Field(ge=1)
    matched_channels: List[str]
    dense_rank: Optional[int] = None
    dense_score: Optional[float] = None
    sparse_rank: Optional[int] = None
    sparse_score: Optional[float] = None
    fusion_score: Optional[float] = None


class RetrievalDiagnostics(ContractModel):
    query_type: RetrievalEntityType
    query_id: str
    result_type: RetrievalEntityType
    strategy: RetrievalStrategy
    top_k_requested: int
    returned_count: int
    corpus_size: int
    eligible_count: int
    dense_pool_size: int
    sparse_pool_size: int
    embedding_provider: str
    embedding_model: str
    document_version: str
    rrf_k: int
    filters_applied: bool
    index_freshness: str
    dense_ms: float
    sparse_ms: float
    fusion_ms: float
    total_ms: float


class RetrievalResponseData(ContractModel):
    results: List[RetrievalResult]
    diagnostics: RetrievalDiagnostics
