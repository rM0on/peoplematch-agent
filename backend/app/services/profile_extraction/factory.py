from __future__ import annotations

from pathlib import Path

from app.schemas.persistence import DataOrigin
from app.services.explanation.generation.factory import build_explanation_provider
from app.services.explanation.generation.provider import (
    ExplanationProviderConfigurationError,
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
    if settings.extraction_provider == "mock":
        return (
            MockStructuredOutputProvider.from_fixture_directory(fixture_root),
            MOCK_PROVIDER_DESCRIPTOR,
        )
    if settings.extraction_provider != "deepseek":
        raise ExplanationProviderConfigurationError(
            f"Extraction provider '{settings.extraction_provider}' is not implemented"
        )

    transport_settings = settings.model_copy(
        update={
            "explanation_provider": "deepseek",
            "explanation_timeout_seconds": settings.extraction_timeout_seconds,
        }
    )
    transport = build_explanation_provider(transport_settings)
    descriptor = ProviderDescriptor(
        name="deepseek",
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
