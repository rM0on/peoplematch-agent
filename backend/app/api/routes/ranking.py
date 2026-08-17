from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_ranking_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.ranking import RankingRequest, RankingResponseData
from app.services.ranking.service import RankingService


router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.post(
    "/jobs/{job_id}/candidates",
    response_model=ApiResponse[RankingResponseData],
)
async def rank_candidates_for_job(
    job_id: str,
    payload: RankingRequest,
    request: Request,
    service: RankingService = Depends(get_ranking_service),
) -> ApiResponse[RankingResponseData]:
    data = await service.rank_job_candidates(job_id, payload)
    return ApiResponse(
        success=True,
        data=data,
        error=None,
        request_id=get_request_id(request),
    )
