from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.exceptions import (
    ProviderOutputInvalidError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.extraction import CandidateExtractionDraft, JobExtractionDraft
from app.schemas.persistence import DataOrigin
from app.services.profile_extraction.provider import ExtractionTask, ProviderRequest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "samples" / "extraction"
PRIVATE_KEY = "private-phase12-key-must-never-appear"


def _request(task: ExtractionTask) -> ProviderRequest:
    schema = CandidateExtractionDraft if task is ExtractionTask.CANDIDATE else JobExtractionDraft
    return ProviderRequest(
        task=task,
        source_text="Synthetic source text with enough bounded content for extraction.",
        prompt_version=f"{task.value}_extraction_prompt_v1",
        prompt_fingerprint="d" * 64,
        system_message="Return only source-supported structured JSON.",
        user_message="Extract the delimited synthetic source.",
        output_contract=schema.model_json_schema(),
        attempt=1,
    )


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "extraction_provider": "deepseek",
        "extraction_timeout_seconds": 7,
        "extraction_max_output_tokens": 2048,
        "explanation_deepseek_base_url": "https://provider.example/v1",
        "explanation_deepseek_model": "configured-model",
        "explanation_deepseek_api_key": PRIVATE_KEY,
    }
    values.update(overrides)
    return Settings(**values)


def test_real_extraction_adapter_reuses_openai_transport_and_sends_exact_schema() -> None:
    from app.services.explanation.generation.openai_compatible import OpenAICompatibleChatProvider
    from app.services.explanation.generation.provider import ExplanationProviderDescriptor
    from app.services.profile_extraction.openai_compatible import (
        OpenAICompatibleStructuredOutputProvider,
    )
    from app.services.profile_extraction.provider import ProviderDescriptor

    observed: dict[str, object] = {}
    output = (FIXTURES / "candidate_matching_output.json").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        observed["authorization"] = request.headers.get("Authorization")
        observed["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"model": "configured-model", "choices": [{"message": {"content": output}}]},
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            transport = OpenAICompatibleChatProvider(
                descriptor=ExplanationProviderDescriptor(
                    kind="openai_compatible",
                    name="deepseek",
                    configured_model="configured-model",
                    configuration_fingerprint="a" * 64,
                ),
                base_url="https://provider.example/v1",
                api_key=PRIVATE_KEY,
                timeout_seconds=7,
                client=client,
            )
            provider = OpenAICompatibleStructuredOutputProvider(
                transport=transport,
                descriptor=ProviderDescriptor(
                    name="deepseek",
                    kind="openai_compatible",
                    data_origin=DataOrigin.LLM_PARSED,
                ),
                max_output_tokens=2048,
            )
            response = await provider.generate(_request(ExtractionTask.CANDIDATE))
            assert response.raw_output == output
            assert PRIVATE_KEY not in repr(provider)

    asyncio.run(scenario())
    assert observed["authorization"] == f"Bearer {PRIVATE_KEY}"
    payload = observed["payload"]
    assert isinstance(payload, dict)
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0
    assert payload["max_tokens"] == 2048
    user_content = payload["messages"][1]["content"]
    assert "CandidateExtractionDraft" in user_content
    assert PRIVATE_KEY not in json.dumps(payload)


@pytest.mark.parametrize(
    ("provider_error", "expected"),
    [
        (httpx.ReadTimeout("private timeout detail"), ProviderTimeoutError),
        (httpx.ConnectError("private transport detail"), ProviderUnavailableError),
    ],
)
def test_real_extraction_adapter_maps_transport_failures_without_secret_leak(
    provider_error: Exception,
    expected: type[Exception],
) -> None:
    from app.services.explanation.generation.openai_compatible import OpenAICompatibleChatProvider
    from app.services.explanation.generation.provider import ExplanationProviderDescriptor
    from app.services.profile_extraction.openai_compatible import OpenAICompatibleStructuredOutputProvider
    from app.services.profile_extraction.provider import ProviderDescriptor

    def handler(_request: httpx.Request) -> httpx.Response:
        raise provider_error

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            transport = OpenAICompatibleChatProvider(
                descriptor=ExplanationProviderDescriptor(
                    kind="openai_compatible",
                    name="deepseek",
                    configured_model="configured-model",
                    configuration_fingerprint="b" * 64,
                ),
                base_url="https://provider.example/v1",
                api_key=PRIVATE_KEY,
                timeout_seconds=7,
                client=client,
            )
            provider = OpenAICompatibleStructuredOutputProvider(
                transport=transport,
                descriptor=ProviderDescriptor("deepseek", "openai_compatible", DataOrigin.LLM_PARSED),
                max_output_tokens=2048,
            )
            with pytest.raises(expected) as exc_info:
                await provider.generate(_request(ExtractionTask.JOB))
            assert PRIVATE_KEY not in str(exc_info.value)
            assert "private" not in str(exc_info.value)

    asyncio.run(scenario())


def test_real_extraction_adapter_maps_malformed_envelope_to_invalid_output() -> None:
    from app.services.explanation.generation.openai_compatible import OpenAICompatibleChatProvider
    from app.services.explanation.generation.provider import ExplanationProviderDescriptor
    from app.services.profile_extraction.openai_compatible import OpenAICompatibleStructuredOutputProvider
    from app.services.profile_extraction.provider import ProviderDescriptor

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"choices": []}))
        ) as client:
            transport = OpenAICompatibleChatProvider(
                descriptor=ExplanationProviderDescriptor(
                    kind="openai_compatible",
                    name="deepseek",
                    configured_model="configured-model",
                    configuration_fingerprint="c" * 64,
                ),
                base_url="https://provider.example/v1",
                api_key=PRIVATE_KEY,
                timeout_seconds=7,
                client=client,
            )
            provider = OpenAICompatibleStructuredOutputProvider(
                transport=transport,
                descriptor=ProviderDescriptor("deepseek", "openai_compatible", DataOrigin.LLM_PARSED),
                max_output_tokens=2048,
            )
            with pytest.raises(ProviderOutputInvalidError):
                await provider.generate(_request(ExtractionTask.JOB))

    asyncio.run(scenario())


