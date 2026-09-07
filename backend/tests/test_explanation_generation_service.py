from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


MATCH_RUN_ID = "00000000-0000-0000-0000-000000000901"
RUN_IDS = (
    "00000000-0000-0000-0000-000000000931",
    "00000000-0000-0000-0000-000000000932",
)


class _TransactionTracker:
    def __init__(self) -> None:
        self.active = 0
        self.events: list[str] = []

    @asynccontextmanager
    async def database_call(self, event: str):
        assert self.active == 0, "repository transactions must not nest"
        self.active += 1
        self.events.append(event)
        try:
            yield
        finally:
            self.active -= 1


class _MatchRunRepository:
    def __init__(self, tracker: _TransactionTracker) -> None:
        self.tracker = tracker
        self.aggregate = SimpleNamespace(
            run_id=MATCH_RUN_ID,
            status="COMPLETED",
            result_count=1,
            results=[
                SimpleNamespace(
                    id=41,
                    run_id=MATCH_RUN_ID,
                    candidate_id="candidate_001",
                    result_rank=1,
                )
            ],
        )

    async def get_by_run_id(self, run_id: str):
        async with self.tracker.database_call("match_run.get"):
            assert run_id == MATCH_RUN_ID
            return self.aggregate


class _ExplanationRepository:
    def __init__(self, tracker: _TransactionTracker) -> None:
        self.tracker = tracker
        self.created_ids: list[str] = []
        self.created_runs = []
        self.failed: list[dict] = []

    async def create_running(self, run) -> None:
        async with self.tracker.database_call("explanation.create_running"):
            self.created_ids.append(run.explanation_run_id)
            self.created_runs.append(run)

    async def store_evidence(self, explanation_run_id: str, **values) -> None:
        async with self.tracker.database_call("explanation.store_evidence"):
            assert explanation_run_id in self.created_ids
            assert values["evidence_bundle"] == "historical-bundle"
            assert values["provider_evidence"] == "provider-projection"

    async def finalize_completed(self, explanation_run_id: str, explanations, **values):
        async with self.tracker.database_call("explanation.finalize_completed"):
            assert explanation_run_id in self.created_ids
            assert explanations
            assert values["attempt_count"] in (1, 2)

    async def finalize_failed(self, explanation_run_id: str, **values) -> None:
        async with self.tracker.database_call("explanation.finalize_failed"):
            assert explanation_run_id in self.created_ids
            self.failed.append(values)


class _AttemptRepository:
    def __init__(self, tracker: _TransactionTracker) -> None:
        self.tracker = tracker
        self.start_error: Exception | None = None
        self.finish_error: Exception | None = None
        self.aborted: list[dict] = []

    async def start_attempt(self, explanation_run_id: str, **values) -> None:
        async with self.tracker.database_call(
            f"attempt.{values['attempt_number']}.start"
        ):
            assert values["attempt_number"] in (1, 2)
            if self.start_error is not None:
                raise self.start_error

    async def finish_attempt(self, explanation_run_id: str, **values) -> None:
        async with self.tracker.database_call(
            f"attempt.{values['attempt_number']}.{values['status'].lower()}"
        ):
            assert values["attempt_number"] in (1, 2)
            assert values["status"] in {"COMPLETED", "FAILED"}
            assert "raw_prompt" not in values
            assert "raw_provider_response" not in values
            if self.finish_error is not None:
                raise self.finish_error

    async def abort_attempt(self, explanation_run_id: str, **values) -> None:
        async with self.tracker.database_call(
            f"attempt.{values['attempt_number']}.abort"
        ):
            self.aborted.append(values)


class _Provider:
    def __init__(self, tracker: _TransactionTracker, responses) -> None:
        self.tracker = tracker
        self.responses = list(responses)
        self.calls = []
        self.descriptor = SimpleNamespace(
            kind="openai_compatible",
            name="deepseek",
            configured_model="configured-model",
            configuration_fingerprint="a" * 64,
        )

    async def generate(self, request):
        assert self.tracker.active == 0, "provider call occurred inside DB transaction"
        self.tracker.events.append(f"provider.{len(self.calls) + 1}")
        self.calls.append(request)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(content=value, observed_model="observed-model")


