from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from app.exceptions import MockInputNotSupportedError
from app.services.profile_extraction.provider import (
    ExtractionTask,
    ProviderRequest,
    ProviderResponse,
)


class MockStructuredOutputProvider:
    name = "deterministic_mock"
    kind = "mock"

    def __init__(self, responses=None, failures=None, registry=None) -> None:
        self._responses = list(responses or [])
        self._failures = list(failures or [])
        self._registry = dict(registry or {})
        self.requests: list[ProviderRequest] = []

    @classmethod
    def with_responses(cls, responses: Iterable[str]) -> "MockStructuredOutputProvider":
        return cls(responses=responses)

    @classmethod
    def with_failures(cls, failures: Iterable[Exception]) -> "MockStructuredOutputProvider":
        return cls(failures=failures)

    @classmethod
    def from_fixture_directory(cls, root: Path) -> "MockStructuredOutputProvider":
        registry = {}
        pairs = (
            (ExtractionTask.CANDIDATE, "candidate_matching_resume.txt", "candidate_matching_output.json"),
            (ExtractionTask.CANDIDATE, "candidate_sparse_resume.txt", "candidate_sparse_output.json"),
            (ExtractionTask.JOB, "job_matching_engineer.txt", "job_matching_engineer_output.json"),
            (ExtractionTask.JOB, "job_sparse_ai_role.txt", "job_sparse_ai_role_output.json"),
        )
        for task, source_name, output_name in pairs:
            source = (root / source_name).read_text(encoding="utf-8")
            registry[(task, hashlib.sha256(source.encode("utf-8")).hexdigest())] = (
                root / output_name
            ).read_text(encoding="utf-8")
        return cls(registry=registry)

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if self._failures:
            raise self._failures.pop(0)
        if self._responses:
            raw_output = self._responses.pop(0)
        else:
            fingerprint = hashlib.sha256(request.source_text.encode("utf-8")).hexdigest()
            key = (request.task, fingerprint)
            if key not in self._registry:
                raise MockInputNotSupportedError(
                    "The deterministic mock provider has no registered output for this input"
                )
            raw_output = self._registry[key]
        return ProviderResponse(raw_output)
