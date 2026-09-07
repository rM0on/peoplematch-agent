from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import re
from urllib.parse import urlsplit

from app.services.explanation.generation.provider import (
    ExplanationProviderConfigurationError,
)


_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")


class ProviderMode(str, Enum):
    MOCK = "mock"
    OPENAI_COMPATIBLE = "openai_compatible"


class ProviderTask(str, Enum):
    EXTRACTION = "extraction"
    EXPLANATION = "explanation"


@dataclass(frozen=True)
class ResolvedProviderSelection:
    mode: ProviderMode
    selector: str
    provider_name: str
    timeout_seconds: float
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = field(default=None, repr=False)
    configuration_fingerprint: str | None = None


def _present(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _resolve_value(*, generic: object, legacy: object) -> str | None:
    generic_value = _present(generic)
    legacy_value = _present(legacy)
    if (
        generic_value is not None
        and legacy_value is not None
        and generic_value != legacy_value
    ):
        raise ExplanationProviderConfigurationError(
            "Generic and legacy provider configuration values conflict"
        )
    return generic_value or legacy_value


def _validate_base_url(value: str | None) -> str:
    if value is None:
        raise ExplanationProviderConfigurationError(
            "OpenAI-compatible base URL must be configured"
        )
    normalized = value.rstrip("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ExplanationProviderConfigurationError(
            "OpenAI-compatible base URL must be a credential-free HTTPS URL"
        )
    return normalized


def _validate_model(value: str | None) -> str:
    if value is None or _SAFE_MODEL.fullmatch(value) is None:
        raise ExplanationProviderConfigurationError(
            "OpenAI-compatible model must be configured"
        )
    return value


def _validate_api_key(value: str | None) -> str:
    if value is None:
        raise ExplanationProviderConfigurationError(
            "OpenAI-compatible API key must be configured"
        )
    return value


def _fingerprint(
    *,
    task: ProviderTask,
    provider_name: str,
    base_url: str,
    model: str,
    timeout_seconds: float,
) -> str:
    canonical = json.dumps(
        {
            "kind": ProviderMode.OPENAI_COMPATIBLE.value,
            "task": task.value,
            "provider_name": provider_name,
            "base_url": base_url,
            "model": model,
            "timeout_seconds": timeout_seconds,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def resolve_provider_selection(settings, task: ProviderTask) -> ResolvedProviderSelection:
    selector = (
        settings.extraction_provider
        if task is ProviderTask.EXTRACTION
        else settings.explanation_provider
    )
    timeout_seconds = (
        settings.extraction_timeout_seconds
        if task is ProviderTask.EXTRACTION
        else settings.explanation_timeout_seconds
    )
    if selector == ProviderMode.MOCK.value:
        return ResolvedProviderSelection(
            mode=ProviderMode.MOCK,
            selector=selector,
            provider_name="deterministic_mock",
            timeout_seconds=timeout_seconds,
        )
    if selector not in {ProviderMode.OPENAI_COMPATIBLE.value, "deepseek"}:
        label = "Extraction" if task is ProviderTask.EXTRACTION else "Explanation"
        raise ExplanationProviderConfigurationError(
            f"{label} provider '{selector}' is not implemented"
        )

    base_url = _validate_base_url(
        _resolve_value(
            generic=settings.llm_base_url,
            legacy=settings.explanation_deepseek_base_url,
        )
    )
    model = _validate_model(
        _resolve_value(
            generic=settings.llm_model,
            legacy=settings.explanation_deepseek_model,
        )
    )
    api_key = _validate_api_key(
        _resolve_value(
            generic=settings.llm_api_key,
            legacy=settings.explanation_deepseek_api_key,
        )
    )
    provider_name = "deepseek" if selector == "deepseek" else "openai_compatible"
    return ResolvedProviderSelection(
        mode=ProviderMode.OPENAI_COMPATIBLE,
        selector=selector,
        provider_name=provider_name,
        timeout_seconds=timeout_seconds,
        base_url=base_url,
        model=model,
        api_key=api_key,
        configuration_fingerprint=_fingerprint(
            task=task,
            provider_name=provider_name,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
        ),
    )


__all__ = [
    "ProviderMode",
    "ProviderTask",
    "ResolvedProviderSelection",
    "resolve_provider_selection",
]
