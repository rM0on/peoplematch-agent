from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.dependencies import get_job_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.mutations import JobCreate, JobPatch
from app.schemas.persistence import JobRecord
from app.services.job_service import JobService


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=ApiResponse[PaginatedData[JobRecord]])
async def list_jobs(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    role_title: Optional[str] = None,
    role_direction: Optional[str] = None,
    city: Optional[str] = None,
    seniority: Optional[str] = None,
    service: JobService = Depends(get_job_service),
) -> ApiResponse[PaginatedData[JobRecord]]:
    items, total = await service.list(
        limit=limit,
        offset=offset,
        role_title=role_title,
        role_direction=role_direction,
        city=city,
        seniority=seniority,
    )
    return ApiResponse(
        success=True,
        data=PaginatedData(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        ),
        error=None,
        request_id=get_request_id(request),
    )


@router.get("/{job_id}", response_model=ApiResponse[JobRecord])
async def get_job(
    job_id: str,
    request: Request,
    service: JobService = Depends(get_job_service),
) -> ApiResponse[JobRecord]:
    return ApiResponse(
        success=True,
        data=await service.get(job_id),
        error=None,
        request_id=get_request_id(request),
    )


@router.post("", response_model=ApiResponse[JobRecord], status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    request: Request,
    service: JobService = Depends(get_job_service),
) -> ApiResponse[JobRecord]:
    return ApiResponse(
        success=True,
        data=await service.create(payload),
        error=None,
        request_id=get_request_id(request),
    )


@router.patch("/{job_id}", response_model=ApiResponse[JobRecord])
async def patch_job(
    job_id: str,
    payload: JobPatch,
    request: Request,
    service: JobService = Depends(get_job_service),
) -> ApiResponse[JobRecord]:
    return ApiResponse(
        success=True,
        data=await service.patch(job_id, payload),
        error=None,
        request_id=get_request_id(request),
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    service: JobService = Depends(get_job_service),
) -> Response:
    await service.delete(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
