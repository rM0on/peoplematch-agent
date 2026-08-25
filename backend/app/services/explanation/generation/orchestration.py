from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Callable
from uuid import uuid4

from app.exceptions import (
    ExplanationRunNotFoundError,
    MatchRunConflictError,
    MatchRunNotFoundError,
)
from app.models.explanation_run import ExplanationRunModel
from app.services.explanation.generation.errors import (
    ExplanationGenerationFailedError,
    ExplanationGroundingError,
    ExplanationPlanParseError,
)
from app.services.explanation.generation.provider import (
    ExplanationProviderConfigurationError,
    ExplanationProviderError,
    ExplanationProviderHttpError,
    ExplanationProviderMalformedResponseError,
    ExplanationProviderTimeoutError,
    ExplanationProviderTransportError,
)
from app.schemas.explanation_generation import (
    explanation_detail_from_model,
    explanation_summary_from_model,
)


_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
_SAFE_FAILURE_DETAILS = {
    "provider_timeout": "Explanation provider timed out",
    "provider_transport": "Explanation provider transport failed",
    "provider_http_status": "Explanation provider request failed",
    "malformed_response": "Explanation provider response was malformed",
    "invalid_output": "Explanation provider output was invalid",
    "grounding_failure": "Explanation plan failed grounding validation",
    "provider_configuration": "Explanation provider is not configured",
    "internal_error": "Explanation generation failed",
    "evidence_build_failed": "Historical explanation evidence could not be built",
    "explanation_persistence_failed": "Atomic explanation persistence failed",
    "attempt_audit_failed": "Explanation attempt audit persistence failed",
}


@dataclass(frozen=True)
class ExplanationGenerationResult:
    explanation_run_id: str
    match_run_id: str
    status: str
    requested_top_k: int
    effective_top_k: int
    explanation_count: int
    attempt_count: int
    repaired: bool
    error_code: None = None
    error_detail_safe: None = None
    explanations: tuple[dict, ...] = ()


def _safe_observed_model(value: str | None) -> str | None:
    if value is None or _SAFE_MODEL.fullmatch(value) is None:
        return None
    return value


def _provider_failure_code(error: Exception) -> str:
    if isinstance(error, ExplanationProviderTimeoutError):
        return "provider_timeout"
    if isinstance(error, ExplanationProviderTransportError):
        return "provider_transport"
    if isinstance(error, ExplanationProviderHttpError):
        return "provider_http_status"
    if isinstance(error, ExplanationProviderMalformedResponseError):
        return "malformed_response"
    if isinstance(error, ExplanationProviderConfigurationError):
        return "provider_configuration"
    if isinstance(error, ExplanationPlanParseError):
        return "invalid_output"
    if isinstance(error, ExplanationGroundingError):
        return "grounding_failure"
    return "internal_error"


