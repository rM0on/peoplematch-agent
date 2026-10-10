from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import get_recruiter_narrative_query_service, get_recruiter_narrative_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.recruiter_narrative import RecruiterNarrativeResponse, narrative_response_from_model


router = APIRouter(tags=["recruiter-narratives"])


@router.post(
    "/match-explanations/{match_explanation_id}/recruiter-narratives",
    response_model=ApiResponse[RecruiterNarrativeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_recruiter_narrative(
    match_explanation_id: int,
    request: Request,
    service=Depends(get_recruiter_narrative_service),
) -> ApiResponse[RecruiterNarrativeResponse]:
    result = await service.generate(match_explanation_id)
    return ApiResponse(
        success=True,
        data=narrative_response_from_model(result),
        error=None,
        request_id=get_request_id(request),
    )


@router.get(
    "/recruiter-narratives/{narrative_id}",
    response_model=ApiResponse[RecruiterNarrativeResponse],
)
async def get_recruiter_narrative(
    narrative_id: str,
    request: Request,
    service=Depends(get_recruiter_narrative_query_service),
) -> ApiResponse[RecruiterNarrativeResponse]:
    record = await service.get(narrative_id)
    return ApiResponse(
        success=True,
        data=narrative_response_from_model(record),
        error=None,
        request_id=get_request_id(request),
    )


__all__ = ["router"]
