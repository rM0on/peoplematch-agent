from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request, status

from app.api.dependencies import get_explanation_generation_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.explanation_generation import (
    ExplanationGenerationRequest,
    ExplanationRunDetailResponse,
    ExplanationRunSummaryResponse,
)


router = APIRouter(tags=["explanations"])


@router.post(
    "/match-runs/{match_run_id}/explanations",
    response_model=ApiResponse[ExplanationRunDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_explanations(
    match_run_id: str,
    request: Request,
    payload: ExplanationGenerationRequest = Body(...),
    service=Depends(get_explanation_generation_service),
) -> ApiResponse[ExplanationRunDetailResponse]:
    result = await service.generate(
        match_run_id,
        requested_top_k=payload.top_k,
        request_id=get_request_id(request),
    )
    persisted = await service.get(result.explanation_run_id)
    return ApiResponse(
        success=True,
        data=persisted,
        error=None,
        request_id=get_request_id(request),
    )


@router.get(
    "/explanation-runs/{explanation_run_id}",
    response_model=ApiResponse[ExplanationRunDetailResponse],
)
async def get_explanation_run(
    explanation_run_id: str,
    request: Request,
    service=Depends(get_explanation_generation_service),
) -> ApiResponse[ExplanationRunDetailResponse]:
    return ApiResponse(
        success=True,
        data=await service.get(explanation_run_id),
        error=None,
        request_id=get_request_id(request),
    )


@router.get(
    "/match-runs/{match_run_id}/explanation-runs",
    response_model=ApiResponse[PaginatedData[ExplanationRunSummaryResponse]],
)
async def list_explanation_runs(
    match_run_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service=Depends(get_explanation_generation_service),
) -> ApiResponse[PaginatedData[ExplanationRunSummaryResponse]]:
    items, total = await service.list(
        match_run_id,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        success=True,
        data=PaginatedData(items=items, total=total, limit=limit, offset=offset),
        error=None,
        request_id=get_request_id(request),
    )


__all__ = ["router"]
