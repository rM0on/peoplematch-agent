from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.candidates import router as candidates_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.features import router as features_router
from app.api.routes.ranking import router as ranking_router
from app.api.routes.cross_encoder import router as cross_encoder_router
from app.api.routes.match_runs import router as match_runs_router
from app.api.routes.explanations import router as explanations_router
from app.api.routes.phase10 import router as phase10_router
from app.api.routes.demo import router as demo_router
from app.api.routes.provider_status import router as provider_status_router
from app.api.routes.recruiter_narratives import router as recruiter_narratives_router
from app.api.routes.recruiter_narratives_v2 import router as recruiter_narratives_v2_router
from app.api.routes.recruiter_narratives_v2_1 import router as recruiter_narratives_v2_1_router
from app.api.routes.recruiter_propositions import router as recruiter_propositions_router
from app.core.config import get_settings


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(candidates_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(jobs_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(retrieval_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(features_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(ranking_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(cross_encoder_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(match_runs_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(explanations_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(phase10_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(demo_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(provider_status_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(recruiter_narratives_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(recruiter_narratives_v2_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(recruiter_narratives_v2_1_router, prefix=get_settings().api_v1_prefix)
api_router.include_router(recruiter_propositions_router, prefix=get_settings().api_v1_prefix)
