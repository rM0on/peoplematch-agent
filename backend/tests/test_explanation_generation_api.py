from __future__ import annotations

import inspect
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest


MATCH_RUN_ID = "00000000-0000-0000-0000-000000000901"
EXPLANATION_RUN_ID = "00000000-0000-0000-0000-000000000931"


class _Service:
    def __init__(self) -> None:
        self.calls = []

    async def generate(self, match_run_id: str, *, requested_top_k: int, request_id: str):
        from app.services.explanation.generation.orchestration import (
            ExplanationGenerationResult,
        )

        self.calls.append(("generate", match_run_id, requested_top_k, request_id))
        return ExplanationGenerationResult(
            explanation_run_id=EXPLANATION_RUN_ID,
            match_run_id=match_run_id,
            status="COMPLETED",
            requested_top_k=requested_top_k,
            effective_top_k=requested_top_k,
            explanation_count=requested_top_k,
            attempt_count=1,
            repaired=False,
        )

    async def get(self, explanation_run_id: str):
        self.calls.append(("get", explanation_run_id))
        return {
            "explanation_run_id": explanation_run_id,
            "match_run_id": MATCH_RUN_ID,
            "status": "COMPLETED",
            "requested_top_k": 1,
            "effective_top_k": 1,
            "explanation_count": 1,
            "provider_kind": "openai_compatible",
            "provider_name": "deepseek",
            "configured_model": "deepseek-chat",
            "prompt_version": "explanation_prompt_v1",
            "attempt_count": 1,
            "repaired": False,
            "error_code": None,
            "error_detail_safe": None,
            "explanations": [],
        }

    async def list(self, match_run_id: str, *, limit: int, offset: int):
        self.calls.append(("list", match_run_id, limit, offset))
        return [], 0


def _client(service: _Service):
    from app.api.dependencies import get_explanation_generation_service
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_explanation_generation_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_explanation_generate_get_and_list_routes_are_backend_only() -> None:
    service = _Service()
    with _client(service) as client:
        created = client.post(
            f"/api/v1/match-runs/{MATCH_RUN_ID}/explanations",
            json={"top_k": 1},
            headers={"X-Request-ID": "request-phase94"},
        )
        detail = client.get(f"/api/v1/explanation-runs/{EXPLANATION_RUN_ID}")
        listed = client.get(
            f"/api/v1/match-runs/{MATCH_RUN_ID}/explanation-runs?limit=10&offset=0"
        )

    assert created.status_code == 201
    assert created.json()["data"]["explanation_run_id"] == EXPLANATION_RUN_ID
    assert detail.status_code == 200
    assert detail.json()["data"]["explanation_run_id"] == EXPLANATION_RUN_ID
    for field in (
        "provider_kind",
        "provider_name",
        "configured_model",
        "prompt_version",
    ):
        assert created.json()["data"][field] == detail.json()["data"][field]
    assert listed.status_code == 200
    assert listed.json()["data"] == {
        "items": [],
        "total": 0,
        "limit": 10,
        "offset": 0,
    }
    assert [call[0] for call in service.calls] == [
        "generate",
        "get",
        "get",
        "list",
    ]


def test_generate_request_cannot_select_provider_or_model() -> None:
    service = _Service()
    with _client(service) as client:
        for forbidden_body in (
            {"top_k": 1, "provider": "deepseek"},
            {"top_k": 1, "model": "private-model"},
            {"top_k": 1, "provider": "mock", "model": "test"},
        ):
            response = client.post(
                f"/api/v1/match-runs/{MATCH_RUN_ID}/explanations",
                json=forbidden_body,
            )
            assert response.status_code == 422
            body = response.json()
            assert body["error"]["code"] == "validation_error"
            assert "private-model" not in response.text
    assert service.calls == []


