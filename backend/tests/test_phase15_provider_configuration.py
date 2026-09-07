from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.explanation.generation.provider import (
    ExplanationProviderConfigurationError,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "samples" / "extraction"
PRIVATE_KEY = "phase15-private-key-must-not-leak"


def _generic_settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "extraction_provider": "openai_compatible",
        "explanation_provider": "openai_compatible",
        "llm_base_url": "https://provider.example/v1",
        "llm_model": "provider-model-v1",
        "llm_api_key": PRIVATE_KEY,
        "extraction_timeout_seconds": 7,
        "explanation_timeout_seconds": 11,
    }
    values.update(overrides)
    return Settings(**values)


def test_generic_openai_compatible_settings_resolve_for_both_domain_tasks() -> None:
    from app.services.llm.configuration import (
        ProviderMode,
        ProviderTask,
        resolve_provider_selection,
    )

    settings = _generic_settings()
    extraction = resolve_provider_selection(settings, ProviderTask.EXTRACTION)
    explanation = resolve_provider_selection(settings, ProviderTask.EXPLANATION)

    assert extraction.mode is ProviderMode.OPENAI_COMPATIBLE
    assert explanation.mode is ProviderMode.OPENAI_COMPATIBLE
    assert extraction.provider_name == "openai_compatible"
    assert explanation.provider_name == "openai_compatible"
    assert extraction.model == explanation.model == "provider-model-v1"
    assert extraction.timeout_seconds == 7
    assert explanation.timeout_seconds == 11
    assert extraction.configuration_fingerprint != explanation.configuration_fingerprint
    assert PRIVATE_KEY not in repr(extraction)
    assert PRIVATE_KEY not in repr(explanation)
    assert PRIVATE_KEY not in extraction.configuration_fingerprint


def test_mock_selection_never_requires_or_reads_transport_credentials() -> None:
    from app.services.llm.configuration import (
        ProviderMode,
        ProviderTask,
        resolve_provider_selection,
    )

    settings = Settings(
        _env_file=None,
        extraction_provider="mock",
        explanation_provider="mock",
        llm_base_url="not-a-url",
        llm_model="not a safe model",
        llm_api_key=PRIVATE_KEY,
    )

    resolved = resolve_provider_selection(settings, ProviderTask.EXTRACTION)

    assert resolved.mode is ProviderMode.MOCK
    assert resolved.provider_name == "deterministic_mock"
    assert resolved.base_url is None
    assert resolved.model is None
    assert resolved.api_key is None
    assert PRIVATE_KEY not in repr(resolved)


def test_deepseek_alias_uses_legacy_values_when_generic_values_are_absent() -> None:
    from app.services.llm.configuration import (
        ProviderMode,
        ProviderTask,
        resolve_provider_selection,
    )

    settings = Settings(
        _env_file=None,
        extraction_provider="deepseek",
        explanation_deepseek_base_url="https://api.deepseek.example/v1",
        explanation_deepseek_model="deepseek-chat",
        explanation_deepseek_api_key=PRIVATE_KEY,
    )

    resolved = resolve_provider_selection(settings, ProviderTask.EXTRACTION)

    assert resolved.mode is ProviderMode.OPENAI_COMPATIBLE
    assert resolved.provider_name == "deepseek"
    assert resolved.base_url == "https://api.deepseek.example/v1"
    assert resolved.model == "deepseek-chat"


@pytest.mark.parametrize("selector", ["", "auto", "openai", "unknown"])
def test_unknown_provider_selectors_fail_closed(selector: str) -> None:
    from app.services.llm.configuration import ProviderTask, resolve_provider_selection

    settings = Settings(_env_file=None, extraction_provider=selector)

    with pytest.raises(ExplanationProviderConfigurationError, match="not implemented"):
        resolve_provider_selection(settings, ProviderTask.EXTRACTION)


def test_conflicting_generic_and_legacy_values_fail_closed() -> None:
    from app.services.llm.configuration import ProviderTask, resolve_provider_selection

    settings = _generic_settings(
        extraction_provider="deepseek",
        explanation_deepseek_base_url="https://different.example/v1",
        explanation_deepseek_model="different-model",
        explanation_deepseek_api_key="different-private-key",
    )

    with pytest.raises(ExplanationProviderConfigurationError, match="conflict"):
        resolve_provider_selection(settings, ProviderTask.EXTRACTION)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://provider.example/v1",
        "https://user:password@provider.example/v1",
        "https://provider.example/v1?key=secret",
        "https://provider.example/v1#fragment",
    ],
)
def test_generic_provider_rejects_unsafe_base_urls(base_url: str) -> None:
    from app.services.llm.configuration import ProviderTask, resolve_provider_selection

    with pytest.raises(ExplanationProviderConfigurationError, match="base URL"):
        resolve_provider_selection(
            _generic_settings(llm_base_url=base_url),
            ProviderTask.EXPLANATION,
        )


def test_generic_provider_requires_model_and_local_key() -> None:
    from app.services.llm.configuration import ProviderTask, resolve_provider_selection

    with pytest.raises(ExplanationProviderConfigurationError, match="model"):
        resolve_provider_selection(
            _generic_settings(llm_model=None),
            ProviderTask.EXTRACTION,
        )
    with pytest.raises(ExplanationProviderConfigurationError, match="API key"):
        resolve_provider_selection(
            _generic_settings(llm_api_key=None),
            ProviderTask.EXTRACTION,
        )


def test_domain_factories_share_generic_transport_configuration_without_merging_domains() -> None:
    from app.services.explanation.generation.factory import build_explanation_provider
    from app.services.profile_extraction.factory import build_profile_extraction_provider

    settings = _generic_settings()
    extraction, descriptor = build_profile_extraction_provider(
        settings,
        fixture_root=FIXTURES,
    )
    explanation = build_explanation_provider(settings)
    try:
        assert descriptor.name == "openai_compatible"
        assert descriptor.kind == "openai_compatible"
        assert explanation.descriptor.name == "openai_compatible"
        assert extraction._transport is not explanation
        assert extraction.configuration_fingerprint != explanation.descriptor.configuration_fingerprint
        assert PRIVATE_KEY not in repr(extraction)
        assert PRIVATE_KEY not in repr(explanation)
    finally:
        asyncio.run(extraction.aclose())
        asyncio.run(explanation.aclose())


def test_compose_and_example_forward_generic_provider_configuration_without_a_key() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for name in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        assert f"{name}:" in compose
        assert f"{name}=" in example
    assert PRIVATE_KEY not in compose
    assert PRIVATE_KEY not in example
