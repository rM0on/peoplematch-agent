from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings


STATUS_PATH = "/api/v1/system/ai-provider-status"


def _client_with_settings(app, settings: Settings) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_mock_status_is_ready_but_arbitrary_input_is_not_supported(client) -> None:
    response = client.get(STATUS_PATH)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["request_id"]
    assert payload["data"]["extraction"] == {
        "task": "extraction",
        "mode": "mock",
        "configured": True,
        "provider_name": "deterministic_mock",
        "configured_model": None,
        "arbitrary_input_supported": False,
    }
    assert payload["data"]["explanation"] == {
        "task": "explanation",
        "mode": "mock",
        "configured": True,
        "provider_name": "deterministic_mock",
        "configured_model": None,
        "arbitrary_input_supported": False,
    }


def test_configured_generic_status_reports_safe_readiness_without_connectivity_claim(
    app,
) -> None:
    settings = Settings(
        _env_file=None,
        extraction_provider="openai_compatible",
        explanation_provider="openai_compatible",
        llm_base_url="https://provider.example/v1",
        llm_model="provider-model",
        llm_api_key="must-not-leak",
    )

    with _client_with_settings(app, settings) as client:
        response = client.get(STATUS_PATH)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["extraction"] == {
        "task": "extraction",
        "mode": "openai_compatible",
        "configured": True,
        "provider_name": "openai_compatible",
        "configured_model": "provider-model",
        "arbitrary_input_supported": True,
    }
    assert data["explanation"] == {
        "task": "explanation",
        "mode": "openai_compatible",
        "configured": True,
        "provider_name": "openai_compatible",
        "configured_model": "provider-model",
        "arbitrary_input_supported": True,
    }
    assert "connected" not in response.text.casefold()


def test_incomplete_real_status_is_closed_and_does_not_return_validation_details(app) -> None:
    settings = Settings(
        _env_file=None,
        extraction_provider="openai_compatible",
        explanation_provider="mock",
        llm_base_url="https://provider.example/v1",
        llm_model="provider-model",
        llm_api_key=None,
    )

    with _client_with_settings(app, settings) as client:
        response = client.get(STATUS_PATH)

    assert response.status_code == 200
    extraction = response.json()["data"]["extraction"]
    assert extraction == {
        "task": "extraction",
        "mode": "openai_compatible",
        "configured": False,
        "provider_name": "openai_compatible",
        "configured_model": None,
        "arbitrary_input_supported": False,
    }
    assert "API key must be configured" not in response.text
    assert response.json()["data"]["explanation"]["mode"] == "mock"


def test_independent_mixed_modes_remain_independently_reported(app) -> None:
    settings = Settings(
        _env_file=None,
        extraction_provider="openai_compatible",
        explanation_provider="mock",
        llm_base_url="https://provider.example/v1",
        llm_model="provider-model",
        llm_api_key="must-not-leak",
    )

    with _client_with_settings(app, settings) as client:
        response = client.get(STATUS_PATH)

    data = response.json()["data"]
    assert data["extraction"]["mode"] == "openai_compatible"
    assert data["extraction"]["configured"] is True
    assert data["explanation"]["mode"] == "mock"
    assert data["explanation"]["configured"] is True


def test_status_never_returns_secret_url_prompt_or_raw_payload(app) -> None:
    private_key = "phase15-status-private-key"
    private_url = "https://private-provider.example/v1"
    settings = Settings(
        _env_file=None,
        extraction_provider="openai_compatible",
        explanation_provider="openai_compatible",
        llm_base_url=private_url,
        llm_model="provider-model",
        llm_api_key=private_key,
    )

    with _client_with_settings(app, settings) as client:
        response = client.get(STATUS_PATH)

    assert response.status_code == 200
    for forbidden in (
        private_key,
        private_url,
        "Authorization",
        "api_key",
        "base_url",
        "raw_prompt",
        "raw_payload",
        "configuration_fingerprint",
    ):
        assert forbidden not in response.text


def test_provider_status_schema_is_closed() -> None:
    from pydantic import ValidationError

    from app.schemas.provider_status import AIProviderTaskStatus

    try:
        AIProviderTaskStatus.model_validate(
            {
                "task": "extraction",
                "mode": "mock",
                "configured": True,
                "provider_name": "deterministic_mock",
                "configured_model": None,
                "arbitrary_input_supported": False,
                "api_key": "forged",
            }
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("provider status contract accepted an unknown field")
