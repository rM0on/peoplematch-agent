from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies import get_bad_case_review_service, get_feedback_service
from app.middleware.request_id import get_request_id
from app.schemas.bad_cases import BadCaseSummaryResponse
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.feedback import FeedbackCreateRequest, FeedbackRecordV1
from app.schemas.phase10 import (
    BadCaseApiDetailResponse,
    BadCaseCreateCommand,
    BadCaseLinkSourceRequest,
    BadCaseReviewCommand,
)


router = APIRouter(tags=["feedback-review"])
_DOMAIN_RESPONSES = {
    404: {"description": "Historical review target not found"},
    409: {"description": "Review conflict or stale revision"},
    422: {"description": "Invalid review request or historical ownership"},
}


@router.post(
    "/feedback",
    response_model=ApiResponse[FeedbackRecordV1],
    status_code=status.HTTP_201_CREATED,
    responses=_DOMAIN_RESPONSES,
)
async def create_feedback(
    request: Request,
    payload: FeedbackCreateRequest,
    service=Depends(get_feedback_service),
) -> ApiResponse[FeedbackRecordV1]:
    return ApiResponse(
        success=True,
        data=await service.create(payload),
        error=None,
        request_id=get_request_id(request),
    )


@router.get(
    "/feedback/{feedback_id}",
    response_model=ApiResponse[FeedbackRecordV1],
    responses=_DOMAIN_RESPONSES,
)
async def get_feedback(
    feedback_id: str,
    request: Request,
    service=Depends(get_feedback_service),
) -> ApiResponse[FeedbackRecordV1]:
    return ApiResponse(
        success=True,
        data=await service.get(feedback_id),
        error=None,
        request_id=get_request_id(request),
    )


@router.post(
    "/bad-cases",
    response_model=ApiResponse[BadCaseApiDetailResponse],
    status_code=status.HTTP_201_CREATED,
    responses=_DOMAIN_RESPONSES,
)
async def create_bad_case(
    request: Request,
    payload: BadCaseCreateCommand,
    service=Depends(get_bad_case_review_service),
) -> ApiResponse[BadCaseApiDetailResponse]:
    return ApiResponse(
        success=True,
        data=await service.create_detail(payload.to_create_request()),
        error=None,
        request_id=get_request_id(request),
    )


@router.get(
    "/bad-cases",
    response_model=ApiResponse[PaginatedData[BadCaseSummaryResponse]],
    responses=_DOMAIN_RESPONSES,
)
async def list_bad_cases(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service=Depends(get_bad_case_review_service),
) -> ApiResponse[PaginatedData[BadCaseSummaryResponse]]:
    items, total = await service.list_summaries(limit=limit, offset=offset)
    return ApiResponse(
        success=True,
        data=PaginatedData(items=items, total=total, limit=limit, offset=offset),
        error=None,
        request_id=get_request_id(request),
    )


@router.get(
    "/bad-cases/{bad_case_id}",
    response_model=ApiResponse[BadCaseApiDetailResponse],
    responses=_DOMAIN_RESPONSES,
)
async def get_bad_case(
    bad_case_id: str,
    request: Request,
    child_limit: int = Query(100, ge=1, le=100),
    service=Depends(get_bad_case_review_service),
) -> ApiResponse[BadCaseApiDetailResponse]:
    return ApiResponse(
        success=True,
        data=await service.get_detail(bad_case_id, child_limit=child_limit),
        error=None,
        request_id=get_request_id(request),
    )


@router.post(
    "/bad-cases/{bad_case_id}/sources",
    response_model=ApiResponse[BadCaseApiDetailResponse],
    responses=_DOMAIN_RESPONSES,
)
async def link_bad_case_source(
    bad_case_id: str,
    request: Request,
    payload: BadCaseLinkSourceRequest,
    service=Depends(get_bad_case_review_service),
) -> ApiResponse[BadCaseApiDetailResponse]:
    return ApiResponse(
        success=True,
        data=await service.link_source_detail(bad_case_id, payload),
        error=None,
        request_id=get_request_id(request),
    )


@router.post(
    "/bad-cases/{bad_case_id}/review",
    response_model=ApiResponse[BadCaseApiDetailResponse],
    responses=_DOMAIN_RESPONSES,
)
async def review_bad_case(
    bad_case_id: str,
    request: Request,
    payload: BadCaseReviewCommand,
    service=Depends(get_bad_case_review_service),
) -> ApiResponse[BadCaseApiDetailResponse]:
    return ApiResponse(
        success=True,
        data=await service.review_detail(bad_case_id, payload.to_update_request()),
        error=None,
        request_id=get_request_id(request),
    )


__all__ = ["router"]
