from __future__ import annotations

import json
from pathlib import Path

import asyncio
from types import SimpleNamespace
import pytest

from app.exceptions import (
    CrossEncoderContractMismatchError,
    CrossEncoderModelUnavailableError,
    MatchRunExecutionError,
    RankingContractMismatchError,
    RankingModelUnavailableError,
)
from app.schemas.cross_encoder import (
    CrossEncoderRerankingResponseData,
    CrossEncoderRerankingResult,
)
from app.schemas.features import FeatureAvailability, FeatureDiagnostics, FeatureVector
from app.schemas.match_runs import (
    CrossEncoderMatchRunRequest,
    LtrMatchRunRequest,
    MatchRunStatus,
)
from app.schemas.persistence import CandidateRecord, JobRecord
from app.schemas.ranking import RankingRequest, RankingResponseData, RankingResult
from app.schemas.retrieval import (
    RetrievalDiagnostics,
    RetrievalEntityType,
    RetrievalResult,
    RetrievalStrategy,
)
from app.services.match_runs.service import MatchRunService


ROOT = Path(__file__).resolve().parents[2]


def _record(path: str, model):
    payload = json.loads((ROOT / path).read_text(encoding="utf-8").splitlines()[0])
    payload["dataset_version"] = "1.0.0"
    return model.model_validate(payload)


def _ranking_response() -> RankingResponseData:
    return RankingResponseData(
        ranker_version="ltr_ranker_v1",
        model_sha256="c8f235ebd95dce611f892394859f9f0251f43f8822a39bd316c404d9ff75a000",
        feature_version="feature_schema_v1",
        feature_fingerprint="dc85c7237c6c67785199d221c919ae48c31c9a6323857070e6399d3eae365e42",
        candidate_pool_k=20,
        results=[
            RankingResult(
                entity_id="cand_001",
                ltr_rank=1,
                ltr_score_raw=0.3125,
                retrieval=RetrievalResult(
                    entity_id="cand_001",
                    rank=2,
                    matched_channels=["dense", "sparse"],
                    dense_rank=2,
                    dense_score=0.75,
                    sparse_rank=1,
                    sparse_score=4.5,
                    fusion_score=0.0325,
                ),
                feature_vector=FeatureVector(
                    semantic_score=0.75,
                    sparse_score=4.5,
                    skill_fit_score=0.8,
                    project_evidence_score=0.6,
                    role_direction_score=0.7,
                    ai_tool_score=0.5,
                    location_score=1.0,
                    seniority_score=1.0,
                    missing_penalty=0.2,
                    overclaim_penalty=0.0,
                ),
                feature_diagnostics=FeatureDiagnostics(
                    availability=FeatureAvailability(**{name: True for name in FeatureVector.model_fields}),
                    matched_must_have_requirement_ids=["req_job_001_02"],
                    weak_matched_must_have_requirement_ids=[],
                    missing_must_have_requirement_ids=["req_job_001_03"],
                    matched_nice_to_have_requirement_ids=[],
                    evidence_supported_requirement_ids=["req_job_001_04"],
                    matched_capabilities=["Candidate retrieval"],
                    matched_evidence_skills=["Offline evaluation"],
                    matched_ai_tools=["structured outputs"],
                    location_relation="exact_city_overlap",
                    seniority_relation="exact_match",
                    overclaim_level="low",
                    overclaim_reason_count=0,
                    retrieval_rank=2,
                    dense_rank=2,
                    sparse_rank=1,
                    fusion_score=0.0325,
                ),
            )
        ],
        retrieval_diagnostics=RetrievalDiagnostics(
            query_type=RetrievalEntityType.JOB,
            query_id="job_001",
            result_type=RetrievalEntityType.CANDIDATE,
            strategy=RetrievalStrategy.HYBRID,
            top_k_requested=20,
            returned_count=1,
            corpus_size=48,
            eligible_count=48,
            dense_pool_size=20,
            sparse_pool_size=20,
            embedding_provider="sentence_transformers",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            document_version="retrieval_doc_v4",
            rrf_k=60,
            filters_applied=False,
            index_freshness="fresh",
            dense_ms=1.0,
            sparse_ms=1.0,
            fusion_ms=1.0,
            total_ms=3.0,
        ),
    )


