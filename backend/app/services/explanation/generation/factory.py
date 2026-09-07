from __future__ import annotations

from app.services.explanation.generation.openai_compatible import (
    OpenAICompatibleChatProvider,
)
from app.services.explanation.generation.mock_provider import (
    DeterministicExplanationProvider,
)
from app.services.explanation.generation.provider import (
    ExplanationProviderDescriptor,
)
from app.services.llm.configuration import (
    ProviderMode,
    ProviderTask,
    resolve_provider_selection,
)


def build_explanation_provider(settings):
    """Build configured transport adapters; no domain behavior belongs here."""

    selection = resolve_provider_selection(settings, ProviderTask.EXPLANATION)
    if selection.mode is ProviderMode.MOCK:
        return DeterministicExplanationProvider()
    descriptor = ExplanationProviderDescriptor(
        kind="openai_compatible",
        name=selection.provider_name,
        configured_model=selection.model,
        configuration_fingerprint=selection.configuration_fingerprint,
    )
    return OpenAICompatibleChatProvider(
        descriptor=descriptor,
        base_url=selection.base_url,
        api_key=selection.api_key,
        timeout_seconds=selection.timeout_seconds,
    )


__all__ = ["build_explanation_provider"]
