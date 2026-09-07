from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / "data" / "samples" / "extraction"


def _text(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


def _service(provider, **kwargs):
    from app.services.profile_extraction.parser import ProfileExtractionService
    from app.services.profile_extraction.provider import MOCK_PROVIDER_DESCRIPTOR

    return ProfileExtractionService(
        provider,
        MOCK_PROVIDER_DESCRIPTOR,
        **kwargs,
    )


def test_candidate_and_job_parse_preview_use_mock_and_request_envelope(
    app, caplog
) -> None:
    from app.api.dependencies import get_profile_extraction_service
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    app.dependency_overrides[get_profile_extraction_service] = lambda: _service(
        MockStructuredOutputProvider.from_fixture_directory(FIXTURE_ROOT)
    )
    with caplog.at_level("INFO", logger="peoplematch.extraction"), TestClient(
        app
    ) as client:
        candidate = client.post(
            "/api/v1/candidates/parse",
            json={"text": _text("candidate_matching_resume.txt")},
            headers={"X-Request-ID": "candidate-preview"},
        )
        job = client.post(
            "/api/v1/jobs/parse",
            json={"text": _text("job_matching_engineer.txt"), "persist": False},
            headers={"X-Request-ID": "job-preview"},
        )

    for response, request_id, prompt_version in (
        (candidate, "candidate-preview", "candidate_extraction_prompt_v1"),
        (job, "job-preview", "job_extraction_prompt_v1"),
    ):
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == request_id
        payload = response.json()
        assert payload["success"] is True
        assert payload["error"] is None
        assert payload["request_id"] == request_id
        assert payload["data"]["record"] is None
        assert payload["data"]["extraction"]["provider"] == "deterministic_mock"
        assert payload["data"]["extraction"]["prompt_version"] == prompt_version
        assert len(payload["data"]["extraction"]["prompt_fingerprint"]) == 64
        assert payload["data"]["extraction"]["persisted"] is False

    completion_records = [
        record
        for record in caplog.records
        if record.name == "peoplematch.extraction"
    ]
    assert len(completion_records) == 2
    assert {record.task for record in completion_records} == {"candidate", "job"}
    assert {record.request_id for record in completion_records} == {
        "candidate-preview",
        "job-preview",
    }
    assert all(record.provider == "deterministic_mock" for record in completion_records)
    assert all(record.attempts == 1 for record in completion_records)
    assert all(len(record.input_fingerprint) == 64 for record in completion_records)
    assert _text("candidate_matching_resume.txt") not in caplog.text
    assert _text("job_matching_engineer.txt") not in caplog.text


def test_parse_request_forbids_identity_and_provider_control(app) -> None:
    from app.api.dependencies import get_profile_extraction_service
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    app.dependency_overrides[get_profile_extraction_service] = lambda: _service(
        MockStructuredOutputProvider.from_fixture_directory(FIXTURE_ROOT)
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/candidates/parse",
            json={
                "text": _text("candidate_matching_resume.txt"),
                "candidate_id": "cand_005",
                "data_origin": "synthetic_sandbox",
                "provider": "real",
            },
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert _text("candidate_matching_resume.txt") not in response.text
    assert all(
        "input" not in detail
        for detail in response.json()["error"]["details"]
    )


def test_invalid_provider_output_uses_upstream_error_without_raw_output(app) -> None:
    from app.api.dependencies import get_profile_extraction_service
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    app.dependency_overrides[get_profile_extraction_service] = lambda: _service(
        MockStructuredOutputProvider.with_responses(["private malformed raw", "still private"]),
        max_attempts=2,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/candidates/parse",
            json={"text": _text("candidate_matching_resume.txt")},
        )
    assert response.status_code == 502
    payload = response.json()
    assert payload["error"]["code"] == "provider_output_invalid"
    assert "private malformed raw" not in response.text


def test_unknown_mock_input_uses_typed_private_error_envelope(app) -> None:
    from app.api.dependencies import get_profile_extraction_service
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    app.dependency_overrides[get_profile_extraction_service] = lambda: _service(
        MockStructuredOutputProvider.from_fixture_directory(FIXTURE_ROOT)
    )
    source = (
        "Unknown synthetic candidate source with enough text for request validation, "
        "but no deterministic mock registry entry."
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/candidates/parse",
            json={"text": source},
            headers={"X-Request-ID": "unknown-mock-input"},
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "mock_input_not_supported"
    assert response.headers["X-Request-ID"] == "unknown-mock-input"
    assert payload["request_id"] == "unknown-mock-input"
    assert source not in response.text


def test_unimplemented_provider_does_not_fall_back_to_mock(monkeypatch) -> None:
    from app.api import dependencies
    from app.core.config import Settings
    from app.exceptions import ProviderUnavailableError

    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: Settings(_env_file=None, extraction_provider="unimplemented"),
    )
    with pytest.raises(ProviderUnavailableError, match="is not implemented"):
        dependencies.get_profile_extraction_service(session=None)


@pytest.mark.parametrize(
    "failure,expected_code",
    [
        (RuntimeError("provider offline"), "provider_unavailable"),
        (TimeoutError(), "provider_timeout"),
    ],
)
def test_provider_failures_use_typed_error_envelopes(
    app, failure: Exception, expected_code: str
) -> None:
    from app.api.dependencies import get_profile_extraction_service
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    app.dependency_overrides[get_profile_extraction_service] = lambda: _service(
        MockStructuredOutputProvider.with_failures([failure])
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/candidates/parse",
            json={"text": _text("candidate_matching_resume.txt")},
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == expected_code
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