class FakeProfileRepository:
    def __init__(self, records):
        self.records = records

    async def get_record_by_id(self, entity_id):
        return self.records.get(entity_id)


class FakeLifecycleRepository:
    def __init__(self):
        self.run = None
        self.steps = []
        self.results = []
        self.events = []

    async def create_running(self, run):
        self.run = run
        self.events.append("create_running")

    async def resolve_job(self, **values):
        for key, value in values.items():
            if key != "run_id":
                setattr(self.run, key, value)
        self.events.append("resolve_job")

    async def start_step(self, step):
        self.steps.append(step)
        self.events.append(f"start:{step.step_name}")

    async def complete_step(self, run_id, sequence, **values):
        step = next(item for item in self.steps if item.sequence == sequence)
        for key, value in values.items():
            setattr(step, key, value)
        step.status = "COMPLETED"
        self.events.append(f"complete:{step.step_name}")

    async def finalize_results_atomically(self, run_id, results, **values):
        self.results = list(results)
        step = next(item for item in self.steps if item.step_name == "persist_results")
        step.status = "COMPLETED"
        for key, value in values.items():
            if key in {"finished_at", "duration_ms", "output_refs"}:
                setattr(step, key, value)
        self.run.status = "COMPLETED"
        self.run.completed_at = values["finished_at"]
        self.run.result_count = len(self.results)
        self.run.result_fingerprint = values["result_fingerprint"]
        self.run.ce_provenance = values.get("ce_provenance")
        self.events.append("finalize_results")

    async def finalize_failed(self, run_id, **values):
        step = None
        if values.get("sequence") is not None:
            step = next(
                (item for item in self.steps if item.sequence == values["sequence"]), None
            )
            if step is None:
                step = values["step"]
                self.steps.append(step)
            step.status = "FAILED"
            step.finished_at = values["finished_at"]
            step.duration_ms = values["duration_ms"]
            step.error_code = values["error_code"]
            step.error_detail_safe = values["error_detail_safe"]
        self.run.status = "FAILED"
        self.run.completed_at = values["finished_at"]
        self.run.error_code = values["error_code"]
        self.run.error_detail_safe = values["error_detail_safe"]
        if step is not None:
            self.events.append(f"failed:{step.step_name}")

    async def get_by_run_id(self, run_id):
        self.run.steps = sorted(self.steps, key=lambda item: item.sequence)
        self.run.results = sorted(self.results, key=lambda item: item.result_rank)
        return self.run


class FakeRankingService:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.ranking_model = SimpleNamespace(
            metadata={
                "retrieval_configuration_fingerprint": (
                    "b004bc52c33f3e15bf38dba1777305039909bb5229261dcf1851b289e7c8f2e7"
                )
            }
        )

    async def rank_job_candidates(self, job_id, request):
        self.calls.append((job_id, request))
        if self.error:
            raise self.error
        return self.response


class FakeCrossEncoderService:
    def __init__(self, ranking_proxy, error=None):
        self.ranking_proxy = ranking_proxy
        self.error = error

    async def rerank_job_candidates(self, job_id, request):
        ltr = await self.ranking_proxy.rank_job_candidates(
            job_id,
            RankingRequest(
                candidate_pool_k=request.retrieval_pool_k,
                top_k=request.cross_encoder_pool_k,
                filters=request.filters,
            ),
        )
        if self.error:
            raise self.error
        first = ltr.results[0]
        return CrossEncoderRerankingResponseData(
            reranker_version="cross_encoder_reranker_v1",
            model_id="cross-encoder/ms-marco-MiniLM-L6-v2",
            model_revision="233902d25c440f23af6f7d6e94d2946bac0bee0a",
            snapshot_fingerprint="013355448b38f6190a4d7250b1d062f76caddd8a5f1cabc47bdc716490a60236",
            text_schema_version="cross_encoder_text_v1",
            text_contract_fingerprint="45803a625d6bb28b3155f216a1d6b571ebb978771cd398134fa984e356c703ee",
            pair_order="job_then_candidate",
            retrieval_pool_k=request.retrieval_pool_k,
            cross_encoder_pool_k=request.cross_encoder_pool_k,
            top_k=request.top_k,
            results=[
                CrossEncoderRerankingResult(
                    entity_id=first.entity_id,
                    retrieval_rank=first.retrieval.rank,
                    ltr_rank=first.ltr_rank,
                    ltr_score_raw=first.ltr_score_raw,
                    cross_encoder_rank=1,
                    cross_encoder_score_raw=1.25,
                    ranker_version=ltr.ranker_version,
                    model_sha256=ltr.model_sha256,
                    feature_version=ltr.feature_version,
                    feature_fingerprint=ltr.feature_fingerprint,
                )
            ],
        )


