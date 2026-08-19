from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, Request, status

from app.api.dependencies import get_match_run_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.match_runs import (
    MatchRunDetailResponse,
    MatchRunRequest,
    MatchRunStatus,
    MatchRunSummaryResponse,
    RankingVariant,
    match_run_detail_from_model,
    match_run_summary_from_model,
)
from app.services.match_runs.service import MatchRunService


router = APIRouter(prefix="/match-runs", tags=["match-runs"])


@router.post(
    "",
    response_model=ApiResponse[MatchRunDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_match_run(
    request: Request,
    payload: MatchRunRequest = Body(...),
    service: MatchRunService = Depends(get_match_run_service),
) -> ApiResponse[MatchRunDetailResponse]:
    request_id = get_request_id(request)
    run = await service.execute(payload, request_id=request_id)
    return ApiResponse(
        success=True,
        data=match_run_detail_from_model(run),
        error=None,
        request_id=request_id,
    )


@router.get("", response_model=ApiResponse[PaginatedData[MatchRunSummaryResponse]])
async def list_match_runs(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    job_id: Optional[str] = None,
    status_filter: Optional[MatchRunStatus] = Query(None, alias="status"),
    ranking_variant: Optional[RankingVariant] = None,
    service: MatchRunService = Depends(get_match_run_service),
) -> ApiResponse[PaginatedData[MatchRunSummaryResponse]]:
    items, total = await service.list(
        limit=limit,
        offset=offset,
        job_id=job_id,
        status=status_filter.value if status_filter else None,
        ranking_variant=ranking_variant.value if ranking_variant else None,
    )
    return ApiResponse(
        success=True,
        data=PaginatedData(
            items=[match_run_summary_from_model(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        ),
        error=None,
        request_id=get_request_id(request),
    )


@router.get("/{run_id}", response_model=ApiResponse[MatchRunDetailResponse])
async def get_match_run(
    run_id: str,
    request: Request,
    service: MatchRunService = Depends(get_match_run_service),
) -> ApiResponse[MatchRunDetailResponse]:
    run = await service.get(run_id)
    return ApiResponse(
        success=True,
        data=match_run_detail_from_model(run),
        error=None,
        request_id=get_request_id(request),
    )
