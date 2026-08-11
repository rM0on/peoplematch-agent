from uuid import UUID

from fastapi.testclient import TestClient


def test_health_success(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["service"] == "peoplematch-backend"
    assert payload["error"] is None
    assert payload["request_id"]


def test_request_id_generated(client: TestClient) -> None:
    response = client.get("/health")

    request_id = response.json()["request_id"]
    assert response.headers["X-Request-ID"] == request_id
    assert str(UUID(request_id)) == request_id


def test_request_id_propagation(client: TestClient) -> None:
    response = client.get(
        "/health",
        headers={"X-Request-ID": "test-request-id"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"
    assert response.json()["request_id"] == "test-request-id"