def _service(*, ranking, jobs=None, ce_factory=None):
    lifecycle = FakeLifecycleRepository()
    ce_calls = []

    def forbidden_ce(_ranking_proxy):
        ce_calls.append(True)
        raise AssertionError("CE must remain lazy for LTR runs")

    service = MatchRunService(
        lifecycle_repository=lifecycle,
        job_repository=FakeProfileRepository(jobs or {"job_001": _record("data/samples/jobs.jsonl", JobRecord)}),
        candidate_repository=FakeProfileRepository(
            {"cand_001": _record("data/samples/candidates.jsonl", CandidateRecord)}
        ),
        ranking_service_factory=lambda: ranking,
        cross_encoder_service_factory=ce_factory or forbidden_ce,
    )
    return service, lifecycle, ce_calls


def test_ltr_run_persists_actual_trace_and_does_not_resolve_ce() -> None:
    async def scenario():
        ranking = FakeRankingService(_ranking_response())
        service, lifecycle, ce_calls = _service(ranking=ranking)
        run = await service.execute(LtrMatchRunRequest(job_id="job_001"), request_id="http-1")
        return run, lifecycle, ranking, ce_calls, service

    run, lifecycle, ranking, ce_calls, service = asyncio.run(scenario())

    assert run.status == MatchRunStatus.COMPLETED.value
    assert run.request_id == "http-1"
    assert run.run_id != run.request_id
    assert [step.step_name for step in run.steps] == [
        "resolve_inputs",
        "phase6_ltr_rank",
        "persist_results",
    ]
    assert all(step.status == "COMPLETED" for step in run.steps)
    assert lifecycle.events[0] == "create_running"
    assert len(ranking.calls) == 1
    assert ce_calls == []
    assert run.ce_provenance is None
    assert run.results[0].candidate_input_snapshot["candidate_id"] == "cand_001"
    assert run.results[0].ltr_score_raw == 0.3125
    assert service._step_sequences == {}


class _ExecutionSessionContext:
    def __init__(self):
        self.session = _ExecutionSession()

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *args):
        return False

    def begin(self):
        return self


class _ExecutionSession:
    def begin(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _SessionBoundRepository(FakeProfileRepository):
    def __init__(self, session, records):
        super().__init__(records)
        self.session = session


def test_execution_graph_uses_one_repeatable_read_session_for_all_profile_reads() -> None:
    async def scenario():
        lifecycle = FakeLifecycleRepository()
        execution_factory = _ExecutionSessionContext()
        ranking = FakeRankingService(_ranking_response())
        observed = {}

        def graph_factory(session):
            observed["session"] = session
            job_repository = _SessionBoundRepository(
                session, {"job_001": _record("data/samples/jobs.jsonl", JobRecord)}
            )
            candidate_repository = _SessionBoundRepository(
                session, {"cand_001": _record("data/samples/candidates.jsonl", CandidateRecord)}
            )
            observed["job_repository"] = job_repository
            observed["candidate_repository"] = candidate_repository
            return {
                "job_repository": job_repository,
                "candidate_repository": candidate_repository,
                "ranking_service_factory": lambda: ranking,
                "cross_encoder_service_factory": lambda proxy: FakeCrossEncoderService(proxy),
            }

        service = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=None,
            candidate_repository=None,
            ranking_service_factory=None,
            cross_encoder_service_factory=None,
            execution_session_factory=execution_factory,
            execution_graph_factory=graph_factory,
        )
        await service.execute(LtrMatchRunRequest(job_id="job_001"), request_id="session-proof")
        return execution_factory, observed

    execution_factory, observed = asyncio.run(scenario())
    assert observed["job_repository"].session is execution_factory.session
    assert observed["candidate_repository"].session is execution_factory.session


