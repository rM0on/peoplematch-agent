from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from test_feature_service import _feature_service


def test_feature_routes_support_both_directions_and_request_ids(app) -> None:
    from app.api.dependencies import get_feature_engineering_service

    service, _, candidates, jobs = _feature_service()
    app.dependency_overrides[get_feature_engineering_service] = lambda: service
    with TestClient(app) as client:
        forward = client.post(
            f"/api/v1/features/jobs/{jobs[0].job_id}/candidates",
            json={"strategy": "sparse", "top_k": 3},
            headers={"X-Request-ID": "feature-forward"},
        )
        reverse = client.post(
            f"/api/v1/features/candidates/{candidates[0].candidate_id}/jobs",
            json={"strategy": "sparse", "top_k": 2},
            headers={"X-Request-ID": "feature-reverse"},
        )

    assert forward.status_code == 200
    assert forward.headers["X-Request-ID"] == "feature-forward"
    payload = forward.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["request_id"] == "feature-forward"
    assert payload["data"]["feature_version"] == "feature_schema_v1"
    assert len(payload["data"]["feature_fingerprint"]) == 64
    assert payload["data"]["results"]
    assert reverse.status_code == 200
    assert reverse.json()["data"]["retrieval_diagnostics"]["result_type"] == "job"


def test_feature_route_inherits_retrieval_filter_behavior(app) -> None:
    from app.api.dependencies import get_feature_engineering_service

    service, retrieval, _, jobs = _feature_service()
    city = retrieval.vector_store.documents["candidates"][0].cities[0]
    app.dependency_overrides[get_feature_engineering_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/features/jobs/{jobs[0].job_id}/candidates",
            json={"strategy": "sparse", "top_k": 10, "filters": {"cities": [city]}},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["retrieval_diagnostics"]["filters_applied"] is True
    eligible = {
        item.entity_id
        for item in retrieval.vector_store.documents["candidates"]
        if city in item.cities
    }
    assert {item["entity_id"] for item in data["results"]} <= eligible


@pytest.mark.parametrize(
    "body",
    [
        {"top_k": 0},
        {"top_k": 51},
        {"strategy": "rerank"},
        {"filters": {"archetype": "forbidden"}},
        {"labels": [3]},
    ],
)
def test_feature_request_is_strict(body, app) -> None:
    from app.api.dependencies import get_feature_engineering_service

    service, _, _, jobs = _feature_service()
    app.dependency_overrides[get_feature_engineering_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/features/jobs/{jobs[0].job_id}/candidates", json=body
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_feature_missing_profile_uses_existing_error_shape(app) -> None:
    from app.api.dependencies import get_feature_engineering_service

    service, _, _, _ = _feature_service()
    app.dependency_overrides[get_feature_engineering_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/features/jobs/job_missing/candidates",
            json={"strategy": "sparse"},
            headers={"X-Request-ID": "feature-missing"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"
    assert response.json()["request_id"] == "feature-missing"


def test_feature_missing_candidate_uses_existing_error_shape(app) -> None:
    from app.api.dependencies import get_feature_engineering_service

    service, _, _, _ = _feature_service()
    app.dependency_overrides[get_feature_engineering_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/features/candidates/cand_missing/jobs",
            json={"strategy": "sparse"},
            headers={"X-Request-ID": "feature-missing-candidate"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"
    assert response.json()["request_id"] == "feature-missing-candidate"


@pytest.mark.parametrize(
    "error_type,error_code,status_code",
    [
        ("contract", "feature_contract_violation", 500),
        ("profile", "invalid_profile_state", 409),
        ("retrieval", "vector_store_unavailable", 503),
    ],
)
def test_feature_failures_remain_typed_and_private(
    error_type, error_code, status_code, app
) -> None:
    from app.api.dependencies import get_feature_engineering_service
    from app.exceptions import (
        FeatureContractViolationError,
        InvalidProfileStateError,
        VectorStoreUnavailableError,
    )

    exception = {
        "contract": FeatureContractViolationError,
        "profile": InvalidProfileStateError,
        "retrieval": VectorStoreUnavailableError,
    }[error_type]

    class FailingService:
        async def features_for_job_candidates(self, job_id, request):
            raise exception("private-profile-or-infrastructure-detail")

    app.dependency_overrides[get_feature_engineering_service] = lambda: FailingService()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/features/jobs/job_001/candidates",
            json={"strategy": "sparse"},
            headers={"X-Request-ID": f"feature-{error_type}"},
        )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    assert response.json()["request_id"] == f"feature-{error_type}"
