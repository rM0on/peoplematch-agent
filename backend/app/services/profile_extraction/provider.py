from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol

from app.schemas.persistence import DataOrigin


class ExtractionTask(str, Enum):
    CANDIDATE = "candidate"
    JOB = "job"


@dataclass(frozen=True)
class ProviderRequest:
    task: ExtractionTask
    source_text: str
    prompt_version: str
    prompt_fingerprint: str
    system_message: str
    user_message: str
    output_contract: dict[str, Any]
    attempt: int
    validation_feedback: Optional[str] = None


@dataclass(frozen=True)
class ProviderResponse:
    raw_output: str


@dataclass(frozen=True)
class ProviderDescriptor:
    name: str
    kind: str
    data_origin: DataOrigin


MOCK_PROVIDER_DESCRIPTOR = ProviderDescriptor(
    name="deterministic_mock",
    kind="mock",
    data_origin=DataOrigin.MOCK_PARSED,
)


class StructuredOutputProvider(Protocol):
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Return strict JSON text for the requested extraction contract."""
