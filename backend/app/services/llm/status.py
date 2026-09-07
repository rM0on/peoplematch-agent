from __future__ import annotations

from app.schemas.provider_status import AIProviderStatusData, AIProviderTaskStatus
from app.services.explanation.generation.provider import (
    ExplanationProviderConfigurationError,
)
from app.services.llm.configuration import (
    ProviderMode,
    ProviderTask,
    resolve_provider_selection,
)


def _selector(settings, task: ProviderTask) -> str:
    return (
        settings.extraction_provider
        if task is ProviderTask.EXTRACTION
        else settings.explanation_provider
    )


def _unconfigured_real_status(settings, task: ProviderTask) -> AIProviderTaskStatus:
    selector = _selector(settings, task)
    return AIProviderTaskStatus(
        task=task.value,
        mode=ProviderMode.OPENAI_COMPATIBLE.value,
        configured=False,
        provider_name="deepseek" if selector == "deepseek" else "openai_compatible",
        configured_model=None,
        arbitrary_input_supported=False,
    )


def project_provider_task_status(settings, task: ProviderTask) -> AIProviderTaskStatus:
    try:
        selection = resolve_provider_selection(settings, task)
    except ExplanationProviderConfigurationError:
        return _unconfigured_real_status(settings, task)
    return AIProviderTaskStatus(
        task=task.value,
        mode=selection.mode.value,
        configured=True,
        provider_name=selection.provider_name,
        configured_model=selection.model,
        arbitrary_input_supported=selection.mode is ProviderMode.OPENAI_COMPATIBLE,
    )


def project_ai_provider_status(settings) -> AIProviderStatusData:
    return AIProviderStatusData(
        extraction=project_provider_task_status(settings, ProviderTask.EXTRACTION),
        explanation=project_provider_task_status(settings, ProviderTask.EXPLANATION),
    )


__all__ = ["project_ai_provider_status", "project_provider_task_status"]
