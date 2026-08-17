from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.candidates import router as candidates_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.features import router as features_router
from app.api.routes.ranking import router as ranking_router
from app.core.config import get_settings


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(candidates_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(jobs_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(retrieval_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(features_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(ranking_router, prefix=get_settings().api_v1_prefix)
