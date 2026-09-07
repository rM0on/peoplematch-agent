from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.config import Settings, get_settings
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse
from app.schemas.provider_status import AIProviderStatusData
from app.services.llm.status import project_ai_provider_status


router = APIRouter(prefix="/system", tags=["system"])


@router.get(
    "/ai-provider-status",
    response_model=ApiResponse[AIProviderStatusData],
)
async def ai_provider_status(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResponse[AIProviderStatusData]:
    return ApiResponse[AIProviderStatusData](
        success=True,
        data=project_ai_provider_status(settings),
        error=None,
        request_id=get_request_id(request),
    )