@pytest.mark.parametrize(
    "field,value",
    [
        ("ranker_version", "wrong_ranker"),
        ("model_sha256", "f" * 64),
        ("feature_fingerprint", "f" * 64),
    ],
)
def test_observed_runtime_provenance_mismatch_fails_closed(field, value) -> None:
    async def scenario():
        response = _ranking_response().model_copy(update={field: value})
        service, lifecycle, _ = _service(ranking=FakeRankingService(response))
        with pytest.raises(MatchRunExecutionError):
            await service.execute(LtrMatchRunRequest(job_id="job_001"), request_id="bad-provenance")
        return lifecycle

    lifecycle = asyncio.run(scenario())
    assert lifecycle.run.status == "FAILED"
    assert lifecycle.results == []


def test_observed_retrieval_configuration_mismatch_fails_closed() -> None:
    async def scenario():
        ranking = FakeRankingService(_ranking_response())
        ranking.ranking_model.metadata["retrieval_configuration_fingerprint"] = "wrong"
        service, lifecycle, _ = _service(ranking=ranking)
        with pytest.raises(MatchRunExecutionError):
            await service.execute(
                LtrMatchRunRequest(job_id="job_001"), request_id="bad-retrieval-provenance"
            )
        return lifecycle

    lifecycle = asyncio.run(scenario())
    assert lifecycle.run.status == "FAILED"
    assert lifecycle.results == []


def test_ce_factory_failure_does_not_create_unstarted_phase_steps() -> None:
    async def scenario():
        lifecycle = FakeLifecycleRepository()
        ranking = FakeRankingService(_ranking_response())

        def unavailable(_proxy):
            raise CrossEncoderModelUnavailableError("CE service unavailable")

        service = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=FakeProfileRepository(
                {"job_001": _record("data/samples/jobs.jsonl", JobRecord)}
            ),
            candidate_repository=FakeProfileRepository(
                {"cand_001": _record("data/samples/candidates.jsonl", CandidateRecord)}
            ),
            ranking_service_factory=lambda: ranking,
            cross_encoder_service_factory=unavailable,
        )
        with pytest.raises(MatchRunExecutionError):
            await service.execute(
                CrossEncoderMatchRunRequest(
                    job_id="job_001", ranking_variant="cross_encoder_experiment"
                ),
                request_id="ce-factory-fail",
            )
        return lifecycle, ranking

    lifecycle, ranking = asyncio.run(scenario())
    assert ranking.calls == []
    assert [(step.step_name, step.status) for step in lifecycle.steps] == [
        ("resolve_inputs", "COMPLETED")
    ]
    assert lifecycle.run.status == "FAILED"


def test_phase6_failure_is_durable_and_has_no_results() -> None:
    async def scenario():
        ranking = FakeRankingService(error=RankingContractMismatchError("bad contract"))
        service, lifecycle, _ = _service(ranking=ranking)
        with pytest.raises(MatchRunExecutionError) as captured:
            await service.execute(LtrMatchRunRequest(job_id="job_001"), request_id="http-2")
        return captured.value, lifecycle

    error, lifecycle = asyncio.run(scenario())

    assert error.details["run_id"] == lifecycle.run.run_id
    assert lifecycle.run.status == "FAILED"
    assert lifecycle.run.error_code == "ranking_contract_mismatch"
    assert lifecycle.results == []
    assert [(step.step_name, step.status) for step in lifecycle.steps] == [
        ("resolve_inputs", "COMPLETED"),
        ("phase6_ltr_rank", "FAILED"),
    ]


def test_missing_job_failure_preserves_requested_id_before_ranking() -> None:
    async def scenario():
        ranking = FakeRankingService(_ranking_response())
        service, lifecycle, _ = _service(ranking=ranking, jobs={})
        with pytest.raises(MatchRunExecutionError):
            await service.execute(LtrMatchRunRequest(job_id="job_missing"), request_id="http-3")
        return ranking, lifecycle

    ranking, lifecycle = asyncio.run(scenario())

    assert lifecycle.run.requested_job_id == "job_missing"
    assert lifecycle.run.job_id is None
    assert lifecycle.run.status == "FAILED"
    assert lifecycle.steps[0].step_name == "resolve_inputs"
    assert lifecycle.steps[0].status == "FAILED"
    assert ranking.calls == []