class _Pipeline:
    prompt_version = "explanation_prompt_v1"
    prompt_fingerprint = "b" * 64

    def __init__(self, outcomes=None) -> None:
        self.outcomes = list(outcomes or ["rendered-output"])
        self.runs = []
        self.repair_categories = []

    def prepare(self, historical_run, *, requested_top_k: int):
        assert historical_run.run_id == MATCH_RUN_ID
        assert requested_top_k == 1
        self.runs.append(historical_run)
        return SimpleNamespace(
            evidence_bundle="historical-bundle",
            provider_evidence="provider-projection",
            effective_top_k=requested_top_k,
            initial_request=SimpleNamespace(attempt_number=1, repair_category=None),
        )

    def repair_request(self, prepared, *, error_category: str):
        self.repair_categories.append(error_category)
        return SimpleNamespace(attempt_number=2, repair_category=error_category)

    def validate_and_render(self, content: str, prepared):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def persistence_models(self, rendered, *, explanation_run_id: str, match_run):
        assert rendered == "rendered-output"
        return [SimpleNamespace(explanation_run_id=explanation_run_id)]


def _service(*, provider_responses, pipeline_outcomes=None, ids=RUN_IDS, max_attempts=2):
    from app.services.explanation.generation.orchestration import (
        ExplanationGenerationService,
    )

    tracker = _TransactionTracker()
    match_runs = _MatchRunRepository(tracker)
    explanations = _ExplanationRepository(tracker)
    attempts = _AttemptRepository(tracker)
    provider = _Provider(tracker, provider_responses)
    pipeline = _Pipeline(
        pipeline_outcomes
        or ["rendered-output" for _ in provider_responses]
    )
    id_values = iter(ids)
    service = ExplanationGenerationService(
        match_run_repository=match_runs,
        explanation_repository=explanations,
        attempt_repository=attempts,
        provider=provider,
        pipeline=pipeline,
        max_attempts=max_attempts,
        id_factory=lambda: next(id_values),
        clock=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc),
    )
    return service, tracker, match_runs, explanations, attempts, provider, pipeline


def test_generation_uses_historical_aggregate_and_finalizes_atomically_outside_provider_call() -> None:
    service, tracker, match_runs, _, _, provider, pipeline = _service(
        provider_responses=["valid-plan"]
    )

    result = asyncio.run(
        service.generate(MATCH_RUN_ID, requested_top_k=1, request_id="request-1")
    )

    assert pipeline.runs == [match_runs.aggregate]
    assert len(provider.calls) == 1
    assert tracker.events == [
        "match_run.get",
        "explanation.create_running",
        "explanation.store_evidence",
        "attempt.1.start",
        "provider.1",
        "attempt.1.completed",
        "explanation.finalize_completed",
    ]
    assert result.explanation_run_id == RUN_IDS[0]


@pytest.mark.parametrize("state", [None, "RUNNING", "FAILED"])
def test_generation_rejects_missing_or_incomplete_match_run_before_creating_history(
    state: str | None,
) -> None:
    from app.exceptions import MatchRunConflictError, MatchRunNotFoundError

    service, _, match_runs, explanations, _, provider, _ = _service(
        provider_responses=["must-not-run"]
    )
    if state is None:
        match_runs.aggregate = None
        expected = MatchRunNotFoundError
    else:
        match_runs.aggregate.status = state
        expected = MatchRunConflictError

    with pytest.raises(expected):
        asyncio.run(
            service.generate(MATCH_RUN_ID, requested_top_k=1, request_id="request-invalid")
        )

    assert explanations.created_ids == []
    assert provider.calls == []


def test_generation_repairs_invalid_output_exactly_once_without_open_transaction() -> None:
    from app.services.explanation.generation.errors import ExplanationPlanParseError

    service, tracker, _, _, _, provider, pipeline = _service(
        provider_responses=["invalid-json", "valid-plan"],
        pipeline_outcomes=[
            ExplanationPlanParseError("invalid provider JSON"),
            "rendered-output",
        ],
    )

    result = asyncio.run(
        service.generate(MATCH_RUN_ID, requested_top_k=1, request_id="request-2")
    )

    assert result.explanation_run_id == RUN_IDS[0]
    assert len(provider.calls) == 2
    assert pipeline.repair_categories == ["invalid_output"]
    assert tracker.active == 0
    assert tracker.events.count("provider.1") == 1
    assert tracker.events.count("provider.2") == 1


