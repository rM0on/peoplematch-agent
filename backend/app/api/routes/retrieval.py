from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_retrieval_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.retrieval import RetrievalRequest, RetrievalResponseData
from app.services.retrieval.service import RetrievalService


router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post(
    "/jobs/{job_id}/candidates",
    response_model=ApiResponse[RetrievalResponseData],
)
async def retrieve_candidates_for_job(
    job_id: str,
    payload: RetrievalRequest,
    request: Request,
    service: RetrievalService = Depends(get_retrieval_service),
) -> ApiResponse[RetrievalResponseData]:
    request_id = get_request_id(request)
    data = await service.retrieve_candidates(job_id, payload)
    return ApiResponse(success=True, data=data, error=None, request_id=request_id)


@router.post(
    "/candidates/{candidate_id}/jobs",
    response_model=ApiResponse[RetrievalResponseData],
)
async def retrieve_jobs_for_candidate(
    candidate_id: str,
    payload: RetrievalRequest,
    request: Request,
    service: RetrievalService = Depends(get_retrieval_service),
) -> ApiResponse[RetrievalResponseData]:
    request_id = get_request_id(request)
    data = await service.retrieve_jobs(candidate_id, payload)
    return ApiResponse(success=True, data=data, error=None, request_id=request_id)
