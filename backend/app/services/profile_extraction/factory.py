from __future__ import annotations

from pathlib import Path

from app.schemas.persistence import DataOrigin
from app.services.explanation.generation.openai_compatible import (
    OpenAICompatibleChatProvider,
)
from app.services.explanation.generation.provider import (
    ExplanationProviderDescriptor,
)
from app.services.llm.configuration import (
    ProviderMode,
    ProviderTask,
    resolve_provider_selection,
)
from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
from app.services.profile_extraction.openai_compatible import (
    OpenAICompatibleStructuredOutputProvider,
)
from app.services.profile_extraction.provider import (
    MOCK_PROVIDER_DESCRIPTOR,
    ProviderDescriptor,
)


def build_profile_extraction_provider(settings, *, fixture_root: Path):
    selection = resolve_provider_selection(settings, ProviderTask.EXTRACTION)
    if selection.mode is ProviderMode.MOCK:
        return (
            MockStructuredOutputProvider.from_fixture_directory(fixture_root),
            MOCK_PROVIDER_DESCRIPTOR,
        )
    transport = OpenAICompatibleChatProvider(
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
    descriptor = ProviderDescriptor(
        name=selection.provider_name,
        kind="openai_compatible",
        data_origin=DataOrigin.LLM_PARSED,
    )
    return (
        OpenAICompatibleStructuredOutputProvider(
            transport=transport,
            descriptor=descriptor,
            max_output_tokens=settings.extraction_max_output_tokens,
        ),
        descriptor,
    )


__all__ = ["build_profile_extraction_provider"]
