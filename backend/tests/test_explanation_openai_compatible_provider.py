from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pathlib import Path


_API_KEY = "test-deepseek-key-must-never-persist"
_PRIVATE_SENTINELS = (
    "candidate:1:skill:internal-evidence-id",
    "workflow_fingerprint",
    "raw_resume_private_text",
    "raw_jd_private_text",
    _API_KEY,
)


def _opaque_prompt_payload() -> dict[str, object]:
    """Only the post-projection contract may cross the provider transport."""
    return {
        "contract_version": "provider_prompt_evidence_v1",
        "job": {
            "requirements": [
                {
                    "requirement_ref": "ref_0001",
                    "priority": "must_have",
                    "category": "skill",
                }
            ]
        },
        "candidates": [
            {
                "candidate_ref": "candidate_0001",
                "result_rank": 1,
                "facts": {
                    "match_reasons": [],
                    "ranking_context": [],
                    "risks": [],
                    "missing_requirements": [],
                    "comparison": None,
                },
            }
        ],
    }


def _request():
    from app.services.explanation.generation.provider import ExplanationProviderRequest

    return ExplanationProviderRequest(
        system_instruction=(
            "Return one JSON object only. Select from opaque references; do not author facts."
        ),
        user_instruction=json.dumps(_opaque_prompt_payload(), sort_keys=True),
        output_contract_version="explanation_plan_v1",
        max_output_tokens=512,
    )


def _descriptor():
    from app.services.explanation.generation.provider import ExplanationProviderDescriptor

    return ExplanationProviderDescriptor(
        kind="openai_compatible",
        name="test_openai_compatible",
        configured_model="configured-test-model",
        configuration_fingerprint="a" * 64,
    )


def _provider(*, client: httpx.AsyncClient):
    from app.services.explanation.generation.openai_compatible import (
        OpenAICompatibleChatProvider,
    )

    return OpenAICompatibleChatProvider(
        descriptor=_descriptor(),
        base_url="https://provider.example/v1/",
        api_key=_API_KEY,
        timeout_seconds=4,
        client=client,
    )


def test_openai_compatible_transport_posts_only_closed_opaque_prompt_in_json_mode() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["method"] = request.method
        observed["path"] = request.url.path
        observed["headers"] = dict(request.headers)
        observed["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "provider-response-id-must-not-leave-transport",
                "model": "observed-provider-model",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "contract_version": "explanation_plan_v1",
                                    "candidates": [],
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            response = await _provider(client=client).generate(_request())

        assert response.content == json.dumps(
            {"contract_version": "explanation_plan_v1", "candidates": []}
        )
        assert response.observed_model == "observed-provider-model"
        assert not hasattr(response, "response_id")
        assert not hasattr(response, "raw_response")

    asyncio.run(scenario())

    assert observed["method"] == "POST"
    assert observed["path"] == "/v1/chat/completions"
    headers = observed["headers"]
    assert headers["authorization"] == f"Bearer {_API_KEY}"
    assert headers["content-type"].startswith("application/json")
    body = observed["body"]
    assert body == {
        "model": "configured-test-model",
        "messages": [
            {
                "role": "system",
                "content": "Return one JSON object only. Select from opaque references; do not author facts.",
            },
            {
                "role": "user",
                "content": json.dumps(_opaque_prompt_payload(), sort_keys=True),
            },
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "temperature": 0,
        "max_tokens": 512,
    }
    serialized_wire_body = json.dumps(body, sort_keys=True)
    for private_value in _PRIVATE_SENTINELS:
        assert private_value not in serialized_wire_body


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (httpx.ReadTimeout, "ExplanationProviderTimeoutError"),
        (httpx.ConnectError, "ExplanationProviderTransportError"),
    ],
)
def test_openai_compatible_transport_maps_network_failures_without_retry(
    exception_type, expected_error: str
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise exception_type("private network failure", request=request)

    async def scenario() -> None:
        from app.services.explanation.generation.provider import (
            ExplanationProviderTimeoutError,
            ExplanationProviderTransportError,
        )

        expected = {
            "ExplanationProviderTimeoutError": ExplanationProviderTimeoutError,
            "ExplanationProviderTransportError": ExplanationProviderTransportError,
        }[expected_error]
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(expected) as exc_info:
                await _provider(client=client).generate(_request())
        assert exc_info.value.category == expected_error.removeprefix(
            "ExplanationProvider"
        ).removesuffix("Error").lower()
        assert "private network failure" not in str(exc_info.value)
        assert _API_KEY not in str(exc_info.value)

    asyncio.run(scenario())
    assert calls == 1


def test_openai_compatible_transport_discards_non_success_provider_body() -> None:
    calls = 0
    private_body = "provider failure body containing raw_resume_private_text"

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, text=private_body)

    async def scenario() -> None:
        from app.services.explanation.generation.provider import ExplanationProviderHttpError

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ExplanationProviderHttpError) as exc_info:
                await _provider(client=client).generate(_request())
        assert exc_info.value.category == "http_status"
        assert exc_info.value.status_code == 429
        assert private_body not in str(exc_info.value)
        assert "raw_resume_private_text" not in str(exc_info.value)

    asyncio.run(scenario())
    assert calls == 1