def test_generation_respects_configured_single_attempt_without_repair() -> None:
    from app.services.explanation.generation.errors import (
        ExplanationGenerationFailedError,
        ExplanationPlanParseError,
    )

    service, tracker, _, repository, _, provider, pipeline = _service(
        provider_responses=["invalid-json"],
        pipeline_outcomes=[ExplanationPlanParseError()],
        max_attempts=1,
    )

    with pytest.raises(ExplanationGenerationFailedError):
        asyncio.run(
            service.generate(MATCH_RUN_ID, requested_top_k=1, request_id="request-once")
        )

    assert len(provider.calls) == 1
    assert pipeline.repair_categories == []
    assert repository.failed[-1]["error_code"] == "invalid_output"
    assert "attempt.2" not in " ".join(tracker.events)


@pytest.mark.parametrize(
    ("failure_factory", "expected_code", "expected_provider_calls"),
    [
        (lambda: "provider_timeout", "provider_timeout", 1),
        (lambda: "provider_rate_limited", "provider_rate_limited", 1),
        (lambda: "parse_twice", "invalid_output", 2),
        (lambda: "ground_twice", "grounding_failure", 2),
    ],
)
def test_generation_failure_is_durable_safe_and_never_attempts_a_third_call(
    failure_factory, expected_code: str, expected_provider_calls: int
) -> None:
    from app.services.explanation.generation.errors import (
        ExplanationGenerationFailedError,
        ExplanationGroundingError,
        ExplanationPlanParseError,
    )
    from app.services.explanation.generation.provider import (
        ExplanationProviderRateLimitError,
        ExplanationProviderTimeoutError,
    )

    failure = failure_factory()
    if failure == "provider_timeout":
        responses = [ExplanationProviderTimeoutError()]
        outcomes = None
    elif failure == "provider_rate_limited":
        responses = [ExplanationProviderRateLimitError()]
        outcomes = None
    elif failure == "parse_twice":
        responses = ["invalid-1", "invalid-2"]
        outcomes = [
            ExplanationPlanParseError("private bad JSON 1"),
            ExplanationPlanParseError("private bad JSON 2"),
        ]
    else:
        responses = ["invalid-1", "invalid-2"]
        outcomes = [
            ExplanationGroundingError("private unsupported claim 1"),
            ExplanationGroundingError("private unsupported claim 2"),
        ]
    service, tracker, _, explanation_repository, _, provider, _ = _service(
        provider_responses=responses,
        pipeline_outcomes=outcomes,
    )

    with pytest.raises(ExplanationGenerationFailedError) as exc_info:
        asyncio.run(
            service.generate(MATCH_RUN_ID, requested_top_k=1, request_id="request-3")
        )

    assert len(provider.calls) == expected_provider_calls
    assert explanation_repository.failed[-1]["error_code"] == expected_code
    safe_detail = explanation_repository.failed[-1]["error_detail_safe"]
    assert len(safe_detail) <= 500
    assert "private" not in safe_detail
    assert exc_info.value.details == {
        "explanation_run_id": RUN_IDS[0],
        "failure_code": expected_code,
    }
    assert tracker.events[-1] == "explanation.finalize_failed"
    assert tracker.active == 0


def test_regeneration_creates_new_run_and_never_overwrites_history() -> None:
    service, _, _, repository, _, _, _ = _service(
        provider_responses=["valid-plan", "valid-plan"]
    )

    first = asyncio.run(
        service.generate(MATCH_RUN_ID, requested_top_k=1, request_id="request-a")
    )
    second = asyncio.run(
        service.generate(MATCH_RUN_ID, requested_top_k=1, request_id="request-b")
    )

    assert first.explanation_run_id != second.explanation_run_id
    assert repository.created_ids == list(RUN_IDS)


def test_atomic_completion_failure_rolls_back_then_finalizes_failed_durably() -> None:
    from app.services.explanation.generation.errors import (
        ExplanationGenerationFailedError,
    )

    service, tracker, _, repository, _, _, _ = _service(
        provider_responses=["valid-plan"]
    )

    async def failing_completion(explanation_run_id: str, explanations, **values):
        async with tracker.database_call("explanation.finalize_completed"):
            raise RuntimeError("private child insert failure")

    repository.finalize_completed = failing_completion

    with pytest.raises(ExplanationGenerationFailedError) as exc_info:
        asyncio.run(
            service.generate(
                MATCH_RUN_ID,
                requested_top_k=1,
                request_id="request-persistence-failure",
            )
        )

    assert repository.failed[-1]["error_code"] == "explanation_persistence_failed"
    assert "private" not in repository.failed[-1]["error_detail_safe"]
    assert exc_info.value.details["failure_code"] == "explanation_persistence_failed"
    assert tracker.events[-2:] == [
        "explanation.finalize_completed",
        "explanation.finalize_failed",
    ]


