from __future__ import annotations

from fastapi.testclient import TestClient

from test_recruiter_narrative_service import _service


def test_recruiter_narrative_create_and_historical_read_use_independent_api():
    from app.api.dependencies import get_recruiter_narrative_query_service, get_recruiter_narrative_service
    from app.main import create_app

    service, repository, transport, _ = _service()
    app = create_app()
    app.dependency_overrides[get_recruiter_narrative_service] = lambda: service
    app.dependency_overrides[get_recruiter_narrative_query_service] = lambda: service
    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post("/api/v1/match-explanations/42/recruiter-narratives")
        assert created.status_code == 201
        narrative_id = created.json()["data"]["narrative_id"]
        detail = client.get(f"/api/v1/recruiter-narratives/{narrative_id}")

    assert detail.status_code == 200
    assert detail.json()["data"]["narrative"]["candidate_summary"]["text"].startswith("候选人")
    assert detail.json()["data"]["source_explanation_id"] == 42
    assert detail.json()["data"]["validation_status"] == "PASSED"
    assert len(transport.requests) == 1
    assert "api_key" not in detail.text.lower()


def test_invalid_narrative_api_failure_is_safe_and_has_no_model_text():
    from app.api.dependencies import get_recruiter_narrative_service
    from app.main import create_app

    service, repository, transport, _ = _service()
    transport.payload["strengths"][0]["text"] = "支撑百万用户，使用 Python。"
    app = create_app()
    app.dependency_overrides[get_recruiter_narrative_service] = lambda: service
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/match-explanations/42/recruiter-narratives")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "narrative_generation_failed"
    assert "百万" not in response.text
    assert repository.saved[0].validated_content_json is None


def test_historical_narrative_read_does_not_require_provider_configuration(monkeypatch):
    from app.api import dependencies

    class _Repository:
        pass

    monkeypatch.setattr(dependencies, "get_session_factory", lambda: object())
    monkeypatch.setattr(dependencies, "RecruiterNarrativeRepository", lambda _factory: _Repository())
    monkeypatch.setattr(
        dependencies,
        "get_runtime_recruiter_narrative_provider",
        lambda: (_ for _ in ()).throw(AssertionError("read must not initialize provider")),
    )

    service = dependencies.get_recruiter_narrative_query_service()
    assert service.provider is None