def test_extraction_provider_factory_is_closed_and_requires_local_credentials() -> None:
    from app.services.profile_extraction.factory import build_profile_extraction_provider
    from app.services.explanation.generation.provider import ExplanationProviderConfigurationError

    with pytest.raises(ExplanationProviderConfigurationError, match="not implemented"):
        build_profile_extraction_provider(
            _settings(extraction_provider="unknown"), fixture_root=FIXTURES
        )
    with pytest.raises(ExplanationProviderConfigurationError, match="API key"):
        build_profile_extraction_provider(
            _settings(explanation_deepseek_api_key=None), fixture_root=FIXTURES
        )


def test_real_extraction_factory_uses_llm_parsed_provenance_and_non_secret_fingerprint() -> None:
    from app.services.profile_extraction.factory import build_profile_extraction_provider

    provider, descriptor = build_profile_extraction_provider(_settings(), fixture_root=FIXTURES)
    try:
        assert descriptor.name == "deepseek"
        assert descriptor.kind == "openai_compatible"
        assert descriptor.data_origin is DataOrigin.LLM_PARSED
        assert PRIVATE_KEY not in repr(provider)
        assert PRIVATE_KEY not in provider.configuration_fingerprint
    finally:
        asyncio.run(provider.aclose())


def test_candidate_and_job_drafts_validate_under_llm_parsed_origin() -> None:
    candidate = json.loads((FIXTURES / "candidate_matching_output.json").read_text(encoding="utf-8"))
    job = json.loads((FIXTURES / "job_matching_engineer_output.json").read_text(encoding="utf-8"))

    CandidateExtractionDraft.model_validate(
        candidate, context={"data_origin": DataOrigin.LLM_PARSED}
    )
    JobExtractionDraft.model_validate(job, context={"data_origin": DataOrigin.LLM_PARSED})


def test_parse_service_preserves_typed_provider_failures() -> None:
    from app.services.profile_extraction.parser import ProfileExtractionService
    from app.services.profile_extraction.provider import ProviderDescriptor

    class FailingProvider:
        async def generate(self, _request):
            raise ProviderTimeoutError("Structured output provider timed out")

    service = ProfileExtractionService(
        FailingProvider(),
        ProviderDescriptor("deepseek", "openai_compatible", DataOrigin.LLM_PARSED),
    )
    with pytest.raises(ProviderTimeoutError):
        asyncio.run(service.extract_candidate("x" * 80))


def test_runtime_extraction_provider_is_cached_and_closed_at_shutdown(monkeypatch) -> None:
    from app.api import dependencies
    from app.services.profile_extraction.provider import ProviderDescriptor

    class CloseableProvider:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    provider = CloseableProvider()
    descriptor = ProviderDescriptor("deepseek", "openai_compatible", DataOrigin.LLM_PARSED)
    dependencies.get_runtime_extraction_provider.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: object())
    monkeypatch.setattr(
        dependencies,
        "build_profile_extraction_provider",
        lambda _settings, fixture_root: (provider, descriptor),
    )

    assert dependencies.get_runtime_extraction_provider() == (provider, descriptor)
    assert dependencies.get_runtime_extraction_provider() == (provider, descriptor)
    assert dependencies.get_runtime_extraction_provider.cache_info().currsize == 1
    asyncio.run(dependencies.close_runtime_extraction_provider())

    assert provider.closed is True
    assert dependencies.get_runtime_extraction_provider.cache_info().currsize == 0


def test_profile_extraction_dependency_uses_trusted_cached_provider(monkeypatch) -> None:
    from app.api import dependencies
    from app.services.profile_extraction.provider import ProviderDescriptor

    provider = object()
    descriptor = ProviderDescriptor("deepseek", "openai_compatible", DataOrigin.LLM_PARSED)
    monkeypatch.setattr(dependencies, "get_runtime_extraction_provider", lambda: (provider, descriptor))
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: Settings(_env_file=None, extraction_max_attempts=1, extraction_timeout_seconds=4),
    )

    service = dependencies.get_profile_extraction_service(session=object())

    assert service.provider is provider
    assert service.provider_descriptor is descriptor
    assert service.max_attempts == 1
    assert service.timeout_seconds == 4


def test_compose_and_example_forward_real_extraction_configuration_without_a_secret() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for name in (
        "EXTRACTION_PROVIDER",
        "EXTRACTION_MAX_ATTEMPTS",
        "EXTRACTION_TIMEOUT_SECONDS",
        "EXTRACTION_MAX_OUTPUT_TOKENS",
        "EXPLANATION_DEEPSEEK_BASE_URL",
        "EXPLANATION_DEEPSEEK_MODEL",
        "EXPLANATION_DEEPSEEK_API_KEY",
    ):
        assert f"{name}:" in compose
        assert f"{name}=" in example
    assert "private-phase12-key" not in compose
    assert "private-phase12-key" not in example


def test_explanation_projection_accepts_every_canonical_job_requirement_category() -> None:
    from app.schemas.job import RequirementCategory
    from app.services.explanation.generation.contracts import ProviderPromptRequirement

    for category in RequirementCategory:
        value = ProviderPromptRequirement(
            requirement_ref="ref_0001",
            priority="must_have",
            category=category.value,
        )
        assert value.category == category.value
