from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import get_recruiter_narrative_v2_1_query_service, get_recruiter_narrative_v2_1_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.recruiter_narrative_v2_1 import RecruiterNarrativeV2_1Response, narrative_v2_1_response_from_model


router = APIRouter(tags=["recruiter-narratives-v2-1"])


@router.post(
    "/match-explanations/{match_explanation_id}/recruiter-narratives-v2-1",
    response_model=ApiResponse[RecruiterNarrativeV2_1Response],
    status_code=status.HTTP_201_CREATED,
)
async def generate_recruiter_narrative_v2_1(
    match_explanation_id: int, request: Request,
    service=Depends(get_recruiter_narrative_v2_1_service),
) -> ApiResponse[RecruiterNarrativeV2_1Response]:
    result = await service.generate(match_explanation_id)
    return ApiResponse(success=True, data=narrative_v2_1_response_from_model(result),
                       error=None, request_id=get_request_id(request))


@router.get(
    "/recruiter-narratives-v2-1/{narrative_id}",
    response_model=ApiResponse[RecruiterNarrativeV2_1Response],
)
async def get_recruiter_narrative_v2_1(
    narrative_id: str, request: Request,
    service=Depends(get_recruiter_narrative_v2_1_query_service),
) -> ApiResponse[RecruiterNarrativeV2_1Response]:
    result = await service.get(narrative_id)
    return ApiResponse(success=True, data=narrative_v2_1_response_from_model(result),
                       error=None, request_id=get_request_id(request))


__all__ = ["router"]
