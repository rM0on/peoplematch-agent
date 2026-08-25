from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from tests.test_explanation_evidence_engine import (
    _PHASE8_RESULT_FIELDS,
    _refresh_candidate_snapshot_fingerprint,
    _refresh_ranking_snapshot_fingerprint,
    _refresh_result_fingerprint,
    _run,
)
from tests.test_explanation_postgres import (
    _alembic,
    _engine_and_factory,
    _source_run,
    _truncate,
)


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


async def _persist_valid_historical_run(factory, suffix: str):
    from app.models.match_run import MatchResultModel, MatchRunModel, RunStepModel

    run_id, job_id, candidate_ids, _ = await _source_run(
        factory,
        suffix,
        candidate_count=2,
    )
    historical = _run(run_id=run_id)
    historical.requested_job_id = job_id
    historical.job_id = job_id
    historical.ranking_input_snapshot["job_id"] = job_id
    for source, candidate_id in zip(historical.results, candidate_ids):
        source.run_id = run_id
        source.candidate_id = candidate_id
        source.candidate_input_snapshot["candidate_id"] = candidate_id
        _refresh_candidate_snapshot_fingerprint(source)
    _refresh_ranking_snapshot_fingerprint(historical)
    _refresh_result_fingerprint(historical)

    now = datetime(2026, 8, 25, tzinfo=timezone.utc)
    async with factory() as session:
        async with session.begin():
            run = await session.get(MatchRunModel, run_id)
            for name in (
                "requested_job_id",
                "job_id",
                "request_id",
                "ranking_variant",
                "status",
                "request_parameters",
                "workflow_version",
                "workflow_fingerprint",
                "ranking_input_contract_version",
                "ranking_input_fingerprint",
                "ranking_input_snapshot",
                "retrieval_document_version",
                "retrieval_configuration_fingerprint",
                "retrieval_provenance",
                "feature_version",
                "feature_fingerprint",
                "ranker_version",
                "ranker_model_sha256",
                "ce_provenance",
                "result_count",
                "result_fingerprint",
            ):
                setattr(run, name, getattr(historical, name))
            results = (
                await session.scalars(
                    select(MatchResultModel)
                    .where(MatchResultModel.run_id == run_id)
                    .order_by(MatchResultModel.result_rank)
                )
            ).all()
            for stored, source in zip(results, historical.results):
                for name in _PHASE8_RESULT_FIELDS:
                    setattr(stored, name, getattr(source, name))
                stored.candidate_input_snapshot = source.candidate_input_snapshot
                source.id = stored.id
            session.add_all(
                [
                    RunStepModel(
                        run_id=run_id,
                        sequence=step.sequence,
                        step_name=step.step_name,
                        status=step.status,
                        started_at=now,
                        finished_at=now,
                        duration_ms=0.0,
                        input_refs={},
                        output_refs={},
                        contract_version=step.contract_version,
                        error_code=None,
                        error_detail_safe=None,
                    )
                    for step in historical.steps
                ]
            )
    return run_id


def _service(factory, *, provider, explanation_run_id: str):
    from app.repositories.explanation_attempt_repository import (
        ExplanationAttemptRepository,
    )
    from app.repositories.explanation_query_repository import ExplanationQueryRepository
    from app.repositories.explanation_run_repository import ExplanationRunRepository
    from app.repositories.match_run_repository import MatchRunRepository
    from app.services.explanation.generation.orchestration import (
        ExplanationGenerationService,
    )
    from app.services.explanation.generation.pipeline import ExplanationGenerationPipeline

    return ExplanationGenerationService(
        match_run_repository=MatchRunRepository(factory),
        explanation_repository=ExplanationRunRepository(factory),
        attempt_repository=ExplanationAttemptRepository(factory),
        query_repository=ExplanationQueryRepository(factory),
        provider=provider,
        pipeline=ExplanationGenerationPipeline(max_output_tokens=1024),
        id_factory=lambda: explanation_run_id,
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
    )


def test_postgres_phase94_upgrade_is_additive_and_matches_attempt_model() -> None:
    async def scenario():
        from app.models.explanation_attempt import ExplanationGenerationAttemptModel

        engine, _factory = await _engine_and_factory()
        try:
            async with engine.connect() as connection:
                table_names = await connection.run_sync(
                    lambda sync: set(inspect(sync).get_table_names())
                )
                columns = await connection.run_sync(
                    lambda sync: {
                        item["name"]
                        for item in inspect(sync).get_columns(
                            "explanation_generation_attempts"
                        )
                    }
                )
            assert "explanation_generation_attempts" in table_names
            assert columns == set(
                ExplanationGenerationAttemptModel.__table__.columns.keys()
            )
        finally:
            await engine.dispose()

    _alembic("base", downgrade=True)
    _alembic("20260819_0003")
    engine, _factory = asyncio.run(_engine_and_factory())

    async def absent():
        try:
            async with engine.connect() as connection:
                names = await connection.run_sync(
                    lambda sync: set(inspect(sync).get_table_names())
                )
            assert "explanation_generation_attempts" not in names
        finally:
            await engine.dispose()

    asyncio.run(absent())
    _alembic("head")
    asyncio.run(scenario())