def test_generation_failure_response_exposes_only_run_id_and_bounded_code() -> None:
    from app.services.explanation.generation.errors import (
        ExplanationGenerationFailedError,
    )

    class FailedService(_Service):
        async def generate(self, *args, **kwargs):
            raise ExplanationGenerationFailedError(
                explanation_run_id=EXPLANATION_RUN_ID,
                failure_code="grounding_failure",
            )

    with _client(FailedService()) as client:
        response = client.post(
            f"/api/v1/match-runs/{MATCH_RUN_ID}/explanations",
            json={"top_k": 1},
        )

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "explanation_generation_failed",
        "message": "Explanation generation failed",
        "details": {
            "explanation_run_id": EXPLANATION_RUN_ID,
            "failure_code": "grounding_failure",
        },
    }
    assert not any(
        forbidden in response.text.lower()
        for forbidden in ("stack", "traceback", "prompt", "provider response", "api key")
    )


def test_runtime_provider_configuration_failure_maps_to_safe_unavailable_error(
    monkeypatch,
) -> None:
    from app.api import dependencies
    from app.exceptions import ProviderUnavailableError

    dependencies.get_runtime_explanation_provider.cache_clear()
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(explanation_provider="unconfigured"),
    )
    try:
        with pytest.raises(ProviderUnavailableError, match="Explanation provider"):
            dependencies.get_runtime_explanation_provider()
    finally:
        dependencies.get_runtime_explanation_provider.cache_clear()


def test_list_query_path_never_loads_large_evidence_or_output_json() -> None:
    from app.repositories.explanation_query_repository import ExplanationQueryRepository

    source = inspect.getsource(inspect.getmodule(ExplanationQueryRepository))
    assert "undefer" not in source
    list_source = inspect.getsource(ExplanationQueryRepository.list_for_match_run)
    assert "evidence_bundle_json" not in list_source
    assert "provider_evidence_json" not in list_source
    assert "validated_output_json" not in list_source
    assert "selectinload" not in list_source


def _persisted_candidate_output() -> dict[str, object]:
    return {
        "output_schema_version": "explanation_output_v1",
        "candidate_id": "candidate-api-1",
        "result_rank": 1,
        "summary": {
            "text": "Recorded evidence supports this persisted match result.",
            "evidence_refs": ["job_requirement:req_python"],
        },
        "match_reasons": [
            {
                "category": "skill_alignment",
                "text": "Recorded structured skill evidence aligns with a requirement.",
                "evidence_refs": ["job_requirement:req_python"],
            },
            {
                "category": "ranking_context",
                "text": "This is the persisted result rank.",
                "evidence_refs": ["ranking:1:result_rank"],
            },
        ],
        "risk_points": [],
        "missing_skills": [],
        "interview_questions": [],
        "why_not_top1": None,
        "profile_rewrite_suggestion": None,
    }


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("candidate_id", "candidate-api-other"),
        ("result_rank", 2),
        ("output_schema_version", "explanation_output_v2"),
        ("candidate_output_fingerprint", "0" * 64),
    ],
)
def test_detail_rejects_persisted_child_column_json_divergence(
    field: str,
    invalid_value: object,
) -> None:
    from app.schemas.explanation_generation import explanation_detail_from_model
    from app.schemas.explanations import CandidateExplanationOutput
    from app.services.explanation.contracts import candidate_output_fingerprint
    from app.services.explanation.generation.errors import (
        ExplanationPersistenceIntegrityError,
    )

    output = CandidateExplanationOutput.model_validate(_persisted_candidate_output())
    child = SimpleNamespace(
        candidate_id=output.candidate_id,
        result_rank=output.result_rank,
        output_schema_version=output.output_schema_version,
        validated_output_json=output.model_dump(mode="json", exclude_none=False),
        candidate_output_fingerprint=candidate_output_fingerprint(output),
    )
    setattr(child, field, invalid_value)
    run = SimpleNamespace(
        explanation_run_id=EXPLANATION_RUN_ID,
        match_run_id=MATCH_RUN_ID,
        status="COMPLETED",
        requested_top_k=1,
        effective_top_k=1,
        explanation_count=1,
        provider_kind="llm",
        provider_name="mock",
        configured_model="deterministic-mock-v1",
        observed_model="deterministic-mock-v1",
        prompt_version="explanation_prompt_v1",
        attempt_count=1,
        repaired=False,
        error_code=None,
        error_detail_safe=None,
        created_at=None,
        completed_at=None,
        explanations=[child],
    )

    with pytest.raises(ExplanationPersistenceIntegrityError):
        explanation_detail_from_model(run)
