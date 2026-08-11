from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiResponse


router = APIRouter(tags=["system"])


class HealthData(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


@router.get("/health", response_model=ApiResponse[HealthData])
async def health(
    request: Request,
) -> ApiResponse[HealthData]:
    settings: Settings = get_settings()
    return ApiResponse[HealthData](
        success=True,
        data=HealthData(
            status="ok",
            service="peoplematch-backend",
            version=settings.app_version,
            environment=settings.app_env,
        ),
        error=None,
        request_id=get_request_id(request),
    )