def test_rerun_always_creates_a_new_run_id() -> None:
    async def scenario():
        first_service, _, _ = _service(ranking=FakeRankingService(_ranking_response()))
        second_service, _, _ = _service(ranking=FakeRankingService(_ranking_response()))
        payload = LtrMatchRunRequest(job_id="job_001")
        first = await first_service.execute(payload, request_id="same")
        second = await second_service.execute(payload, request_id="same")
        return first, second

    first, second = asyncio.run(scenario())
    assert first.run_id != second.run_id


def test_explicit_ce_request_keeps_frozen_defaults() -> None:
    request = CrossEncoderMatchRunRequest(
        job_id="job_001", ranking_variant="cross_encoder_experiment"
    )
    assert (request.retrieval_pool_k, request.cross_encoder_pool_k, request.top_k) == (
        20,
        10,
        5,
    )


def test_explicit_ce_records_ltr_then_ce_and_persists_ce_provenance() -> None:
    async def scenario():
        ranking = FakeRankingService(_ranking_response())
        service, lifecycle, _ = _service(
            ranking=ranking,
            ce_factory=lambda proxy: FakeCrossEncoderService(proxy),
        )
        run = await service.execute(
            CrossEncoderMatchRunRequest(
                job_id="job_001", ranking_variant="cross_encoder_experiment"
            ),
            request_id="http-ce",
        )
        return run

    run = asyncio.run(scenario())
    assert [step.step_name for step in run.steps] == [
        "resolve_inputs",
        "phase6_ltr_rank",
        "phase7_cross_encoder_rerank",
        "persist_results",
    ]
    assert all(step.status == "COMPLETED" for step in run.steps)
    assert run.ce_provenance["calibration"] is False
    assert run.results[0].cross_encoder_score_raw == 1.25


@pytest.mark.parametrize(
    "error,code",
    [
        (CrossEncoderModelUnavailableError("snapshot unavailable"), "cross_encoder_model_unavailable"),
        (CrossEncoderContractMismatchError("contract mismatch"), "cross_encoder_contract_mismatch"),
    ],
)
def test_ce_failure_retains_completed_ltr_and_failed_ce_step(error, code) -> None:
    async def scenario():
        ranking = FakeRankingService(_ranking_response())
        service, lifecycle, _ = _service(
            ranking=ranking,
            ce_factory=lambda proxy: FakeCrossEncoderService(proxy, error=error),
        )
        with pytest.raises(MatchRunExecutionError):
            await service.execute(
                CrossEncoderMatchRunRequest(
                    job_id="job_001", ranking_variant="cross_encoder_experiment"
                ),
                request_id="http-ce-fail",
            )
        return lifecycle

    lifecycle = asyncio.run(scenario())
    assert [(step.step_name, step.status) for step in lifecycle.steps] == [
        ("resolve_inputs", "COMPLETED"),
        ("phase6_ltr_rank", "COMPLETED"),
        ("phase7_cross_encoder_rerank", "FAILED"),
    ]
    assert lifecycle.run.error_code == code
    assert lifecycle.results == []


def test_result_persistence_failure_rolls_back_results_and_fails_persist_step() -> None:
    class FailingFinalization(FakeLifecycleRepository):
        async def finalize_results_atomically(self, run_id, results, **values):
            raise RuntimeError("simulated atomic write failure")

    async def scenario():
        lifecycle = FailingFinalization()
        service = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=FakeProfileRepository(
                {"job_001": _record("data/samples/jobs.jsonl", JobRecord)}
            ),
            candidate_repository=FakeProfileRepository(
                {"cand_001": _record("data/samples/candidates.jsonl", CandidateRecord)}
            ),
            ranking_service_factory=lambda: FakeRankingService(_ranking_response()),
            cross_encoder_service_factory=lambda _: None,
        )
        with pytest.raises(MatchRunExecutionError):
            await service.execute(LtrMatchRunRequest(job_id="job_001"), request_id="persist-fail")
        return lifecycle

    lifecycle = asyncio.run(scenario())
    assert lifecycle.run.status == "FAILED"
    assert lifecycle.results == []
    assert lifecycle.steps[-1].step_name == "persist_results"
    assert lifecycle.steps[-1].status == "FAILED"


