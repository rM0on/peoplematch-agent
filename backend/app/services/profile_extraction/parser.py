from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Optional, Type

from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger
from app.exceptions import (
    MockInputNotSupportedError,
    ProviderOutputInvalidError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.extraction import (
    CandidateExtractionDraft,
    CandidateParseData,
    ExtractionMetadata,
    JobExtractionDraft,
    JobParseData,
)
from app.services.profile_extraction.prompts import (
    build_candidate_prompt,
    build_job_prompt,
)
from app.services.profile_extraction.provider import (
    ExtractionTask,
    ProviderDescriptor,
    ProviderRequest,
    StructuredOutputProvider,
)


logger = get_logger("extraction")


def _compact_validation_feedback(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors(include_url=False, include_context=False)[:8]:
        location = ".".join(str(value) for value in error["loc"])
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


class ProfileExtractionService:
    def __init__(
        self,
        provider: StructuredOutputProvider,
        provider_descriptor: ProviderDescriptor,
        *,
        max_attempts: int = 2,
        timeout_seconds: float = 10,
        candidate_service=None,
        job_service=None,
    ) -> None:
        if not 1 <= max_attempts <= 2:
            raise ValueError("max_attempts must be one or two")
        self.provider = provider
        self.provider_descriptor = provider_descriptor
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds
        self.candidate_service = candidate_service
        self.job_service = job_service

    async def extract_candidate(
        self, source: str, *, request_id: Optional[str] = None
    ) -> CandidateParseData:
        draft, metadata = await self._extract(
            source,
            ExtractionTask.CANDIDATE,
            CandidateExtractionDraft,
            request_id=request_id,
        )
        return CandidateParseData(draft=draft, record=None, extraction=metadata)

    async def extract_job(
        self, source: str, *, request_id: Optional[str] = None
    ) -> JobParseData:
        draft, metadata = await self._extract(
            source,
            ExtractionTask.JOB,
            JobExtractionDraft,
            request_id=request_id,
        )
        return JobParseData(draft=draft, record=None, extraction=metadata)

    async def parse_candidate(
        self,
        source: str,
        *,
        persist: bool,
        request_id: Optional[str] = None,
    ) -> CandidateParseData:
        result = await self.extract_candidate(source, request_id=request_id)
        if not persist:
            return result
        if self.candidate_service is None:
            raise ProviderUnavailableError("Candidate persistence service is unavailable")
        record = await self.candidate_service.create_from_extraction(
            result.draft,
            raw_text=source,
            data_origin=self.provider_descriptor.data_origin,
        )
        return result.model_copy(
            update={
                "record": record,
                "extraction": result.extraction.model_copy(update={"persisted": True}),
            }
        )

    async def parse_job(
        self,
        source: str,
        *,
        persist: bool,
        request_id: Optional[str] = None,
    ) -> JobParseData:
        result = await self.extract_job(source, request_id=request_id)
        if not persist:
            return result
        if self.job_service is None:
            raise ProviderUnavailableError("Job persistence service is unavailable")
        record = await self.job_service.create_from_extraction(
            result.draft,
            raw_jd=source,
            data_origin=self.provider_descriptor.data_origin,
        )
        return result.model_copy(
            update={
                "record": record,
                "extraction": result.extraction.model_copy(update={"persisted": True}),
            }
        )

    async def _extract(
        self,
        source: str,
        task: ExtractionTask,
        schema: Type[BaseModel],
        *,
        request_id: Optional[str] = None,
    ):
        feedback: Optional[str] = None
        fingerprint = hashlib.sha256(source.encode("utf-8")).hexdigest()
        for attempt in range(1, self.max_attempts + 1):
            prompt = (
                build_candidate_prompt(source, feedback)
                if task == ExtractionTask.CANDIDATE
                else build_job_prompt(source, feedback)
            )
            request = ProviderRequest(
                task=task,
                source_text=source,
                prompt_version=prompt.prompt_version,
                prompt_fingerprint=prompt.prompt_fingerprint,
                system_message=prompt.system_message,
                user_message=prompt.user_message,
                output_contract=prompt.output_contract,
                attempt=attempt,
                validation_feedback=feedback,
            )
            try:
                response = await asyncio.wait_for(
                    self.provider.generate(request), timeout=self.timeout_seconds
                )
            except MockInputNotSupportedError:
                logger.warning(
                    "Structured extraction failed request_id=%s "
                    "input_fingerprint=%s provider=%s task=%s attempt=%s "
                    "error_type=mock_input_not_supported",
                    request_id,
                    fingerprint,
                    self.provider_descriptor.name,
                    task.value,
                    attempt,
                )
                raise
            except (asyncio.TimeoutError, TimeoutError) as exc:
                logger.warning(
                    "Structured extraction failed request_id=%s "
                    "input_fingerprint=%s provider=%s task=%s attempt=%s "
                    "error_type=provider_timeout",
                    request_id,
                    fingerprint,
                    self.provider_descriptor.name,
                    task.value,
                    attempt,
                )
                raise ProviderTimeoutError("Structured output provider timed out") from exc
            except (
                ProviderTimeoutError,
                ProviderRateLimitError,
                ProviderUnavailableError,
                ProviderOutputInvalidError,
            ) as exc:
                logger.warning(
                    "Structured extraction failed request_id=%s "
                    "input_fingerprint=%s provider=%s task=%s attempt=%s "
                    "error_type=%s",
                    request_id,
                    fingerprint,
                    self.provider_descriptor.name,
                    task.value,
                    attempt,
                    exc.code,
                )
                raise
            except Exception as exc:
                logger.warning(
                    "Structured extraction failed request_id=%s "
                    "input_fingerprint=%s provider=%s task=%s attempt=%s "
                    "error_type=provider_unavailable",
                    request_id,
                    fingerprint,
                    self.provider_descriptor.name,
                    task.value,
                    attempt,
                )
                raise ProviderUnavailableError(
                    "Structured output provider is unavailable"
                ) from exc
            try:
                decoded = json.loads(response.raw_output)
            except json.JSONDecodeError as exc:
                feedback = f"invalid JSON: {exc.msg}"
                continue
            try:
                validation_context = None
                if schema in {CandidateExtractionDraft, JobExtractionDraft}:
                    validation_context = {"data_origin": self.provider_descriptor.data_origin}
                draft = schema.model_validate(decoded, context=validation_context)
            except ValidationError as exc:
                feedback = _compact_validation_feedback(exc)
                continue
            logger.info(
                "Structured extraction validated request_id=%s "
                "input_fingerprint=%s provider=%s provider_kind=%s task=%s "
                "attempts=%s repaired=%s",
                request_id,
                fingerprint,
                self.provider_descriptor.name,
                self.provider_descriptor.kind,
                task.value,
                attempt,
                attempt > 1,
                extra={
                    "input_fingerprint": fingerprint,
                    "provider": self.provider_descriptor.name,
                    "provider_kind": self.provider_descriptor.kind,
                    "task": task.value,
                    "attempts": attempt,
                    "repaired": attempt > 1,
                    "request_id": request_id,
                },
            )
            return draft, ExtractionMetadata(
                provider=self.provider_descriptor.name,
                provider_kind=self.provider_descriptor.kind,
                prompt_version=prompt.prompt_version,
                prompt_fingerprint=prompt.prompt_fingerprint,
                attempts=attempt,
                repaired=attempt > 1,
                persisted=False,
                input_fingerprint=fingerprint,
            )
        logger.warning(
            "Structured extraction failed request_id=%s input_fingerprint=%s "
            "provider=%s task=%s attempts=%s error_type=provider_output_invalid",
            request_id,
            fingerprint,
            self.provider_descriptor.name,
            task.value,
            self.max_attempts,
        )
        raise ProviderOutputInvalidError(
            f"Provider output failed validation after {self.max_attempts} attempts"
        )
