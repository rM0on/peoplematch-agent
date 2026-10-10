from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.middleware.request_id import RequestIdMiddleware
from app.api.dependencies import (
    close_runtime_explanation_provider,
    close_runtime_extraction_provider,
    close_runtime_recruiter_narrative_provider,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger = get_logger("lifecycle")
    logger.info(
        "Application starting",
        extra={"environment": settings.app_env, "version": settings.app_version},
    )
    try:
        yield
    finally:
        await close_runtime_extraction_provider()
        await close_runtime_explanation_provider()
        await close_runtime_recruiter_narrative_provider()
        logger.info("Application stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_env)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Phase 5 frozen canonical profile, deterministic extraction, first-stage "
            "hybrid retrieval, and label-free feature inspection plus the Phase 6 "
            "deterministic LambdaMART ranking API and the Phase 7 frozen local "
            "Cross-Encoder reranking endpoint for Job-to-Candidates plus Phase 8 "
            "durable MatchRun orchestration and historical trace APIs, plus the "
            "Phase 9 backend explanation planning, grounding, rendering, and history "
            "APIs. The ranker is "
            "trained only on explicit synthetic Train/Dev judgments, while the "
            "Cross-Encoder uses an immutable pretrained snapshot and raw logits. "
            "Provider output cannot author factual prose or alter ranking. No "
            "fine-tuning, Test evaluation, calibrated probability, explanation "
            "frontend, or final production match score is implemented."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
