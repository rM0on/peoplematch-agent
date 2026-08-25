from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlsplit

from app.services.explanation.generation.openai_compatible import (
    OpenAICompatibleChatProvider,
)


_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
from app.services.explanation.generation.mock_provider import (
    DeterministicExplanationProvider,
)
from app.services.explanation.generation.provider import (
    ExplanationProviderConfigurationError,
    ExplanationProviderDescriptor,
)


def _configuration_fingerprint(*, base_url: str, model: str, timeout_seconds: float) -> str:
    """Fingerprint non-secret provider configuration only."""

    canonical = json.dumps(
        {
            "kind": "openai_compatible",
            "name": "deepseek",
            "base_url": base_url,
            "model": model,
            "timeout_seconds": timeout_seconds,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_explanation_provider(settings):
    """Build configured transport adapters; no domain behavior belongs here."""

    if settings.explanation_provider == "mock":
        return DeterministicExplanationProvider()
    if settings.explanation_provider != "deepseek":
        raise ExplanationProviderConfigurationError(
            f"Explanation provider '{settings.explanation_provider}' is not implemented"
        )
    base_url = settings.explanation_deepseek_base_url
    model = settings.explanation_deepseek_model
    api_key = settings.explanation_deepseek_api_key
    if not isinstance(base_url, str) or not base_url.strip():
        raise ExplanationProviderConfigurationError(
            "DeepSeek base URL must be configured"
        )
    base_url = base_url.strip().rstrip("/")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ExplanationProviderConfigurationError(
            "DeepSeek base URL must be a credential-free HTTPS URL"
        )
    if not isinstance(model, str) or _SAFE_MODEL.fullmatch(model) is None:
        raise ExplanationProviderConfigurationError("DeepSeek model must be configured")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ExplanationProviderConfigurationError("DeepSeek API key must be configured")
    descriptor = ExplanationProviderDescriptor(
        kind="openai_compatible",
        name="deepseek",
        configured_model=model,
        configuration_fingerprint=_configuration_fingerprint(
            base_url=base_url,
            model=model,
            timeout_seconds=settings.explanation_timeout_seconds,
        ),
    )
    return OpenAICompatibleChatProvider(
        descriptor=descriptor,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=settings.explanation_timeout_seconds,
    )


__all__ = ["build_explanation_provider"]
