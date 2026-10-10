"""Read-only, source-backed recruiter propositions; no free-text generation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_recruiter_proposition_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.recruiter_proposition import StructuredRecruiterBriefV1


router = APIRouter(tags=["recruiter-propositions"])


@router.get(
    "/match-explanations/{match_explanation_id}/recruiter-propositions",
    response_model=ApiResponse[StructuredRecruiterBriefV1],
)
async def get_recruiter_propositions(
    match_explanation_id: int,
    request: Request,
    service=Depends(get_recruiter_proposition_service),
) -> ApiResponse[StructuredRecruiterBriefV1]:
    return ApiResponse(
        success=True,
        data=await service.get(match_explanation_id),
        error=None,
        request_id=get_request_id(request),
    )


__all__ = ["router"]