def test_step_write_failure_still_creates_failed_step_in_independent_transaction() -> None:
    class FailingStepWrite(FakeLifecycleRepository):
        failed_once = False

        async def start_step(self, step):
            if step.step_name == "phase6_ltr_rank" and not self.failed_once:
                self.failed_once = True
                raise RuntimeError("simulated step write failure")
            await super().start_step(step)

    async def scenario():
        lifecycle = FailingStepWrite()
        ranking = FakeRankingService(_ranking_response())
        service = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=FakeProfileRepository(
                {"job_001": _record("data/samples/jobs.jsonl", JobRecord)}
            ),
            candidate_repository=FakeProfileRepository(
                {"cand_001": _record("data/samples/candidates.jsonl", CandidateRecord)}
            ),
            ranking_service_factory=lambda: ranking,
            cross_encoder_service_factory=lambda _: None,
        )
        with pytest.raises(MatchRunExecutionError):
            await service.execute(LtrMatchRunRequest(job_id="job_001"), request_id="step-fail")
        return lifecycle, ranking

    lifecycle, ranking = asyncio.run(scenario())
    assert lifecycle.run.status == "FAILED"
    assert lifecycle.steps[-1].step_name == "phase6_ltr_rank"
    assert lifecycle.steps[-1].status == "FAILED"
    assert ranking.calls == []


def test_step_completion_write_failure_marks_the_actual_step_failed() -> None:
    class FailingStepCompletion(FakeLifecycleRepository):
        async def complete_step(self, run_id, sequence, **values):
            step = next(item for item in self.steps if item.sequence == sequence)
            if step.step_name == "phase6_ltr_rank":
                raise RuntimeError("simulated step completion failure")
            await super().complete_step(run_id, sequence, **values)

    async def scenario():
        lifecycle = FailingStepCompletion()
        service = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=FakeProfileRepository(
                {"job_001": _record("data/samples/jobs.jsonl", JobRecord)}
            ),
            candidate_repository=FakeProfileRepository(
                {"cand_001": _record("data/samples/candidates.jsonl", CandidateRecord)}
            ),
            ranking_service_factory=lambda: FakeRankingService(_ranking_response()),
            cross_encoder_service_factory=lambda _: None,
        )
        with pytest.raises(MatchRunExecutionError):
            await service.execute(
                LtrMatchRunRequest(job_id="job_001"), request_id="complete-fail"
            )
        return lifecycle

    lifecycle = asyncio.run(scenario())
    assert lifecycle.run.status == "FAILED"
    assert [(step.step_name, step.status) for step in lifecycle.steps] == [
        ("resolve_inputs", "COMPLETED"),
        ("phase6_ltr_rank", "FAILED"),
    ]


def test_ranking_service_factory_failure_is_recorded_as_phase6_failure() -> None:
    async def scenario():
        lifecycle = FakeLifecycleRepository()

        def unavailable():
            raise RankingModelUnavailableError("ranking model unavailable")

        service = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=FakeProfileRepository(
                {"job_001": _record("data/samples/jobs.jsonl", JobRecord)}
            ),
            candidate_repository=FakeProfileRepository(
                {"cand_001": _record("data/samples/candidates.jsonl", CandidateRecord)}
            ),
            ranking_service_factory=unavailable,
            cross_encoder_service_factory=lambda _: None,
        )
        with pytest.raises(MatchRunExecutionError):
            await service.execute(
                LtrMatchRunRequest(job_id="job_001"), request_id="model-fail"
            )
        return lifecycle

    lifecycle = asyncio.run(scenario())
    assert lifecycle.run.status == "FAILED"
    assert [(step.step_name, step.status) for step in lifecycle.steps] == [
        ("resolve_inputs", "COMPLETED"),
        ("phase6_ltr_rank", "FAILED"),
    ]
    assert lifecycle.run.error_code == "ranking_model_unavailable"


