from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Depends, Request

from app.api.dependencies import get_demo_index_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.demo import (
    DemoIndexRebuildData,
    DemoIndexRebuildRequest,
    DemoSamplesData,
)
from app.services.demo.indexes import DemoIndexService


router = APIRouter(prefix="/demo", tags=["demo"])
_FIXTURE_ROOT = Path(__file__).resolve().parents[4] / "data" / "samples" / "extraction"


@router.get("/samples", response_model=ApiResponse[DemoSamplesData])
async def get_demo_samples(request: Request) -> ApiResponse[DemoSamplesData]:
    data = DemoSamplesData(
        candidate_text=(_FIXTURE_ROOT / "candidate_phase13_zh_resume.txt").read_text(
            encoding="utf-8"
        ),
        job_text=(_FIXTURE_ROOT / "job_phase13_zh.txt").read_text(
            encoding="utf-8"
        ),
    )
    return ApiResponse(
        success=True,
        data=data,
        error=None,
        request_id=get_request_id(request),
    )


@router.post(
    "/rebuild-retrieval-index",
    response_model=ApiResponse[DemoIndexRebuildData],
)
async def rebuild_demo_retrieval_index(
    request: Request,
    _payload: DemoIndexRebuildRequest = Body(...),
    service: DemoIndexService = Depends(get_demo_index_service),
) -> ApiResponse[DemoIndexRebuildData]:
    return ApiResponse(
        success=True,
        data=await service.rebuild(),
        error=None,
        request_id=get_request_id(request),
    )


__all__ = ["router"]