def test_postgres_generation_success_persists_grounded_outputs_and_bounded_attempt() -> None:
    async def scenario():
        from app.models.explanation_attempt import ExplanationGenerationAttemptModel
        from app.models.explanation_run import MatchExplanationModel
        from app.services.explanation.generation.mock_provider import (
            DeterministicExplanationProvider,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id = await _persist_valid_historical_run(factory, "941")
            explanation_run_id = "10000000-0000-0000-0000-000000000941"
            service = _service(
                factory,
                provider=DeterministicExplanationProvider(),
                explanation_run_id=explanation_run_id,
            )

            result = await service.generate(
                run_id,
                requested_top_k=2,
                request_id="phase94-postgres-success",
            )
            detail = await service.get(explanation_run_id)

            assert result.status == detail.status == "COMPLETED"
            assert result.explanation_count == len(detail.explanations) == 2
            assert result.attempt_count == 1
            async with factory() as session:
                attempt = await session.scalar(
                    select(ExplanationGenerationAttemptModel).where(
                        ExplanationGenerationAttemptModel.explanation_run_id
                        == explanation_run_id
                    )
                )
                child_count = await session.scalar(
                    select(func.count())
                    .select_from(MatchExplanationModel)
                    .where(
                        MatchExplanationModel.explanation_run_id
                        == explanation_run_id
                    )
                )
            assert attempt.status == "COMPLETED"
            assert attempt.attempt_number == 1
            assert attempt.error_category is None
            assert child_count == 2
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_generation_repair_and_provider_failure_are_durable() -> None:
    async def scenario():
        from app.models.explanation_attempt import ExplanationGenerationAttemptModel
        from app.models.explanation_run import ExplanationRunModel, MatchExplanationModel
        from app.services.explanation.generation.errors import (
            ExplanationGenerationFailedError,
        )
        from app.services.explanation.generation.mock_provider import (
            DeterministicExplanationProvider,
        )
        from app.services.explanation.generation.provider import (
            ExplanationProviderResponse,
            ExplanationProviderTimeoutError,
        )

        class RepairProvider(DeterministicExplanationProvider):
            def __init__(self):
                self.calls = 0

            async def generate(self, request):
                self.calls += 1
                if self.calls == 1:
                    return ExplanationProviderResponse(
                        content="{}",
                        observed_model=self.descriptor.configured_model,
                    )
                return await super().generate(request)

        class TimeoutProvider(DeterministicExplanationProvider):
            async def generate(self, request):
                raise ExplanationProviderTimeoutError()

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            repair_match_run_id = await _persist_valid_historical_run(factory, "942")
            repair_run_id = "10000000-0000-0000-0000-000000000942"
            repair_service = _service(
                factory,
                provider=RepairProvider(),
                explanation_run_id=repair_run_id,
            )
            repaired = await repair_service.generate(
                repair_match_run_id,
                requested_top_k=1,
                request_id="phase94-postgres-repair",
            )
            assert repaired.attempt_count == 2
            assert repaired.repaired is True

            timeout_match_run_id = await _persist_valid_historical_run(factory, "943")
            timeout_run_id = "10000000-0000-0000-0000-000000000943"
            timeout_service = _service(
                factory,
                provider=TimeoutProvider(),
                explanation_run_id=timeout_run_id,
            )
            with pytest.raises(ExplanationGenerationFailedError):
                await timeout_service.generate(
                    timeout_match_run_id,
                    requested_top_k=1,
                    request_id="phase94-postgres-timeout",
                )
            failed_detail = await timeout_service.get(timeout_run_id)
            failed_summaries, failed_total = await timeout_service.list(
                timeout_match_run_id,
                limit=10,
                offset=0,
            )

            async with factory() as session:
                repair_attempts = (
                    await session.scalars(
                        select(ExplanationGenerationAttemptModel)
                        .where(
                            ExplanationGenerationAttemptModel.explanation_run_id
                            == repair_run_id
                        )
                        .order_by(ExplanationGenerationAttemptModel.attempt_number)
                    )
                ).all()
                failed = await session.get(ExplanationRunModel, timeout_run_id)
                timeout_attempt = await session.scalar(
                    select(ExplanationGenerationAttemptModel).where(
                        ExplanationGenerationAttemptModel.explanation_run_id
                        == timeout_run_id
                    )
                )
                timeout_children = await session.scalar(
                    select(func.count())
                    .select_from(MatchExplanationModel)
                    .where(MatchExplanationModel.explanation_run_id == timeout_run_id)
                )
            assert [(item.status, item.error_category) for item in repair_attempts] == [
                ("FAILED", "invalid_output"),
                ("COMPLETED", None),
            ]
            assert failed.status == "FAILED"
            assert failed.error_code == "provider_timeout"
            assert "provider" in failed.error_detail_safe.lower()
            assert failed.attempt_count == 1
            assert failed.repaired is False
            assert failed.provider_kind == "deterministic"
            assert failed.provider_name == "mock"
            assert failed.configured_model == "deterministic-explanation-planner-v1"
            assert failed.provider_configuration_fingerprint is not None
            assert failed.prompt_version == "explanation_prompt_v1"
            assert failed.prompt_fingerprint is not None
            assert timeout_attempt.status == "FAILED"
            assert timeout_attempt.error_category == "provider_timeout"
            assert timeout_children == 0
            assert failed_detail.status == "FAILED"
            assert failed_detail.attempt_count == 1
            assert failed_detail.repaired is False
            assert failed_detail.provider_kind == "deterministic"
            assert failed_detail.provider_name == "mock"
            assert failed_total == 1
            assert failed_summaries[0].attempt_count == 1
            assert failed_summaries[0].repaired is False
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_two_failed_attempts_preserve_truthful_parent_and_audit() -> None:
    async def scenario():
        from app.models.explanation_attempt import ExplanationGenerationAttemptModel
        from app.models.explanation_run import ExplanationRunModel, MatchExplanationModel
        from app.services.explanation.generation.errors import (
            ExplanationGenerationFailedError,
        )
        from app.services.explanation.generation.mock_provider import (
            DeterministicExplanationProvider,
        )
        from app.services.explanation.generation.provider import (
            ExplanationProviderResponse,
        )

        class InvalidTwiceProvider(DeterministicExplanationProvider):
            def __init__(self):
                self.calls = 0

            async def generate(self, request):
                self.calls += 1
                return ExplanationProviderResponse(
                    content="{}",
                    observed_model=self.descriptor.configured_model,
                )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            match_run_id = await _persist_valid_historical_run(factory, "946")
            explanation_run_id = "10000000-0000-0000-0000-000000000946"
            provider = InvalidTwiceProvider()
            service = _service(
                factory,
                provider=provider,
                explanation_run_id=explanation_run_id,
            )

            with pytest.raises(ExplanationGenerationFailedError) as exc_info:
                await service.generate(
                    match_run_id,
                    requested_top_k=1,
                    request_id="phase94-postgres-two-invalid-attempts",
                )

            assert exc_info.value.details["failure_code"] == "invalid_output"
            assert provider.calls == 2
            async with factory() as session:
                parent = await session.get(ExplanationRunModel, explanation_run_id)
                attempts = (
                    await session.scalars(
                        select(ExplanationGenerationAttemptModel)
                        .where(
                            ExplanationGenerationAttemptModel.explanation_run_id
                            == explanation_run_id
                        )
                        .order_by(ExplanationGenerationAttemptModel.attempt_number)
                    )
                ).all()
                child_count = await session.scalar(
                    select(func.count())
                    .select_from(MatchExplanationModel)
                    .where(
                        MatchExplanationModel.explanation_run_id
                        == explanation_run_id
                    )
                )

            assert parent.status == "FAILED"
            assert parent.error_code == "invalid_output"
            assert parent.attempt_count == 2
            assert parent.repaired is True
            assert parent.provider_kind == "deterministic"
            assert parent.provider_name == "mock"
            assert parent.prompt_version == "explanation_prompt_v1"
            assert parent.prompt_fingerprint is not None
            assert [item.attempt_number for item in attempts] == [1, 2]
            assert [item.status for item in attempts] == ["FAILED", "FAILED"]
            assert [item.error_category for item in attempts] == [
                "invalid_output",
                "invalid_output",
            ]
            assert all(item.provider_kind == "deterministic" for item in attempts)
            assert all(item.provider_name == "mock" for item in attempts)
            assert all(item.configured_model == parent.configured_model for item in attempts)
            assert all(item.observed_model == parent.configured_model for item in attempts)
            assert all(item.started_at is not None for item in attempts)
            assert all(item.completed_at is not None for item in attempts)
            assert child_count == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_atomic_child_insert_failure_rolls_back_then_fails_durably() -> None:
    async def scenario():
        from app.models.explanation_attempt import ExplanationGenerationAttemptModel
        from app.models.explanation_run import ExplanationRunModel, MatchExplanationModel
        from app.repositories.explanation_run_repository import ExplanationRunRepository
        from app.services.explanation.generation.errors import (
            ExplanationGenerationFailedError,
        )
        from app.services.explanation.generation.mock_provider import (
            DeterministicExplanationProvider,
        )

        class DuplicateChildRepository(ExplanationRunRepository):
            async def finalize_completed(self, explanation_run_id, explanations, **values):
                for item in explanations:
                    item.id = 777
                await super().finalize_completed(
                    explanation_run_id,
                    explanations,
                    **values,
                )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id = await _persist_valid_historical_run(factory, "944")
            explanation_run_id = "10000000-0000-0000-0000-000000000944"
            service = _service(
                factory,
                provider=DeterministicExplanationProvider(),
                explanation_run_id=explanation_run_id,
            )
            service.explanation_repository = DuplicateChildRepository(factory)

            with pytest.raises(ExplanationGenerationFailedError) as exc_info:
                await service.generate(
                    run_id,
                    requested_top_k=2,
                    request_id="phase94-postgres-child-rollback",
                )

            assert exc_info.value.details["failure_code"] == (
                "explanation_persistence_failed"
            )
            async with factory() as session:
                failed = await session.get(ExplanationRunModel, explanation_run_id)
                children = await session.scalar(
                    select(func.count())
                    .select_from(MatchExplanationModel)
                    .where(
                        MatchExplanationModel.explanation_run_id
                        == explanation_run_id
                    )
                )
                attempts = (
                    await session.scalars(
                        select(ExplanationGenerationAttemptModel).where(
                            ExplanationGenerationAttemptModel.explanation_run_id
                            == explanation_run_id
                        )
                    )
                ).all()
            assert failed.status == "FAILED"
            assert failed.error_code == "explanation_persistence_failed"
            assert "private" not in failed.error_detail_safe.lower()
            assert failed.explanation_count == 0
            assert children == 0
            assert [(item.attempt_number, item.status) for item in attempts] == [
                (1, "COMPLETED")
            ]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_attempt_audit_failure_terminalizes_attempt_and_parent() -> None:
    async def scenario():
        from app.models.explanation_attempt import ExplanationGenerationAttemptModel
        from app.models.explanation_run import ExplanationRunModel, MatchExplanationModel
        from app.repositories.explanation_attempt_repository import (
            ExplanationAttemptRepository,
        )
        from app.services.explanation.generation.errors import (
            ExplanationGenerationFailedError,
        )
        from app.services.explanation.generation.mock_provider import (
            DeterministicExplanationProvider,
        )

        class FailNormalFinishRepository(ExplanationAttemptRepository):
            async def finish_attempt(self, *args, **kwargs):
                raise RuntimeError("private attempt audit failure")

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id = await _persist_valid_historical_run(factory, "945")
            explanation_run_id = "10000000-0000-0000-0000-000000000945"
            service = _service(
                factory,
                provider=DeterministicExplanationProvider(),
                explanation_run_id=explanation_run_id,
            )
            service.attempt_repository = FailNormalFinishRepository(factory)

            with pytest.raises(ExplanationGenerationFailedError) as exc_info:
                await service.generate(
                    run_id,
                    requested_top_k=1,
                    request_id="phase94-postgres-attempt-audit-failure",
                )

            assert exc_info.value.details["failure_code"] == "attempt_audit_failed"
            async with factory() as session:
                failed = await session.get(ExplanationRunModel, explanation_run_id)
                attempt = await session.scalar(
                    select(ExplanationGenerationAttemptModel).where(
                        ExplanationGenerationAttemptModel.explanation_run_id
                        == explanation_run_id
                    )
                )
                children = await session.scalar(
                    select(func.count())
                    .select_from(MatchExplanationModel)
                    .where(
                        MatchExplanationModel.explanation_run_id
                        == explanation_run_id
                    )
                )
            assert failed.status == "FAILED"
            assert failed.error_code == "attempt_audit_failed"
            assert failed.attempt_count == 1
            assert failed.repaired is False
            assert failed.provider_kind == "deterministic"
            assert failed.provider_name == "mock"
            assert attempt.status == "FAILED"
            assert attempt.error_category == "internal_error"
            assert attempt.completed_at is not None
            assert children == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())
