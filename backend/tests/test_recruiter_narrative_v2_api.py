from __future__ import annotations

from fastapi.testclient import TestClient

from test_recruiter_narrative_service import _service
from test_recruiter_narrative_v2 import _case


def test_v2_api_creates_and_reads_versioned_narrative():
    from app.api.dependencies import get_recruiter_narrative_v2_query_service, get_recruiter_narrative_v2_service
    from app.main import create_app
    from app.services.explanation.presentation.service_v2 import RecruiterNarrativeV2Service

    _, _, _, _, payload = _case()
    _, repository, transport, _ = _service(payload)
    service = RecruiterNarrativeV2Service(repository=repository, provider=transport)
    app = create_app()
    app.dependency_overrides[get_recruiter_narrative_v2_service] = lambda: service
    app.dependency_overrides[get_recruiter_narrative_v2_query_service] = lambda: service
    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post("/api/v1/match-explanations/42/recruiter-narratives-v2")
        assert created.status_code == 201
        detail = client.get(f"/api/v1/recruiter-narratives-v2/{created.json()['data']['narrative_id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["narrative"]["contract_version"] == "recruiter_narrative_v2"
    assert detail.json()["data"]["narrative"]["decision_summary"]["text"].startswith("这位候选人")
    assert "api_key" not in detail.text.lower()
