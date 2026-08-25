from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from app.exceptions import ExplanationRunConflictError, ExplanationRunNotFoundError
from app.models.explanation_attempt import ExplanationGenerationAttemptModel
from app.models.explanation_run import ExplanationRunModel
from app.schemas.explanations import ExplanationRunStatus


_ERROR_CATEGORIES = {
    "provider_timeout",
    "provider_transport",
    "provider_http_status",
    "malformed_response",
    "invalid_output",
    "grounding_failure",
    "provider_configuration",
    "internal_error",
}


class ExplanationAttemptRepository:
    """Own short, independent attempt-audit transactions."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    @staticmethod
    async def _lock_running_parent(
        session, explanation_run_id: str
    ) -> ExplanationRunModel:
        parent = await session.scalar(
            select(ExplanationRunModel)
            .where(ExplanationRunModel.explanation_run_id == explanation_run_id)
            .with_for_update()
        )
        if parent is None:
            raise ExplanationRunNotFoundError(
                f"Explanation run {explanation_run_id} was not found"
            )
        if parent.status != ExplanationRunStatus.RUNNING.value:
            raise ExplanationRunConflictError("Terminal explanation runs are immutable")
        return parent

    async def start_attempt(
        self,
        explanation_run_id: str,
        *,
        attempt_number: int,
        provider_kind: str,
        provider_name: str,
        configured_model: str,
        provider_configuration_fingerprint: str,
        started_at: datetime,
    ) -> None:
        if type(attempt_number) is not int or attempt_number not in (1, 2):
            raise ExplanationRunConflictError("Attempt number must be 1 or 2")
        async with self.session_factory() as session:
            async with session.begin():
                parent = await self._lock_running_parent(session, explanation_run_id)
                if attempt_number != parent.attempt_count + 1:
                    raise ExplanationRunConflictError(
                        "Explanation attempts must be consecutive"
                    )
                expected_provenance = (
                    parent.provider_kind,
                    parent.provider_name,
                    parent.configured_model,
                    parent.provider_configuration_fingerprint,
                )
                supplied_provenance = (
                    provider_kind,
                    provider_name,
                    configured_model,
                    provider_configuration_fingerprint,
                )
                if expected_provenance != supplied_provenance:
                    raise ExplanationRunConflictError(
                        "Attempt provider provenance conflicts with its parent"
                    )
                existing = await session.scalar(
                    select(ExplanationGenerationAttemptModel.id).where(
                        ExplanationGenerationAttemptModel.explanation_run_id
                        == explanation_run_id,
                        ExplanationGenerationAttemptModel.attempt_number
                        == attempt_number,
                    )
                )
                if existing is not None:
                    raise ExplanationRunConflictError(
                        "Explanation attempt number already exists"
                    )
                session.add(
                    ExplanationGenerationAttemptModel(
                        explanation_run_id=explanation_run_id,
                        attempt_number=attempt_number,
                        status="RUNNING",
                        error_category=None,
                        provider_kind=provider_kind,
                        provider_name=provider_name,
                        configured_model=configured_model,
                        observed_model=None,
                        provider_configuration_fingerprint=(
                            provider_configuration_fingerprint
                        ),
                        started_at=started_at,
                        completed_at=None,
                    )
                )
                parent.attempt_count = attempt_number
                parent.repaired = attempt_number > 1

    async def finish_attempt(
        self,
        explanation_run_id: str,
        *,
        attempt_number: int,
        status: str,
        error_category: str | None,
        observed_model: str | None,
        completed_at: datetime,
    ) -> None:
        if status not in {"COMPLETED", "FAILED"}:
            raise ExplanationRunConflictError("Attempt terminal status is invalid")
        if (status == "COMPLETED" and error_category is not None) or (
            status == "FAILED" and error_category not in _ERROR_CATEGORIES
        ):
            raise ExplanationRunConflictError("Attempt error category is invalid")
        async with self.session_factory() as session:
            async with session.begin():
                parent = await self._lock_running_parent(session, explanation_run_id)
                attempt = await session.scalar(
                    select(ExplanationGenerationAttemptModel)
                    .where(
                        ExplanationGenerationAttemptModel.explanation_run_id
                        == explanation_run_id,
                        ExplanationGenerationAttemptModel.attempt_number
                        == attempt_number,
                    )
                    .with_for_update()
                )
                if attempt is None or attempt.status != "RUNNING":
                    raise ExplanationRunConflictError(
                        "Explanation attempt is not mutable"
                    )
                attempt.status = status
                attempt.error_category = error_category
                attempt.observed_model = observed_model
                attempt.completed_at = completed_at
                if observed_model is not None:
                    parent.observed_model = observed_model

    async def abort_attempt(
        self,
        explanation_run_id: str,
        *,
        attempt_number: int,
        completed_at: datetime,
    ) -> None:
        """Best-effort terminalization after the normal audit path failed."""

        if type(attempt_number) is not int or attempt_number not in (1, 2):
            raise ExplanationRunConflictError("Attempt number must be 1 or 2")
        async with self.session_factory() as session:
            async with session.begin():
                await self._lock_running_parent(session, explanation_run_id)
                attempt = await session.scalar(
                    select(ExplanationGenerationAttemptModel)
                    .where(
                        ExplanationGenerationAttemptModel.explanation_run_id
                        == explanation_run_id,
                        ExplanationGenerationAttemptModel.attempt_number
                        == attempt_number,
                    )
                    .with_for_update()
                )
                if attempt is None or attempt.status != "RUNNING":
                    return
                attempt.status = "FAILED"
                attempt.error_category = "internal_error"
                attempt.completed_at = completed_at

    async def list_attempts(
        self, explanation_run_id: str
    ) -> Sequence[ExplanationGenerationAttemptModel]:
        async with self.session_factory() as session:
            return (
                await session.scalars(
                    select(ExplanationGenerationAttemptModel)
                    .where(
                        ExplanationGenerationAttemptModel.explanation_run_id
                        == explanation_run_id
                    )
                    .order_by(ExplanationGenerationAttemptModel.attempt_number)
                )
            ).all()


__all__ = ["ExplanationAttemptRepository"]
