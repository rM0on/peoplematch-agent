from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_cross_encoder_reranking_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.cross_encoder import (
    CrossEncoderRerankingRequest,
    CrossEncoderRerankingResponseData,
)
from app.services.cross_encoder.service import CrossEncoderRerankingService


router = APIRouter(prefix="/reranking", tags=["reranking"])


@router.post(
    "/jobs/{job_id}/candidates",
    response_model=ApiResponse[CrossEncoderRerankingResponseData],
)
async def rerank_candidates_for_job(
    job_id: str,
    payload: CrossEncoderRerankingRequest,
    request: Request,
    service: CrossEncoderRerankingService = Depends(
        get_cross_encoder_reranking_service
    ),
) -> ApiResponse[CrossEncoderRerankingResponseData]:
    data = await service.rerank_job_candidates(job_id, payload)
    return ApiResponse(
        success=True,
        data=data,
        error=None,
        request_id=get_request_id(request),
    )
