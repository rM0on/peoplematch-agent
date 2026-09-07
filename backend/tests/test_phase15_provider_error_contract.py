from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.exceptions import (
    ProviderOutputInvalidError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.extraction import JobExtractionDraft
from app.schemas.persistence import DataOrigin
from app.services.profile_extraction.provider import (
    ExtractionTask,
    ProviderDescriptor,
    ProviderRequest,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "samples" / "extraction"
PRIVATE_KEY = "phase15-private-key-must-not-leak"
PRIVATE_SOURCE = "候选人私人简历内容不得进入日志 PRIVATE-RESUME-TEXT " * 8


def _request() -> ProviderRequest:
    return ProviderRequest(
        task=ExtractionTask.JOB,
        source_text="Synthetic job description with enough content for extraction.",
        prompt_version="job_extraction_prompt_v1",
        prompt_fingerprint="d" * 64,
        system_message="Return source-supported structured JSON.",
        user_message="Extract this synthetic job description.",
        output_contract=JobExtractionDraft.model_json_schema(),
        attempt=1,
    )


def _real_extraction_provider(handler):
    from app.services.explanation.generation.openai_compatible import (
        OpenAICompatibleChatProvider,
    )
    from app.services.explanation.generation.provider import (
        ExplanationProviderDescriptor,
    )
    from app.services.profile_extraction.openai_compatible import (
        OpenAICompatibleStructuredOutputProvider,
    )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = OpenAICompatibleChatProvider(
        descriptor=ExplanationProviderDescriptor(
            kind="openai_compatible",
            name="openai_compatible",
            configured_model="configured-model",
            configuration_fingerprint="a" * 64,
        ),
        base_url="https://provider.example/v1",
        api_key=PRIVATE_KEY,
        timeout_seconds=7,
        client=client,
    )
    return (
        OpenAICompatibleStructuredOutputProvider(
            transport=transport,
            descriptor=ProviderDescriptor(
                "openai_compatible", "openai_compatible", DataOrigin.LLM_PARSED
            ),
            max_output_tokens=2048,
        ),
        client,
    )


def test_timeout_maps_to_stable_safe_domain_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            f"Authorization: Bearer {PRIVATE_KEY} PRIVATE-RESUME-TEXT",
            request=request,
        )

    async def scenario() -> None:
        provider, client = _real_extraction_provider(handler)
        try:
            with pytest.raises(ProviderTimeoutError) as exc_info:
                await provider.generate(_request())
            assert exc_info.value.code == "provider_timeout"
            assert PRIVATE_KEY not in str(exc_info.value)
            assert "PRIVATE-RESUME-TEXT" not in str(exc_info.value)
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_rate_limit_maps_to_closed_safe_domain_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "private-upstream-detail"},
            text=f"Bearer {PRIVATE_KEY} PRIVATE-RESUME-TEXT traceback",
        )

    async def scenario() -> None:
        from app.exceptions import ProviderRateLimitError
        from app.services.profile_extraction.parser import ProfileExtractionService

        provider, client = _real_extraction_provider(handler)
        try:
            with pytest.raises(ProviderRateLimitError) as exc_info:
                await ProfileExtractionService(
                    provider,
                    provider.descriptor,
                ).extract_job("Synthetic job description " * 5)
            assert exc_info.value.code == "provider_rate_limited"
            assert exc_info.value.status_code == 503
            assert str(exc_info.value) == "AI provider request rate limited"
            serialized = str(exc_info.value)
            assert PRIVATE_KEY not in serialized
            assert "Retry-After" not in serialized
            assert "PRIVATE-RESUME-TEXT" not in serialized
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_invalid_output_never_reaches_candidate_persistence() -> None:
    from app.services.profile_extraction.mock_provider import (
        MockStructuredOutputProvider,
    )
    from app.services.profile_extraction.parser import ProfileExtractionService

    class CandidatePersistenceSpy:
        called = False

        async def create_from_extraction(self, *_args, **_kwargs):
            self.called = True
            raise AssertionError("invalid provider output must not be persisted")

    async def scenario() -> None:
        spy = CandidatePersistenceSpy()
        service = ProfileExtractionService(
            MockStructuredOutputProvider.with_responses(
                ["not-json", json.dumps({"name": "schema-invalid"})]
            ),
            ProviderDescriptor("test", "mock", DataOrigin.SYNTHETIC_SANDBOX),
            candidate_service=spy,
        )
        with pytest.raises(ProviderOutputInvalidError):
            await service.parse_candidate(PRIVATE_SOURCE, persist=True)
        assert spy.called is False

    asyncio.run(scenario())


def test_missing_real_provider_configuration_fails_without_mock_fallback() -> None:
    from app.services.explanation.generation.provider import (
        ExplanationProviderConfigurationError,
    )
    from app.services.profile_extraction.factory import (
        build_profile_extraction_provider,
    )

    settings = Settings(
        _env_file=None,
        extraction_provider="openai_compatible",
        llm_base_url="https://provider.example/v1",
        llm_model="configured-model",
        llm_api_key=None,
    )
    with pytest.raises(ExplanationProviderConfigurationError, match="API key"):
        build_profile_extraction_provider(settings, fixture_root=FIXTURES)


def test_extraction_failure_log_redacts_secret_and_source(caplog) -> None:
    from app.services.profile_extraction.parser import ProfileExtractionService

    class FailingProvider:
        async def generate(self, _request):
            raise RuntimeError(
                f"Authorization: Bearer {PRIVATE_KEY}; source={PRIVATE_SOURCE}"
            )

    service = ProfileExtractionService(
        FailingProvider(),
        ProviderDescriptor("openai_compatible", "openai_compatible", DataOrigin.LLM_PARSED),
    )
    with caplog.at_level(logging.WARNING, logger="peoplematch.extraction"):
        with pytest.raises(ProviderUnavailableError) as exc_info:
            asyncio.run(service.extract_candidate(PRIVATE_SOURCE, request_id="safe-id"))

    captured = caplog.text
    assert PRIVATE_KEY not in captured
    assert "PRIVATE-RESUME-TEXT" not in captured
    assert PRIVATE_KEY not in str(exc_info.value)
    assert "PRIVATE-RESUME-TEXT" not in str(exc_info.value)