@pytest.mark.parametrize(
    "response_payload",
    [
        b"provider malformed envelope raw_jd_private_text",
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": ["not", "text"]}}]},
        {"choices": [{"message": {"content": "   "}}]},
    ],
)
def test_openai_compatible_transport_rejects_malformed_or_empty_envelopes_safely(
    response_payload,
) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if isinstance(response_payload, bytes):
            return httpx.Response(200, content=response_payload)
        return httpx.Response(200, json=response_payload)

    async def scenario() -> None:
        from app.services.explanation.generation.provider import (
            ExplanationProviderMalformedResponseError,
        )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ExplanationProviderMalformedResponseError) as exc_info:
                await _provider(client=client).generate(_request())
        assert exc_info.value.category == "malformed_response"
        assert "raw_jd_private_text" not in str(exc_info.value)
        assert _API_KEY not in str(exc_info.value)

    asyncio.run(scenario())
    assert calls == 1


def test_openai_compatible_transport_rejects_oversized_response_and_untrusted_model_metadata() -> None:
    def oversized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "safe-model",
                "choices": [{"message": {"content": "x" * 70000}}],
            },
        )

    async def oversized_scenario() -> None:
        from app.services.explanation.generation.provider import (
            ExplanationProviderMalformedResponseError,
        )

        async with httpx.AsyncClient(transport=httpx.MockTransport(oversized)) as client:
            with pytest.raises(ExplanationProviderMalformedResponseError):
                await _provider(client=client).generate(_request())

    asyncio.run(oversized_scenario())

    def unsafe_model(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "RAW RESUME: private employment text",
                "choices": [{"message": {"content": "{}"}}],
            },
        )

    async def metadata_scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(unsafe_model)) as client:
            response = await _provider(client=client).generate(_request())
        assert response.observed_model is None

    asyncio.run(metadata_scenario())


def test_openai_compatible_transport_aborts_oversized_stream_before_buffering_tail() -> None:
    from app.services.explanation.generation.provider import (
        ExplanationProviderMalformedResponseError,
    )

    class OversizedStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.iterations = 0
            self.closed = False

        async def __aiter__(self):
            for chunk in (b"x" * 32768,) * 4:
                self.iterations += 1
                yield chunk

        async def aclose(self) -> None:
            self.closed = True

    stream = OversizedStream()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ExplanationProviderMalformedResponseError):
                await _provider(client=client).generate(_request())

    asyncio.run(scenario())

    assert stream.iterations == 3
    assert stream.closed is True


def test_openai_compatible_provider_closes_only_its_owned_client() -> None:
    from app.services.explanation.generation.openai_compatible import (
        OpenAICompatibleChatProvider,
    )

    async def scenario() -> None:
        owned = OpenAICompatibleChatProvider(
            descriptor=_descriptor(),
            base_url="https://provider.example/v1",
            api_key=_API_KEY,
            timeout_seconds=4,
        )
        owned_client = owned._client
        await owned.aclose()
        assert owned_client.is_closed is True

        injected_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))
        )
        injected = _provider(client=injected_client)
        await injected.aclose()
        assert injected_client.is_closed is False
        await injected_client.aclose()

    asyncio.run(scenario())


def test_runtime_provider_shutdown_closes_cached_provider(monkeypatch) -> None:
    from app.api import dependencies

    class CloseableProvider:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    provider = CloseableProvider()
    dependencies.get_runtime_explanation_provider.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: object())
    monkeypatch.setattr(
        dependencies,
        "build_explanation_provider",
        lambda _settings: provider,
    )

    assert dependencies.get_runtime_explanation_provider() is provider
    asyncio.run(dependencies.close_runtime_explanation_provider())

    assert provider.closed is True
    assert dependencies.get_runtime_explanation_provider.cache_info().currsize == 0