def test_ce_step_completion_failure_is_retained_as_phase7_failure() -> None:
    class FailingCECompletion(FakeLifecycleRepository):
        async def complete_step(self, run_id, sequence, **values):
            step = next(item for item in self.steps if item.sequence == sequence)
            if step.step_name == "phase7_cross_encoder_rerank":
                raise RuntimeError("simulated CE step completion failure")
            await super().complete_step(run_id, sequence, **values)

    async def scenario():
        lifecycle = FailingCECompletion()
        service = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=FakeProfileRepository(
                {"job_001": _record("data/samples/jobs.jsonl", JobRecord)}
            ),
            candidate_repository=FakeProfileRepository(
                {"cand_001": _record("data/samples/candidates.jsonl", CandidateRecord)}
            ),
            ranking_service_factory=lambda: FakeRankingService(_ranking_response()),
            cross_encoder_service_factory=lambda proxy: FakeCrossEncoderService(proxy),
        )
        with pytest.raises(MatchRunExecutionError):
            await service.execute(
                CrossEncoderMatchRunRequest(
                    job_id="job_001", ranking_variant="cross_encoder_experiment"
                ),
                request_id="ce-complete-fail",
            )
        return lifecycle

    lifecycle = asyncio.run(scenario())
    assert lifecycle.run.status == "FAILED"
    assert [(step.step_name, step.status) for step in lifecycle.steps] == [
        ("resolve_inputs", "COMPLETED"),
        ("phase6_ltr_rank", "COMPLETED"),
        ("phase7_cross_encoder_rerank", "FAILED"),
    ]


def test_sequence_state_is_cleaned_when_running_record_creation_fails() -> None:
    class FailingCreate(FakeLifecycleRepository):
        async def create_running(self, run):
            raise RuntimeError("lifecycle unavailable")

    async def scenario():
        lifecycle = FailingCreate()
        service = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=FakeProfileRepository({}),
            candidate_repository=FakeProfileRepository({}),
            ranking_service_factory=lambda: FakeRankingService(_ranking_response()),
            cross_encoder_service_factory=lambda proxy: FakeCrossEncoderService(proxy),
            run_id_factory=lambda: "sequence-cleanup-run",
        )
        with pytest.raises(RuntimeError):
            await service.execute(
                LtrMatchRunRequest(job_id="job_001"), request_id="cleanup-test"
            )
        return service

    service = asyncio.run(scenario())
    assert service._step_sequences == {}


def test_match_run_ltr_preserves_frozen_ranking_output() -> None:
    from app.schemas.ranking import RankingRequest
    from app.services.ranking.service import RankingService
    from test_feature_service import _feature_service
    from test_ltr_service import FakeModel

    from app.services.match_runs.contracts import (
        RANKER_MODEL_SHA256,
        RETRIEVAL_CONFIGURATION_FINGERPRINT,
    )

    class ContractModel(FakeModel):
        model_sha256 = RANKER_MODEL_SHA256

        def __init__(self):
            super().__init__()
            self.metadata = {
                "retrieval_configuration_fingerprint": RETRIEVAL_CONFIGURATION_FINGERPRINT
            }

    async def scenario():
        feature_service, _retrieval, candidates, jobs = _feature_service()
        direct_service = RankingService(
            feature_service=feature_service,
            ranking_model=ContractModel(),
        )
        job = jobs[0]
        candidate_map = {item.candidate_id: item for item in candidates}
        direct = await direct_service.rank_job_candidates(
            job.job_id, RankingRequest(candidate_pool_k=4, top_k=2)
        )
        lifecycle = FakeLifecycleRepository()
        wrapped = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=FakeProfileRepository({job.job_id: job}),
            candidate_repository=FakeProfileRepository(candidate_map),
            ranking_service_factory=lambda: direct_service,
            cross_encoder_service_factory=lambda proxy: None,
            run_id_factory=lambda: "equivalence-run",
        )
        await wrapped.execute(
            LtrMatchRunRequest(job_id=job.job_id, candidate_pool_k=4, top_k=2),
            request_id="equivalence",
        )
        return direct, lifecycle.results

    direct, persisted = asyncio.run(scenario())
    assert [item.entity_id for item in direct.results] == [
        item.candidate_id for item in persisted
    ]
    for source, stored in zip(direct.results, persisted):
        assert stored.retrieval_rank == source.retrieval.rank
        assert stored.ltr_rank == source.ltr_rank
        assert stored.ltr_score_raw == source.ltr_score_raw
        for name in (
            "semantic_score",
            "sparse_score",
            "skill_fit_score",
            "project_evidence_score",
            "role_direction_score",
            "ai_tool_score",
            "location_score",
            "seniority_score",
            "missing_penalty",
            "overclaim_penalty",
        ):
            assert getattr(stored, name) == getattr(source.feature_vector, name)


