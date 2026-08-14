from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from test_retrieval_service import _service


def test_retrieval_routes_support_both_directions_and_request_ids(app) -> None:
    from app.api.dependencies import get_retrieval_service

    service, candidates, jobs = _service()
    app.dependency_overrides[get_retrieval_service] = lambda: service
    with TestClient(app) as client:
        candidates_response = client.post(
            f"/api/v1/retrieval/jobs/{jobs[0].job_id}/candidates",
            json={},
            headers={"X-Request-ID": "job-retrieval-request"},
        )
        jobs_response = client.post(
            f"/api/v1/retrieval/candidates/{candidates[0].candidate_id}/jobs",
            json={"strategy": "sparse", "top_k": 2},
            headers={"X-Request-ID": "candidate-retrieval-request"},
        )

    assert candidates_response.status_code == 200
    assert candidates_response.headers["X-Request-ID"] == "job-retrieval-request"
    candidate_payload = candidates_response.json()
    assert candidate_payload["request_id"] == "job-retrieval-request"
    assert candidate_payload["success"] is True
    assert candidate_payload["error"] is None
    assert candidate_payload["data"]["diagnostics"]["strategy"] == "hybrid"
    assert candidate_payload["data"]["results"]

    assert jobs_response.status_code == 200
    assert jobs_response.headers["X-Request-ID"] == "candidate-retrieval-request"
    job_payload = jobs_response.json()
    assert job_payload["data"]["diagnostics"]["strategy"] == "sparse"
    assert job_payload["data"]["diagnostics"]["result_type"] == "job"
    assert "vector" not in jobs_response.text
    assert "relevance" not in jobs_response.text


@pytest.mark.parametrize(
    "body",
    [
        {"top_k": 0},
        {"top_k": 51},
        {"strategy": "final"},
        {"filters": {"archetype": "forbidden"}},
        {"collection": "caller_controlled"},
        {"embedding_model": "caller_controlled"},
    ],
)
def test_retrieval_request_is_strict(body, app) -> None:
    from app.api.dependencies import get_retrieval_service

    service, _, jobs = _service()
    app.dependency_overrides[get_retrieval_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/retrieval/jobs/{jobs[0].job_id}/candidates", json=body
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_retrieval_missing_profile_uses_existing_error_semantics(app) -> None:
    from app.api.dependencies import get_retrieval_service

    service, _, _ = _service()
    app.dependency_overrides[get_retrieval_service] = lambda: service
    with TestClient(app) as client:
        job_response = client.post(
            "/api/v1/retrieval/jobs/job_missing/candidates", json={}
        )
        candidate_response = client.post(
            "/api/v1/retrieval/candidates/candidate_missing/jobs", json={}
        )

    for response in (job_response, candidate_response):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "profile_not_found"


@pytest.mark.parametrize(
    "exception,status_code,error_code",
    [
        ("missing", 503, "retrieval_index_missing"),
        ("stale", 409, "retrieval_index_stale"),
        ("vector", 503, "vector_store_unavailable"),
        ("embedding", 503, "embedding_provider_unavailable"),
    ],
)
def test_retrieval_infrastructure_errors_are_typed_and_private(
    exception, status_code, error_code, app
) -> None:
    from app.api.dependencies import get_retrieval_service
    from app.exceptions import (
        EmbeddingProviderUnavailableError,
        RetrievalIndexMissingError,
        RetrievalIndexStaleError,
        VectorStoreUnavailableError,
    )

    error_type = {
        "missing": RetrievalIndexMissingError,
        "stale": RetrievalIndexStaleError,
        "vector": VectorStoreUnavailableError,
        "embedding": EmbeddingProviderUnavailableError,
    }[exception]

    class FailingService:
        async def retrieve_candidates(self, job_id, request):
            raise error_type("private-qdrant-or-model-detail")

    app.dependency_overrides[get_retrieval_service] = lambda: FailingService()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/retrieval/jobs/job_001/candidates",
            json={},
            headers={"X-Request-ID": f"error-{exception}"},
        )

    assert response.status_code == status_code
    payload = response.json()
    assert payload["error"]["code"] == error_code
    assert payload["request_id"] == f"error-{exception}"
    assert response.headers["X-Request-ID"] == f"error-{exception}"
