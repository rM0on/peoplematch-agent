from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import Annotated, Any, List, Literal, Optional, Union

from pydantic import Discriminator, Field, Tag, model_validator

from app.schemas.retrieval import RetrievalFilters
from app.schemas.shared import ContractModel


class RankingVariant(str, Enum):
    LTR = "ltr"
    CROSS_ENCODER_EXPERIMENT = "cross_encoder_experiment"


class MatchRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RunStepStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LtrMatchRunRequest(ContractModel):
    job_id: str = Field(min_length=1, max_length=80)
    ranking_variant: Literal[RankingVariant.LTR] = RankingVariant.LTR
    candidate_pool_k: int = Field(default=20, ge=1, le=50)
    top_k: int = Field(default=10, ge=1, le=50)
    filters: Optional[RetrievalFilters] = None

    @model_validator(mode="after")
    def top_k_must_fit_pool(self) -> "LtrMatchRunRequest":
        if self.top_k > self.candidate_pool_k:
            raise ValueError("top_k must be less than or equal to candidate_pool_k")
        return self


class CrossEncoderMatchRunRequest(ContractModel):
    job_id: str = Field(min_length=1, max_length=80)
    ranking_variant: Literal[RankingVariant.CROSS_ENCODER_EXPERIMENT]
    retrieval_pool_k: int = Field(default=20, ge=1, le=50)
    cross_encoder_pool_k: int = Field(default=10, ge=1, le=50)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: Optional[RetrievalFilters] = None

    @model_validator(mode="after")
    def cascade_order_is_valid(self) -> "CrossEncoderMatchRunRequest":
        if self.cross_encoder_pool_k > self.retrieval_pool_k:
            raise ValueError(
                "cross_encoder_pool_k must be less than or equal to retrieval_pool_k"
            )
        if self.top_k > self.cross_encoder_pool_k:
            raise ValueError("top_k must be less than or equal to cross_encoder_pool_k")
        return self


def _ranking_variant(value: object) -> Optional[str]:
    if isinstance(value, dict):
        return str(value.get("ranking_variant", RankingVariant.LTR.value))
    variant = getattr(value, "ranking_variant", None)
    return variant.value if isinstance(variant, RankingVariant) else variant


MatchRunRequest = Annotated[
    Union[
        Annotated[LtrMatchRunRequest, Tag(RankingVariant.LTR.value)],
        Annotated[
            CrossEncoderMatchRunRequest,
            Tag(RankingVariant.CROSS_ENCODER_EXPERIMENT.value),
        ],
    ],
    Discriminator(_ranking_variant),
]


class MatchResultResponse(ContractModel):
    match_result_id: int = Field(gt=0)
    candidate_id: str
    result_rank: int
    candidate_input_fingerprint: str
    retrieval_rank: int
    matched_channels: List[str]
    dense_rank: Optional[int]
    dense_score: Optional[float]
    sparse_rank: Optional[int]
    sparse_score: Optional[float]
    fusion_score: Optional[float]
    semantic_score: Optional[float]
    skill_fit_score: Optional[float]
    project_evidence_score: Optional[float]
    role_direction_score: Optional[float]
    ai_tool_score: Optional[float]
    location_score: Optional[float]
    seniority_score: Optional[float]
    missing_penalty: Optional[float]
    overclaim_penalty: Optional[float]
    feature_diagnostics_contract_version: str
    feature_diagnostics: dict[str, Any]
    ltr_rank: int
    ltr_score_raw: float
    cross_encoder_rank: Optional[int]
    cross_encoder_score_raw: Optional[float]


class RunStepResponse(ContractModel):
    sequence: int
    step_name: str
    status: RunStepStatus
    started_at: datetime
    finished_at: Optional[datetime]
    duration_ms: Optional[float]
    input_refs: dict[str, Any]
    output_refs: Optional[dict[str, Any]]
    contract_version: str
    error_code: Optional[str]
    error_detail_safe: Optional[str]


class MatchRunSummaryResponse(ContractModel):
    run_id: str
    requested_job_id: str
    job_id: Optional[str]
    request_id: str
    ranking_variant: RankingVariant
    status: MatchRunStatus
    created_at: datetime
    started_at: datetime
    completed_at: Optional[datetime]
    result_count: int
    error_code: Optional[str]


class MatchRunDetailResponse(MatchRunSummaryResponse):
    request_parameters: dict[str, Any]
    workflow_version: str
    workflow_fingerprint: str
    ranking_input_contract_version: str
    ranking_input_fingerprint: Optional[str]
    retrieval_document_version: Optional[str]
    retrieval_configuration_fingerprint: Optional[str]
    retrieval_provenance: Optional[dict[str, Any]]
    feature_version: Optional[str]
    feature_fingerprint: Optional[str]
    ranker_version: Optional[str]
    ranker_model_sha256: Optional[str]
    ce_provenance: Optional[dict[str, Any]]
    result_fingerprint: Optional[str]
    error_detail_safe: Optional[str]
    results: List[MatchResultResponse]
    steps: List[RunStepResponse]


def match_run_summary_from_model(model: Any) -> MatchRunSummaryResponse:
    return MatchRunSummaryResponse(
        run_id=model.run_id,
        requested_job_id=model.requested_job_id,
        job_id=model.job_id,
        request_id=model.request_id,
        ranking_variant=model.ranking_variant,
        status=model.status,
        created_at=model.created_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
        result_count=model.result_count,
        error_code=model.error_code,
    )


def match_run_detail_from_model(model: Any) -> MatchRunDetailResponse:
    summary = match_run_summary_from_model(model).model_dump()
    return MatchRunDetailResponse(
        **summary,
        request_parameters=model.request_parameters,
        workflow_version=model.workflow_version,
        workflow_fingerprint=model.workflow_fingerprint,
        ranking_input_contract_version=model.ranking_input_contract_version,
        ranking_input_fingerprint=model.ranking_input_fingerprint,
        retrieval_document_version=model.retrieval_document_version,
        retrieval_configuration_fingerprint=model.retrieval_configuration_fingerprint,
        retrieval_provenance=model.retrieval_provenance,
        feature_version=model.feature_version,
        feature_fingerprint=model.feature_fingerprint,
        ranker_version=model.ranker_version,
        ranker_model_sha256=model.ranker_model_sha256,
        ce_provenance=model.ce_provenance,
        result_fingerprint=model.result_fingerprint,
        error_detail_safe=model.error_detail_safe,
        results=[
            MatchResultResponse(
                match_result_id=result.id,
                **{
                    field: getattr(result, field)
                    for field in MatchResultResponse.model_fields
                    if field != "match_result_id"
                }
            )
            for result in model.results
        ],
        steps=[
            RunStepResponse(
                **{field: getattr(step, field) for field in RunStepResponse.model_fields}
            )
            for step in model.steps
        ],
    )
