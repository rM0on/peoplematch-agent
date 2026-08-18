from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient


def _response_data():
    from app.schemas.cross_encoder import (
        CrossEncoderRerankingResponseData,
        CrossEncoderRerankingResult,
    )

    return CrossEncoderRerankingResponseData(
        reranker_version="cross_encoder_reranker_v1",
        model_id="cross-encoder/ms-marco-MiniLM-L6-v2",
        model_revision="233902d25c440f23af6f7d6e94d2946bac0bee0a",
        snapshot_fingerprint="a" * 64,
        text_schema_version="cross_encoder_text_v1",
        text_contract_fingerprint="b" * 64,
        pair_order="job_then_candidate",
        retrieval_pool_k=20,
        cross_encoder_pool_k=10,
        top_k=5,
        results=[
            CrossEncoderRerankingResult(
                entity_id="cand_001",
                retrieval_rank=1,
                ltr_rank=1,
                ltr_score_raw=1.0,
                cross_encoder_rank=1,
                cross_encoder_score_raw=0.25,
                ranker_version="ltr_ranker_v1",
                model_sha256="c" * 64,
                feature_version="feature_schema_v1",
                feature_fingerprint="d" * 64,
            )
        ],
    )


class _FakeCrossEncoderService:
    def __init__(self, response=None, error=None):
        self.response = response or _response_data()
        self.error = error
        self.calls = []

    async def rerank_job_candidates(self, job_id, payload):
        self.calls.append((job_id, payload))
        if self.error:
            raise self.error
        return self.response


def test_cross_encoder_api_returns_auditable_raw_scores_and_request_id(app) -> None:
    from app.api.dependencies import get_cross_encoder_reranking_service

    service = _FakeCrossEncoderService()
    app.dependency_overrides[get_cross_encoder_reranking_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/reranking/jobs/job_001/candidates",
            json={},
            headers={"X-Request-ID": "ce-request"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["request_id"] == "ce-request"
    assert response.headers["X-Request-ID"] == "ce-request"
    assert payload["data"]["retrieval_pool_k"] == 20
    assert payload["data"]["cross_encoder_pool_k"] == 10
    assert payload["data"]["top_k"] == 5
    assert "cross_encoder_score_raw" in payload["data"]["results"][0]
    for forbidden in ("probability", "confidence", "match_percentage", "final_match_score"):
        assert forbidden not in response.text
    assert service.calls[0][1].retrieval_pool_k == 20


def test_cross_encoder_api_rejects_invalid_cascade_bounds(app) -> None:
    from app.api.dependencies import get_cross_encoder_reranking_service

    app.dependency_overrides[get_cross_encoder_reranking_service] = lambda: _FakeCrossEncoderService()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/reranking/jobs/job_001/candidates",
            json={"retrieval_pool_k": 10, "cross_encoder_pool_k": 11, "top_k": 5},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_cross_encoder_api_exposes_typed_model_and_contract_failures(app) -> None:
    from app.api.dependencies import get_cross_encoder_reranking_service
    from app.exceptions import (
        CrossEncoderContractMismatchError,
        CrossEncoderModelUnavailableError,
    )

    for error, status, code in (
        (CrossEncoderModelUnavailableError("snapshot missing"), 503, "cross_encoder_model_unavailable"),
        (CrossEncoderContractMismatchError("stale contract"), 409, "cross_encoder_contract_mismatch"),
    ):
        app.dependency_overrides[get_cross_encoder_reranking_service] = lambda error=error: _FakeCrossEncoderService(error=error)
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/reranking/jobs/job_001/candidates",
                json={},
            )
        assert response.status_code == status
        assert response.json()["error"]["code"] == code


def test_cross_encoder_api_missing_job_uses_profile_not_found_contract(app) -> None:
    from app.api.dependencies import get_cross_encoder_reranking_service
    from app.services.cross_encoder.service import CrossEncoderRerankingService

    ranking = SimpleNamespace(
        rank_job_candidates=lambda *_args, **_kwargs: None,
    )

    async def rank_job_candidates(*_args, **_kwargs):
        return SimpleNamespace(results=[])

    async def get_record_by_id(_identifier):
        return None

    async def list_all_records():
        return []

    ranking.rank_job_candidates = rank_job_candidates
    repository = SimpleNamespace(
        get_record_by_id=get_record_by_id,
        list_all_records=list_all_records,
    )
    service = CrossEncoderRerankingService(
        ranking_service=ranking,
        cross_encoder_model=SimpleNamespace(),
        job_repository=repository,
        candidate_repository=repository,
    )
    app.dependency_overrides[get_cross_encoder_reranking_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/reranking/jobs/job_missing/candidates",
            json={},
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"