class ExplanationGenerationService:
    """Coordinate short DB transitions around untrusted provider calls."""

    def __init__(
        self,
        *,
        match_run_repository,
        explanation_repository,
        attempt_repository,
        provider,
        pipeline,
        query_repository=None,
        max_attempts: int = 2,
        id_factory: Callable[[], str] = lambda: str(uuid4()),
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.match_run_repository = match_run_repository
        self.explanation_repository = explanation_repository
        self.attempt_repository = attempt_repository
        self.provider = provider
        self.pipeline = pipeline
        self.query_repository = query_repository
        if type(max_attempts) is not int or max_attempts not in (1, 2):
            raise ValueError("Explanation max attempts must be one or two")
        self.max_attempts = max_attempts
        self.id_factory = id_factory
        self.clock = clock

    async def _fail_run(self, explanation_run_id: str, code: str) -> None:
        detail = _SAFE_FAILURE_DETAILS.get(code, _SAFE_FAILURE_DETAILS["internal_error"])
        await self.explanation_repository.finalize_failed(
            explanation_run_id,
            completed_at=self.clock(),
            error_code=code,
            error_detail_safe=detail,
        )

    async def _abort_for_attempt_audit(
        self,
        explanation_run_id: str,
        attempt_number: int,
    ) -> None:
        try:
            await self.attempt_repository.abort_attempt(
                explanation_run_id,
                attempt_number=attempt_number,
                completed_at=self.clock(),
            )
        except Exception:
            # Parent truth is the terminal safety boundary.  A persistently
            # unavailable audit store must not keep the parent RUNNING.
            pass
        await self._fail_run(explanation_run_id, "attempt_audit_failed")
        raise ExplanationGenerationFailedError(
            explanation_run_id=explanation_run_id,
            failure_code="attempt_audit_failed",
        )

    async def _finish_attempt(
        self,
        explanation_run_id: str,
        **values,
    ) -> None:
        try:
            await self.attempt_repository.finish_attempt(
                explanation_run_id,
                **values,
            )
        except Exception:
            await self._abort_for_attempt_audit(
                explanation_run_id,
                values["attempt_number"],
            )

    async def generate(
        self,
        match_run_id: str,
        *,
        requested_top_k: int,
        request_id: str,
    ) -> ExplanationGenerationResult:
        historical_run = await self.match_run_repository.get_by_run_id(match_run_id)
        if historical_run is None:
            raise MatchRunNotFoundError(f"Match run {match_run_id} was not found")
        if historical_run.status != "COMPLETED":
            raise MatchRunConflictError(
                "Explanations require a completed historical MatchRun"
            )

        descriptor = self.provider.descriptor
        explanation_run_id = self.id_factory()
        await self.explanation_repository.create_running(
            ExplanationRunModel(
                explanation_run_id=explanation_run_id,
                match_run_id=match_run_id,
                request_id=request_id,
                status="RUNNING",
                requested_top_k=requested_top_k,
                effective_top_k=None,
                explanation_count=0,
                attempt_count=0,
                repaired=False,
                provider_kind=descriptor.kind,
                provider_name=descriptor.name,
                configured_model=descriptor.configured_model,
                provider_configuration_fingerprint=(
                    descriptor.configuration_fingerprint
                ),
                prompt_version=self.pipeline.prompt_version,
                prompt_fingerprint=self.pipeline.prompt_fingerprint,
                completed_at=None,
                error_code=None,
                error_detail_safe=None,
            )
        )
        try:
            prepared = self.pipeline.prepare(
                historical_run,
                requested_top_k=requested_top_k,
            )
            await self.explanation_repository.store_evidence(
                explanation_run_id,
                evidence_bundle=prepared.evidence_bundle,
                provider_evidence=prepared.provider_evidence,
            )
        except Exception:
            await self._fail_run(explanation_run_id, "evidence_build_failed")
            raise ExplanationGenerationFailedError(
                explanation_run_id=explanation_run_id,
                failure_code="evidence_build_failed",
            ) from None

        request = prepared.initial_request
        rendered = None
        observed_model = None
        final_code = "internal_error"
        attempt_count = 0
        for attempt_number in range(1, self.max_attempts + 1):
            attempt_count = attempt_number
            try:
                await self.attempt_repository.start_attempt(
                    explanation_run_id,
                    attempt_number=attempt_number,
                    provider_kind=descriptor.kind,
                    provider_name=descriptor.name,
                    configured_model=descriptor.configured_model,
                    provider_configuration_fingerprint=(
                        descriptor.configuration_fingerprint
                    ),
                    started_at=self.clock(),
                )
            except Exception:
                await self._abort_for_attempt_audit(
                    explanation_run_id,
                    attempt_number,
                )
            try:
                response = await self.provider.generate(request)
                observed_model = _safe_observed_model(response.observed_model)
                rendered = self.pipeline.validate_and_render(
                    response.content,
                    prepared,
                )
            except (ExplanationPlanParseError, ExplanationGroundingError) as error:
                final_code = _provider_failure_code(error)
                await self._finish_attempt(
                    explanation_run_id,
                    attempt_number=attempt_number,
                    status="FAILED",
                    error_category=final_code,
                    observed_model=observed_model,
                    completed_at=self.clock(),
                )
                if attempt_number < self.max_attempts:
                    request = self.pipeline.repair_request(
                        prepared,
                        error_category=final_code,
                    )
                    continue
                break
            except ExplanationProviderError as error:
                final_code = _provider_failure_code(error)
                await self._finish_attempt(
                    explanation_run_id,
                    attempt_number=attempt_number,
                    status="FAILED",
                    error_category=final_code,
                    observed_model=None,
                    completed_at=self.clock(),
                )
                break
            except Exception:
                final_code = "internal_error"
                await self._finish_attempt(
                    explanation_run_id,
                    attempt_number=attempt_number,
                    status="FAILED",
                    error_category=final_code,
                    observed_model=observed_model,
                    completed_at=self.clock(),
                )
                break
            else:
                await self._finish_attempt(
                    explanation_run_id,
                    attempt_number=attempt_number,
                    status="COMPLETED",
                    error_category=None,
                    observed_model=observed_model,
                    completed_at=self.clock(),
                )
                break

        if rendered is None:
            await self._fail_run(explanation_run_id, final_code)
            raise ExplanationGenerationFailedError(
                explanation_run_id=explanation_run_id,
                failure_code=final_code,
            )

        try:
            explanations = self.pipeline.persistence_models(
                rendered,
                explanation_run_id=explanation_run_id,
                match_run=historical_run,
            )
            await self.explanation_repository.finalize_completed(
                explanation_run_id,
                explanations,
                completed_at=self.clock(),
                provider_kind=descriptor.kind,
                provider_name=descriptor.name,
                configured_model=descriptor.configured_model,
                observed_model=observed_model,
                provider_configuration_fingerprint=(
                    descriptor.configuration_fingerprint
                ),
                prompt_version=self.pipeline.prompt_version,
                prompt_fingerprint=self.pipeline.prompt_fingerprint,
                attempt_count=attempt_count,
                repaired=attempt_count > 1,
            )
        except Exception:
            await self._fail_run(
                explanation_run_id,
                "explanation_persistence_failed",
            )
            raise ExplanationGenerationFailedError(
                explanation_run_id=explanation_run_id,
                failure_code="explanation_persistence_failed",
            ) from None
        return ExplanationGenerationResult(
            explanation_run_id=explanation_run_id,
            match_run_id=match_run_id,
            status="COMPLETED",
            requested_top_k=requested_top_k,
            effective_top_k=prepared.effective_top_k,
            explanation_count=len(explanations),
            attempt_count=attempt_count,
            repaired=attempt_count > 1,
            explanations=tuple(
                getattr(item, "validated_output_json", {})
                for item in explanations
            ),
        )

    async def get(self, explanation_run_id: str):
        if self.query_repository is None:
            raise RuntimeError("Explanation query repository is not configured")
        model = await self.query_repository.get_detail(explanation_run_id)
        if model is None:
            raise ExplanationRunNotFoundError(
                f"Explanation run {explanation_run_id} was not found"
            )
        return explanation_detail_from_model(model)

    async def list(self, match_run_id: str, *, limit: int, offset: int):
        if self.query_repository is None:
            raise RuntimeError("Explanation query repository is not configured")
        if not await self.query_repository.match_run_exists(match_run_id):
            raise MatchRunNotFoundError(f"Match run {match_run_id} was not found")
        items, total = await self.query_repository.list_for_match_run(
            match_run_id,
            limit=limit,
            offset=offset,
        )
        return [explanation_summary_from_model(item) for item in items], total


__all__ = ["ExplanationGenerationResult", "ExplanationGenerationService"]
