from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import get_match_run_service
from app.exceptions import MatchRunExecutionError
from app.main import create_app


def _completed_run(variant: str = "ltr"):
    now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    result = SimpleNamespace(
        id=41,
        candidate_id="cand_001",
        result_rank=1,
        candidate_input_fingerprint="a" * 64,
        retrieval_rank=2,
        matched_channels=["dense", "sparse"],
        dense_rank=2,
        dense_score=0.75,
        sparse_rank=1,
        sparse_score=4.5,
        fusion_score=0.0325,
        semantic_score=0.75,
        skill_fit_score=0.8,
        project_evidence_score=0.6,
        role_direction_score=0.7,
        ai_tool_score=0.5,
        location_score=1.0,
        seniority_score=1.0,
        missing_penalty=0.2,
        overclaim_penalty=0.0,
        feature_diagnostics_contract_version="selected_feature_diagnostics_v1",
        feature_diagnostics={"contract_version": "selected_feature_diagnostics_v1"},
        ltr_rank=1,
        ltr_score_raw=0.3125,
        cross_encoder_rank=1 if variant != "ltr" else None,
        cross_encoder_score_raw=1.25 if variant != "ltr" else None,
    )
    step_names = ["resolve_inputs", "phase6_ltr_rank"]
    if variant != "ltr":
        step_names.append("phase7_cross_encoder_rerank")
    step_names.append("persist_results")
    steps = [
        SimpleNamespace(
            sequence=index,
            step_name=name,
            status="COMPLETED",
            started_at=now,
            finished_at=now,
            duration_ms=1.0,
            input_refs={"run_id": "11111111-1111-1111-1111-111111111111"},
            output_refs={"result_count": 1},
            contract_version="match_run_step_refs_v1",
            error_code=None,
            error_detail_safe=None,
        )
        for index, name in enumerate(step_names, 1)
    ]
    return SimpleNamespace(
        run_id="11111111-1111-1111-1111-111111111111",
        requested_job_id="job_001",
        job_id="job_001",
        request_id="http-request-1",
        ranking_variant=variant,
        status="COMPLETED",
        created_at=now,
        started_at=now,
        completed_at=now,
        request_parameters={"candidate_pool_k": 20, "top_k": 10},
        workflow_version="match_run_workflow_v1",
        workflow_fingerprint="b" * 64,
        ranking_input_contract_version="ranking_input_snapshot_v1",
        ranking_input_fingerprint="c" * 64,
        retrieval_document_version="retrieval_doc_v4",
        retrieval_configuration_fingerprint="d" * 64,
        retrieval_provenance={"index_freshness": "fresh"},
        feature_version="feature_schema_v1",
        feature_fingerprint="e" * 64,
        ranker_version="ltr_ranker_v1",
        ranker_model_sha256="f" * 64,
        ce_provenance={"calibration": False} if variant != "ltr" else None,
        result_count=1,
        result_fingerprint="1" * 64,
        error_code=None,
        error_detail_safe=None,
        results=[result],
        steps=steps,
    )


class FakeMatchRunService:
    def __init__(self):
        self.run = _completed_run()
        self.execute_calls = []
        self.get_calls = []
        self.list_calls = []

    async def execute(self, payload, *, request_id):
        self.execute_calls.append((payload, request_id))
        self.run.request_id = request_id
        self.run.ranking_variant = payload.ranking_variant.value
        return self.run

    async def get(self, run_id):
        self.get_calls.append(run_id)
        return self.run

    async def list(self, **filters):
        self.list_calls.append(filters)
        return [self.run], 1


def _client(service):
    app = create_app()
    app.dependency_overrides[get_match_run_service] = lambda: service
    return TestClient(app)