def test_match_run_ce_preserves_frozen_reranking_output() -> None:
    import numpy as np

    from app.schemas.cross_encoder import CrossEncoderRerankingRequest
    from app.services.cross_encoder.service import CrossEncoderRerankingService
    from app.services.match_runs.contracts import (
        CE_MODEL_ID,
        CE_MODEL_REVISION,
        CE_SNAPSHOT_FINGERPRINT,
        RANKER_MODEL_SHA256,
        RETRIEVAL_CONFIGURATION_FINGERPRINT,
    )
    from app.services.ranking.service import RankingService
    from test_feature_service import _feature_service
    from test_ltr_service import FakeModel

    class ContractModel(FakeModel):
        model_sha256 = RANKER_MODEL_SHA256

        def __init__(self):
            super().__init__()
            self.metadata = {
                "retrieval_configuration_fingerprint": RETRIEVAL_CONFIGURATION_FINGERPRINT
            }

    class StableCrossEncoder:
        model_id = CE_MODEL_ID
        revision = CE_MODEL_REVISION
        snapshot_fingerprint = CE_SNAPSHOT_FINGERPRINT

        def predict_pairs(self, pairs, *, batch_size):
            return np.asarray([float(len(left) + len(right)) for left, right in pairs])

    async def scenario():
        feature_service, _retrieval, candidates, jobs = _feature_service()
        ranking = RankingService(
            feature_service=feature_service,
            ranking_model=ContractModel(),
        )
        job = jobs[0]
        candidate_map = {item.candidate_id: item for item in candidates}
        repositories = {
            "job": FakeProfileRepository({job.job_id: job}),
            "candidate": FakeProfileRepository(candidate_map),
        }
        direct_service = CrossEncoderRerankingService(
            ranking_service=ranking,
            cross_encoder_model=StableCrossEncoder(),
            job_repository=repositories["job"],
            candidate_repository=repositories["candidate"],
        )
        request = CrossEncoderMatchRunRequest(
            job_id=job.job_id,
            ranking_variant="cross_encoder_experiment",
            retrieval_pool_k=4,
            cross_encoder_pool_k=3,
            top_k=2,
        )
        direct = await direct_service.rerank_job_candidates(
            job.job_id,
            CrossEncoderRerankingRequest(
                retrieval_pool_k=4, cross_encoder_pool_k=3, top_k=2
            ),
        )
        lifecycle = FakeLifecycleRepository()
        wrapped = MatchRunService(
            lifecycle_repository=lifecycle,
            job_repository=repositories["job"],
            candidate_repository=repositories["candidate"],
            ranking_service_factory=lambda: ranking,
            cross_encoder_service_factory=lambda proxy: CrossEncoderRerankingService(
                ranking_service=proxy,
                cross_encoder_model=StableCrossEncoder(),
                job_repository=repositories["job"],
                candidate_repository=repositories["candidate"],
            ),
            run_id_factory=lambda: "ce-equivalence-run",
        )
        await wrapped.execute(request, request_id="ce-equivalence")
        return direct, lifecycle.results

    direct, persisted = asyncio.run(scenario())
    assert [item.entity_id for item in direct.results] == [
        item.candidate_id for item in persisted
    ]
    for source, stored in zip(direct.results, persisted):
        assert stored.retrieval_rank == source.retrieval_rank
        assert stored.ltr_rank == source.ltr_rank
        assert stored.ltr_score_raw == source.ltr_score_raw
        assert stored.cross_encoder_rank == source.cross_encoder_rank
        assert stored.cross_encoder_score_raw == source.cross_encoder_score_raw
