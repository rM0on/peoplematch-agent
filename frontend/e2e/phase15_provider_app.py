"""Test-only FastAPI entrypoint using real adapters over httpx.MockTransport."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import (  # noqa: E402
    get_explanation_generation_service,
    get_profile_extraction_service,
)
from app.core.config import get_settings  # noqa: E402
from app.core.database import get_db_session, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories.candidate_repository import CandidateRepository  # noqa: E402
from app.repositories.explanation_attempt_repository import ExplanationAttemptRepository  # noqa: E402
from app.repositories.explanation_query_repository import ExplanationQueryRepository  # noqa: E402
from app.repositories.explanation_run_repository import ExplanationRunRepository  # noqa: E402
from app.repositories.job_repository import JobRepository  # noqa: E402
from app.repositories.match_run_repository import MatchRunRepository  # noqa: E402
from app.schemas.persistence import DataOrigin  # noqa: E402
from app.services.candidate_service import CandidateService  # noqa: E402
from app.services.explanation.generation.mock_provider import DeterministicExplanationProvider  # noqa: E402
from app.services.explanation.generation.openai_compatible import OpenAICompatibleChatProvider  # noqa: E402
from app.services.explanation.generation.orchestration import ExplanationGenerationService  # noqa: E402
from app.services.explanation.generation.pipeline import ExplanationGenerationPipeline  # noqa: E402
from app.services.explanation.generation.provider import (  # noqa: E402
    ExplanationProviderDescriptor,
    ExplanationProviderRequest,
)
from app.services.job_service import JobService  # noqa: E402
from app.services.profile_extraction.openai_compatible import OpenAICompatibleStructuredOutputProvider  # noqa: E402
from app.services.profile_extraction.parser import ProfileExtractionService  # noqa: E402
from app.services.profile_extraction.provider import ProviderDescriptor  # noqa: E402


PRIVATE_KEY = "phase15-private-test-key"
JOB_OUTPUT = (REPOSITORY_ROOT / "data" / "samples" / "extraction" / "job_phase13_zh_output.json").read_text(encoding="utf-8")


async def _handler(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    messages = payload["messages"]
    system_instruction = messages[0]["content"]
    user_instruction = messages[1]["content"]
    if "PHASE15_RATE_LIMIT" in user_instruction:
        return httpx.Response(429, text=f"Bearer {PRIVATE_KEY} must never escape")
    if "Job profile" in system_instruction:
        content = JOB_OUTPUT
    else:
        generated = await DeterministicExplanationProvider().generate(
            ExplanationProviderRequest(
                system_instruction=system_instruction,
                user_instruction=user_instruction,
                output_contract_version="explanation_plan_v1",
                max_output_tokens=payload["max_tokens"],
            )
        )
        content = generated.content
    return httpx.Response(
        200,
        json={
            "model": "phase15-test-model",
            "choices": [{"message": {"content": content}}],
        },
    )


_client = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
_extraction_descriptor = ExplanationProviderDescriptor(
    kind="openai_compatible",
    name="openai_compatible",
    configured_model="phase15-test-model",
    configuration_fingerprint="a" * 64,
)
_extraction_transport = OpenAICompatibleChatProvider(
    descriptor=_extraction_descriptor,
    base_url="https://phase15-provider.invalid/v1",
    api_key=PRIVATE_KEY,
    timeout_seconds=10,
    client=_client,
)
_structured_provider = OpenAICompatibleStructuredOutputProvider(
    transport=_extraction_transport,
    descriptor=ProviderDescriptor(
        name="openai_compatible",
        kind="openai_compatible",
        data_origin=DataOrigin.LLM_PARSED,
    ),
    max_output_tokens=2048,
)
_explanation_provider = OpenAICompatibleChatProvider(
    descriptor=ExplanationProviderDescriptor(
        kind="openai_compatible",
        name="openai_compatible",
        configured_model="phase15-test-model",
        configuration_fingerprint="b" * 64,
    ),
    base_url="https://phase15-provider.invalid/v1",
    api_key=PRIVATE_KEY,
    timeout_seconds=10,
    client=_client,
)


def _profile_service(
    session: AsyncSession = Depends(get_db_session),
) -> ProfileExtractionService:
    return ProfileExtractionService(
        _structured_provider,
        _structured_provider.descriptor,
        max_attempts=2,
        timeout_seconds=10,
        candidate_service=CandidateService(session, CandidateRepository(session)),
        job_service=JobService(session, JobRepository(session)),
    )


def _explanation_service() -> ExplanationGenerationService:
    settings = get_settings()
    session_factory = get_session_factory()
    return ExplanationGenerationService(
        match_run_repository=MatchRunRepository(session_factory),
        explanation_repository=ExplanationRunRepository(session_factory),
        attempt_repository=ExplanationAttemptRepository(session_factory),
        query_repository=ExplanationQueryRepository(session_factory),
        provider=_explanation_provider,
        pipeline=ExplanationGenerationPipeline(
            max_output_tokens=settings.explanation_max_output_tokens,
            max_prompt_bytes=settings.explanation_max_prompt_bytes,
        ),
        max_attempts=settings.explanation_max_attempts,
    )


app.dependency_overrides[get_profile_extraction_service] = _profile_service
app.dependency_overrides[get_explanation_generation_service] = _explanation_service