def test_attempt_start_failure_finalizes_parent_without_calling_provider() -> None:
    from app.services.explanation.generation.errors import (
        ExplanationGenerationFailedError,
    )

    service, tracker, _, repository, attempts, provider, _ = _service(
        provider_responses=["must-not-run"]
    )
    attempts.start_error = RuntimeError("private attempt insert failure")

    with pytest.raises(ExplanationGenerationFailedError) as exc_info:
        asyncio.run(
            service.generate(
                MATCH_RUN_ID,
                requested_top_k=1,
                request_id="request-attempt-start-failure",
            )
        )

    assert provider.calls == []
    assert repository.failed[-1]["error_code"] == "attempt_audit_failed"
    assert "private" not in repository.failed[-1]["error_detail_safe"]
    assert exc_info.value.details["failure_code"] == "attempt_audit_failed"
    assert attempts.aborted[-1]["attempt_number"] == 1
    assert tracker.events[-1] == "explanation.finalize_failed"


def test_provider_success_with_attempt_finish_failure_finalizes_parent_failed() -> None:
    from app.services.explanation.generation.errors import (
        ExplanationGenerationFailedError,
    )

    service, tracker, _, repository, attempts, provider, _ = _service(
        provider_responses=["valid-plan"]
    )
    attempts.finish_error = RuntimeError("private attempt finish failure")

    with pytest.raises(ExplanationGenerationFailedError) as exc_info:
        asyncio.run(
            service.generate(
                MATCH_RUN_ID,
                requested_top_k=1,
                request_id="request-attempt-finish-success-failure",
            )
        )

    assert len(provider.calls) == 1
    assert repository.failed[-1]["error_code"] == "attempt_audit_failed"
    assert exc_info.value.details["failure_code"] == "attempt_audit_failed"
    assert attempts.aborted[-1]["attempt_number"] == 1
    assert "explanation.finalize_completed" not in tracker.events
    assert tracker.events[-1] == "explanation.finalize_failed"


def test_provider_failure_with_attempt_finish_failure_finalizes_parent_failed() -> None:
    from app.services.explanation.generation.errors import (
        ExplanationGenerationFailedError,
    )
    from app.services.explanation.generation.provider import (
        ExplanationProviderTimeoutError,
    )

    service, tracker, _, repository, attempts, provider, _ = _service(
        provider_responses=[ExplanationProviderTimeoutError()]
    )
    attempts.finish_error = RuntimeError("private attempt finish failure")

    with pytest.raises(ExplanationGenerationFailedError) as exc_info:
        asyncio.run(
            service.generate(
                MATCH_RUN_ID,
                requested_top_k=1,
                request_id="request-attempt-finish-provider-failure",
            )
        )

    assert len(provider.calls) == 1
    assert repository.failed[-1]["error_code"] == "attempt_audit_failed"
    assert exc_info.value.details["failure_code"] == "attempt_audit_failed"
    assert attempts.aborted[-1]["attempt_number"] == 1
    assert tracker.events[-1] == "explanation.finalize_failed"


def test_running_parent_records_available_provider_and_prompt_provenance() -> None:
    service, _, _, repository, _, _, _ = _service(
        provider_responses=["valid-plan"]
    )

    asyncio.run(
        service.generate(
            MATCH_RUN_ID,
            requested_top_k=1,
            request_id="request-parent-provenance",
        )
    )

    parent = repository.created_runs[0]
    assert parent.provider_kind == "openai_compatible"
    assert parent.provider_name == "deepseek"
    assert parent.configured_model == "configured-model"
    assert parent.provider_configuration_fingerprint == "a" * 64
    assert parent.prompt_version == "explanation_prompt_v1"
    assert parent.prompt_fingerprint == "b" * 64


def test_orchestration_has_no_current_state_or_ranking_dependencies() -> None:
    import inspect

    from app.services.explanation.generation import orchestration

    source = inspect.getsource(orchestration)
    assert not any(
        forbidden in source
        for forbidden in (
            "CandidateRepository",
            "JobRepository",
            "CandidateService",
            "JobService",
            "Qdrant",
            "RetrievalService",
            "FeatureEngineeringService",
            "RankingService",
            "CrossEncoderRerankingService",
        )
    )