def test_post_default_ltr_returns_durable_run_without_forbidden_fields() -> None:
    service = FakeMatchRunService()
    with _client(service) as client:
        response = client.post(
            "/api/v1/match-runs",
            json={"job_id": "job_001"},
            headers={"X-Request-ID": "http-post"},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["request_id"] == "http-post"
    assert body["data"]["run_id"] != body["data"]["request_id"]
    assert body["data"]["ranking_variant"] == "ltr"
    serialized = response.text.lower()
    for forbidden in (
        "probability",
        "confidence",
        "match_percentage",
        "final_match_score",
        "explanation",
    ):
        assert forbidden not in serialized


def test_post_explicit_ce_and_request_validation() -> None:
    service = FakeMatchRunService()
    with _client(service) as client:
        ce = client.post(
            "/api/v1/match-runs",
            json={"job_id": "job_001", "ranking_variant": "cross_encoder_experiment"},
        )
        invalid_variant = client.post(
            "/api/v1/match-runs",
            json={"job_id": "job_001", "ranking_variant": "automatic"},
        )
        invalid_bounds = client.post(
            "/api/v1/match-runs",
            json={"job_id": "job_001", "candidate_pool_k": 2, "top_k": 3},
        )
    assert ce.status_code == 201
    assert service.execute_calls[0][0].ranking_variant.value == "cross_encoder_experiment"
    assert invalid_variant.status_code == 422
    assert invalid_bounds.status_code == 422


def test_get_reads_persisted_run_and_never_executes_ranking() -> None:
    service = FakeMatchRunService()
    with _client(service) as client:
        response = client.get(f"/api/v1/match-runs/{service.run.run_id}")
    assert response.status_code == 200
    assert service.get_calls == [service.run.run_id]
    assert service.execute_calls == []
    assert response.json()["data"]["results"][0]["ltr_score_raw"] == 0.3125


def test_get_exposes_the_persisted_match_result_feedback_locator() -> None:
    service = FakeMatchRunService()
    with _client(service) as client:
        response = client.get(f"/api/v1/match-runs/{service.run.run_id}")

    assert response.status_code == 200
    assert response.json()["data"]["results"][0]["match_result_id"] == 41


def test_history_routes_do_not_construct_any_ranking_runtime(monkeypatch) -> None:
    service = FakeMatchRunService()
    import app.api.dependencies as dependencies

    def forbidden(*_args, **_kwargs):
        raise AssertionError("history routes must not construct ranking runtime")

    for name in (
        "RetrievalService",
        "FeatureEngineeringService",
        "RankingService",
        "CrossEncoderRerankingService",
        "get_runtime_embedding_provider",
        "get_runtime_vector_store",
        "get_runtime_ranking_model",
        "get_runtime_cross_encoder_model",
    ):
        monkeypatch.setattr(dependencies, name, forbidden)

    with _client(service) as client:
        detail = client.get(f"/api/v1/match-runs/{service.run.run_id}")
        summary = client.get("/api/v1/match-runs")

    assert detail.status_code == 200
    assert summary.status_code == 200
    assert detail.json()["data"]["results"]
    assert summary.json()["data"]["items"]


def test_list_uses_conservative_pagination_filters() -> None:
    service = FakeMatchRunService()
    with _client(service) as client:
        response = client.get(
            "/api/v1/match-runs",
            params={
                "limit": 10,
                "offset": 2,
                "job_id": "job_001",
                "status": "COMPLETED",
                "ranking_variant": "ltr",
            },
        )
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    assert service.list_calls == [
        {
            "limit": 10,
            "offset": 2,
            "job_id": "job_001",
            "status": "COMPLETED",
            "ranking_variant": "ltr",
        }
    ]


def test_execution_error_exposes_run_id_without_raw_detail() -> None:
    class FailingService(FakeMatchRunService):
        async def execute(self, payload, *, request_id):
            raise MatchRunExecutionError(
                "22222222-2222-2222-2222-222222222222",
                "profile_not_found",
                404,
            )

    with _client(FailingService()) as client:
        response = client.post("/api/v1/match-runs", json={"job_id": "job_missing"})
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "match_run_execution_failed",
        "message": "Match run execution failed",
        "details": {
            "run_id": "22222222-2222-2222-2222-222222222222",
            "failure_code": "profile_not_found",
        },
    }


def test_match_run_dependency_does_not_construct_runtime_for_history_reads(monkeypatch) -> None:
    import app.api.dependencies as dependencies

    def forbidden(*args, **kwargs):
        raise AssertionError("ranking runtime must remain lazy for GET/LIST")

    monkeypatch.setattr(dependencies, "get_runtime_ranking_model", forbidden)
    monkeypatch.setattr(dependencies, "get_runtime_cross_encoder_model", forbidden)
    monkeypatch.setattr(dependencies, "get_runtime_embedding_provider", forbidden)
    monkeypatch.setattr(dependencies, "get_session_factory", lambda: object())
    monkeypatch.setattr(dependencies, "get_repeatable_read_session_factory", lambda: object())
    service = dependencies.get_match_run_service(object())
    assert service.execution_session_factory is not None
