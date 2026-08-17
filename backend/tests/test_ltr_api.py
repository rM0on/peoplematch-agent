from __future__ import annotations

from fastapi.testclient import TestClient

from test_feature_service import _feature_service
from test_ltr_service import FakeModel


def test_ranking_api_returns_raw_scores_and_request_id(app) -> None:
    from app.api.dependencies import get_ranking_service
    from app.services.ranking.service import RankingService

    feature_service, _, _, jobs = _feature_service()
    app.dependency_overrides[get_ranking_service] = lambda: RankingService(
        feature_service=feature_service,
        ranking_model=FakeModel(),
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ranking/jobs/{jobs[0].job_id}/candidates",
            json={"candidate_pool_k": 4, "top_k": 2},
            headers={"X-Request-ID": "ltr-request"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["request_id"] == "ltr-request"
    assert response.headers["X-Request-ID"] == "ltr-request"
    assert payload["data"]["ranker_version"] == "ltr_ranker_v1"
    assert payload["data"]["feature_fingerprint"] == (
        "dc85c7237c6c67785199d221c919ae48c31c9a6323857070e6399d3eae365e42"
    )
    assert payload["data"]["candidate_pool_k"] == 4
    assert len(payload["data"]["results"]) == 2
    assert "ltr_score_raw" in payload["data"]["results"][0]
    assert "match_probability" not in response.text
    assert "final_match_score" not in response.text


def test_ranking_api_enforces_pool_bounds_and_does_not_accept_strategy(app) -> None:
    from app.api.dependencies import get_ranking_service
    from app.services.ranking.service import RankingService

    feature_service, _, _, jobs = _feature_service()
    app.dependency_overrides[get_ranking_service] = lambda: RankingService(
        feature_service=feature_service,
        ranking_model=FakeModel(),
    )
    with TestClient(app) as client:
        for body in (
            {"candidate_pool_k": 10, "top_k": 11},
            {"candidate_pool_k": 51, "top_k": 10},
            {"strategy": "dense"},
        ):
            response = client.post(
                f"/api/v1/ranking/jobs/{jobs[0].job_id}/candidates",
                json=body,
            )
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "validation_error"


def test_ranking_api_returns_typed_error_when_model_is_unavailable(app) -> None:
    from app.api.dependencies import get_ranking_service
    from app.exceptions import RankingModelUnavailableError

    def unavailable():
        raise RankingModelUnavailableError("model is unavailable")

    app.dependency_overrides[get_ranking_service] = unavailable
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ranking/jobs/job_001/candidates",
            json={"candidate_pool_k": 4, "top_k": 2},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ranking_model_unavailable"
    assert "model is unavailable" in response.json()["error"]["message"]


def test_ranking_api_returns_typed_error_on_contract_mismatch(app) -> None:
    from app.api.dependencies import get_ranking_service
    from app.exceptions import RankingContractMismatchError

    def mismatched():
        raise RankingContractMismatchError("stale model contract")

    app.dependency_overrides[get_ranking_service] = mismatched
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ranking/jobs/job_001/candidates",
            json={"candidate_pool_k": 4, "top_k": 2},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ranking_contract_mismatch"
    assert "stale model contract" in response.json()["error"]["message"]


def test_ranking_api_missing_job_uses_production_profile_not_found_path(app) -> None:
    from app.api.dependencies import get_ranking_service
    from app.services.ranking.service import RankingService

    feature_service, _, _, _ = _feature_service()
    app.dependency_overrides[get_ranking_service] = lambda: RankingService(
        feature_service=feature_service,
        ranking_model=FakeModel(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ranking/jobs/job_missing/candidates",
            json={"candidate_pool_k": 4, "top_k": 2},
            headers={"X-Request-ID": "ranking-missing"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"
    assert response.json()["request_id"] == "ranking-missing"
