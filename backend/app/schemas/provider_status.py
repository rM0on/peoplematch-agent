from __future__ import annotations

from typing import Literal, Optional

from app.schemas.shared import ContractModel


class AIProviderTaskStatus(ContractModel):
    task: Literal["extraction", "explanation"]
    mode: Literal["mock", "openai_compatible"]
    configured: bool
    provider_name: Literal["deterministic_mock", "openai_compatible", "deepseek"]
    configured_model: Optional[str]
    arbitrary_input_supported: bool


class AIProviderStatusData(ContractModel):
    extraction: AIProviderTaskStatus
    explanation: AIProviderTaskStatus


__all__ = ["AIProviderStatusData", "AIProviderTaskStatus"]
