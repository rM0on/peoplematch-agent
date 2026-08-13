from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.dependencies import get_candidate_service, get_profile_extraction_service
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.mutations import CandidateCreate, CandidatePatch
from app.schemas.persistence import CandidateRecord
from app.services.candidate_service import CandidateService
from app.schemas.extraction import CandidateParseData, CandidateParseRequest
from app.services.profile_extraction.parser import ProfileExtractionService


router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/parse", response_model=ApiResponse[CandidateParseData])
async def parse_candidate(
    payload: CandidateParseRequest,
    request: Request,
    service: ProfileExtractionService = Depends(get_profile_extraction_service),
) -> ApiResponse[CandidateParseData]:
    request_id = get_request_id(request)
    return ApiResponse(
        success=True,
        data=await service.parse_candidate(
            payload.text,
            persist=payload.persist,
            request_id=request_id,
        ),
        error=None,
        request_id=request_id,
    )


@router.get("", response_model=ApiResponse[PaginatedData[CandidateRecord]])
async def list_candidates(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    seniority: Optional[str] = None,
    city: Optional[str] = None,
    target_role: Optional[str] = None,
    service: CandidateService = Depends(get_candidate_service),
) -> ApiResponse[PaginatedData[CandidateRecord]]:
    items, total = await service.list(
        limit=limit,
        offset=offset,
        seniority=seniority,
        city=city,
        target_role=target_role,
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


@router.get("/{candidate_id}", response_model=ApiResponse[CandidateRecord])
async def get_candidate(
    candidate_id: str,
    request: Request,
    service: CandidateService = Depends(get_candidate_service),
) -> ApiResponse[CandidateRecord]:
    return ApiResponse(
        success=True,
        data=await service.get(candidate_id),
        error=None,
        request_id=get_request_id(request),
    )


@router.post("", response_model=ApiResponse[CandidateRecord], status_code=status.HTTP_201_CREATED)
async def create_candidate(
    payload: CandidateCreate,
    request: Request,
    service: CandidateService = Depends(get_candidate_service),
) -> ApiResponse[CandidateRecord]:
    return ApiResponse(
        success=True,
        data=await service.create(payload),
        error=None,
        request_id=get_request_id(request),
    )


@router.patch("/{candidate_id}", response_model=ApiResponse[CandidateRecord])
async def patch_candidate(
    candidate_id: str,
    payload: CandidatePatch,
    request: Request,
    service: CandidateService = Depends(get_candidate_service),
) -> ApiResponse[CandidateRecord]:
    return ApiResponse(
        success=True,
        data=await service.patch(candidate_id, payload),
        error=None,
        request_id=get_request_id(request),
    )


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: str,
    service: CandidateService = Depends(get_candidate_service),
) -> Response:
    await service.delete(candidate_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
