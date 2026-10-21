"""Read-only recruiter requirement inspection over persisted source."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_requirement_review_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.requirement_review import RequirementReviewV1


router = APIRouter(tags=["requirement-reviews"])


@router.get(
    "/match-explanations/{match_explanation_id}/requirement-review",
    response_model=ApiResponse[RequirementReviewV1],
)
async def get_requirement_review(
    match_explanation_id: int,
    request: Request,
    service=Depends(get_requirement_review_service),
) -> ApiResponse[RequirementReviewV1]:
    return ApiResponse(
        success=True,
        data=await service.get(match_explanation_id),
        error=None,
        request_id=get_request_id(request),
    )


__all__ = ["router"]
