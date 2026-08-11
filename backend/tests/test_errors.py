from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_unknown_endpoint_uses_api_error_schema(client: TestClient) -> None:
    response = client.get(
        "/does-not-exist",
        headers={"X-Request-ID": "missing-route-id"},
    )

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "missing-route-id"
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "details": None,
        },
        "request_id": "missing-route-id",
    }


def test_validation_error_uses_api_error_schema(app: FastAPI) -> None:
    @app.get("/_test/items/{item_id}", include_in_schema=False)
    async def validation_target(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    with TestClient(app) as client:
        response = client.get(
            "/_test/items/not-an-integer",
            headers={"X-Request-ID": "validation-id"},
        )

    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "validation-id"
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "Request validation failed"
    assert payload["error"]["details"]
    assert payload["request_id"] == "validation-id"
