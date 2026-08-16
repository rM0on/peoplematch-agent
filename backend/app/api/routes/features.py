from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_feature_engineering_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.features import FeatureResponseData
from app.schemas.retrieval import RetrievalRequest
from app.services.features.service import FeatureEngineeringService


router = APIRouter(prefix="/features", tags=["features"])


@router.post(
    "/jobs/{job_id}/candidates",
    response_model=ApiResponse[FeatureResponseData],
)
async def features_for_job_candidates(
    job_id: str,
    payload: RetrievalRequest,
    request: Request,
    service: FeatureEngineeringService = Depends(get_feature_engineering_service),
) -> ApiResponse[FeatureResponseData]:
    data = await service.features_for_job_candidates(job_id, payload)
    return ApiResponse(
        success=True,
        data=data,
        error=None,
        request_id=get_request_id(request),
    )


@router.post(
    "/candidates/{candidate_id}/jobs",
    response_model=ApiResponse[FeatureResponseData],
)
async def features_for_candidate_jobs(
    candidate_id: str,
    payload: RetrievalRequest,
    request: Request,
    service: FeatureEngineeringService = Depends(get_feature_engineering_service),
) -> ApiResponse[FeatureResponseData]:
    data = await service.features_for_candidate_jobs(candidate_id, payload)
    return ApiResponse(
        success=True,
        data=data,
        error=None,
        request_id=get_request_id(request),
    )
