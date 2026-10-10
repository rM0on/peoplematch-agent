from __future__ import annotations

from app.exceptions import ProviderUnavailableError
from app.services.explanation.generation.openai_compatible import OpenAICompatibleChatProvider
from app.services.explanation.generation.provider import (
    ExplanationProviderConfigurationError,
    ExplanationProviderDescriptor,
)
from app.services.llm.configuration import ProviderMode, ProviderTask, resolve_provider_selection


def build_recruiter_narrative_provider(settings):
    """Use the configured real explanation transport; never silently use mock."""

    try:
        selection = resolve_provider_selection(settings, ProviderTask.EXPLANATION)
    except ExplanationProviderConfigurationError:
        raise ProviderUnavailableError("Recruiter narrative provider is not configured") from None
    if selection.mode is not ProviderMode.OPENAI_COMPATIBLE:
        raise ProviderUnavailableError("Recruiter narrative requires a real AI provider")
    return OpenAICompatibleChatProvider(
        descriptor=ExplanationProviderDescriptor(
            kind="openai_compatible",
            name=selection.provider_name,
            configured_model=selection.model,
            configuration_fingerprint=selection.configuration_fingerprint,
        ),
        base_url=selection.base_url,
        api_key=selection.api_key,
        timeout_seconds=selection.timeout_seconds,
    )


__all__ = ["build_recruiter_narrative_provider"]