def test_deepseek_factory_is_configuration_only_and_never_exposes_key_or_hardcodes_model() -> None:
    from app.core.config import Settings
    from app.services.explanation.generation.factory import build_explanation_provider

    settings = Settings(
        _env_file=None,
        explanation_provider="deepseek",
        explanation_deepseek_base_url="https://deepseek.example/openai/v1",
        explanation_deepseek_model="configured-deepseek-model",
        explanation_deepseek_api_key=_API_KEY,
        explanation_timeout_seconds=7,
    )
    provider = build_explanation_provider(settings)

    assert provider.descriptor.kind == "openai_compatible"
    assert provider.descriptor.name == "deepseek"
    assert provider.descriptor.configured_model == "configured-deepseek-model"
    assert _API_KEY not in provider.descriptor.configuration_fingerprint
    assert _API_KEY not in repr(provider)
    assert "deepseek.example/openai/v1" not in provider.descriptor.configuration_fingerprint


def test_explanation_provider_factory_rejects_unknown_or_uncredentialed_provider_without_network() -> None:
    from app.core.config import Settings
    from app.services.explanation.generation.factory import build_explanation_provider
    from app.services.explanation.generation.provider import (
        ExplanationProviderConfigurationError,
    )

    unknown = Settings(_env_file=None, explanation_provider="not-a-provider")
    with pytest.raises(ExplanationProviderConfigurationError, match="not implemented"):
        build_explanation_provider(unknown)

    missing_key = Settings(
        _env_file=None,
        explanation_provider="deepseek",
        explanation_deepseek_base_url="https://deepseek.example/v1",
        explanation_deepseek_model="configured-deepseek-model",
        explanation_deepseek_api_key=None,
    )
    with pytest.raises(ExplanationProviderConfigurationError, match="API key"):
        build_explanation_provider(missing_key)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://deepseek.example/v1",
        "https://user:password@deepseek.example/v1",
        "https://deepseek.example/v1?api_key=secret",
        "https://deepseek.example/v1#fragment",
    ],
)
def test_deepseek_factory_rejects_unsafe_base_urls(base_url: str) -> None:
    from app.core.config import Settings
    from app.services.explanation.generation.factory import build_explanation_provider
    from app.services.explanation.generation.provider import (
        ExplanationProviderConfigurationError,
    )

    settings = Settings(
        _env_file=None,
        explanation_provider="deepseek",
        explanation_deepseek_base_url=base_url,
        explanation_deepseek_model="configured-deepseek-model",
        explanation_deepseek_api_key=_API_KEY,
    )
    with pytest.raises(ExplanationProviderConfigurationError, match="base URL"):
        build_explanation_provider(settings)
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "openai compatible"),
        ("name", "deepseek\nAuthorization: Bearer private"),
        ("configured_model", "private model name"),
        ("configuration_fingerprint", "not-a-fingerprint"),
    ],
)
def test_provider_descriptor_rejects_unbounded_or_unsafe_audit_metadata(
    field: str,
    value: str,
) -> None:
    from app.services.explanation.generation.provider import (
        ExplanationProviderConfigurationError,
        ExplanationProviderDescriptor,
    )

    values = {
        "kind": "openai_compatible",
        "name": "deepseek",
        "configured_model": "deepseek-chat",
        "configuration_fingerprint": "a" * 64,
    }
    values[field] = value

    with pytest.raises(ExplanationProviderConfigurationError):
        ExplanationProviderDescriptor(**values)


@pytest.mark.parametrize(
    ("case", "size"),
    [("empty", 0), ("whitespace", 3), ("oversized", 65537)],
)
def test_provider_response_contract_rejects_empty_or_unbounded_content(
    case: str,
    size: int,
) -> None:
    from app.services.explanation.generation.provider import (
        ExplanationProviderMalformedResponseError,
        ExplanationProviderResponse,
    )

    content = " " * size if case == "whitespace" else "x" * size
    with pytest.raises(ExplanationProviderMalformedResponseError):
        ExplanationProviderResponse(content=content, observed_model=None)


def test_compose_forwards_only_bounded_explanation_provider_configuration() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")

    for name in (
        "EXPLANATION_PROVIDER",
        "EXPLANATION_MAX_ATTEMPTS",
        "EXPLANATION_TIMEOUT_SECONDS",
        "EXPLANATION_MAX_OUTPUT_TOKENS",
        "EXPLANATION_MAX_PROMPT_BYTES",
        "EXPLANATION_DEEPSEEK_BASE_URL",
        "EXPLANATION_DEEPSEEK_MODEL",
        "EXPLANATION_DEEPSEEK_API_KEY",
    ):
        assert f"{name}:" in compose
    for forbidden in (
        "EXPLANATION_RAW_PROMPT",
        "EXPLANATION_PROVIDER_RESPONSE",
        "EXPLANATION_AUTHORIZATION_HEADER",
    ):
        assert forbidden not in compose
