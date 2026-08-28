from __future__ import annotations

from datetime import datetime, timezone

from app.api.dependencies import get_bad_case_review_service, get_feedback_service
from app.services.feedback.errors import (
    HistoricalTargetError,
    Phase10NotFoundError,
    ReviewConcurrencyError,
)


NOW = datetime(2026, 8, 27, tzinfo=timezone.utc).isoformat()


def _feedback_response() -> dict:
    return {
        "feedback_type": "ranking",
        "feedback_id": "10000000-0000-0000-0000-000000000001",
        "contract_version": "feedback_record_v1",
        "origin": "human",
        "match_run_id": "run-phase10-api",
        "target_type": "top1",
        "subject_match_result_id": 1,
        "comparison_match_result_id": None,
        "expected_candidate_reference": None,
        "value": "wrong",
        "reason_code": "wrong_top1",
        "comment": None,
        "supersedes_feedback_id": None,
        "job_id": "job-historical",
        "candidate_id": "candidate-historical",
        "result_rank": 1,
        "comparison_candidate_id": None,
        "comparison_result_rank": None,
        "created_at": NOW,
    }


def _case_summary() -> dict:
    return {
        "bad_case_id": "20000000-0000-0000-0000-000000000001",
        "case_contract_version": "bad_case_v1",
        "taxonomy_version": "bad_case_taxonomy_v1",
        "primary_match_run_id": "run-phase10-api",
        "primary_match_result_id": 1,
        "historical_job_id": "job-historical",
        "historical_candidate_id": "candidate-historical",
        "result_rank": 1,
        "primary_explanation_run_id": None,
        "primary_match_explanation_id": None,
        "symptom_code": "wrong_top1",
        "symptom_family": "RANKING",
        "severity": "HIGH",
        "status": "CREATED",
        "revision": 0,
        "duplicate_of_bad_case_id": None,
        "related_case_id": None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def _case_detail() -> dict:
    return {
        **_case_summary(),
        "sources": [
            {
                "source_type": "feedback",
                "feedback_id": "10000000-0000-0000-0000-000000000001",
                "system_signal_id": None,
                "created_at": NOW,
            }
        ],
        "evidence_links": [],
        "analyses": [],
        "resolution_actions": [],
        "transitions": [],
        "child_limit": 25,
        "truncated_collections": ["transitions"],
    }


class _FeedbackApiService:
    def __init__(self, *, error=None):
        self.error = error
        self.created = []

    async def create(self, payload):
        if self.error is not None:
            raise self.error
        self.created.append(payload)
        return _feedback_response()

    async def get(self, feedback_id: str):
        assert feedback_id == _feedback_response()["feedback_id"]
        return _feedback_response()


class _BadCaseApiService:
    def __init__(self, *, review_error=None, get_error=None):
        self.review_error = review_error
        self.get_error = get_error
        self.calls = []

    async def create_detail(self, payload):
        self.calls.append(("create", payload))
        return _case_detail()

    async def get_detail(self, bad_case_id: str, *, child_limit: int):
        if self.get_error is not None:
            raise self.get_error
        self.calls.append(("get", bad_case_id, child_limit))
        return _case_detail()

    async def list_summaries(self, *, limit: int, offset: int):
        self.calls.append(("list", limit, offset))
        return [_case_summary()], 1

    async def review_detail(self, bad_case_id: str, payload):
        if self.review_error is not None:
            raise self.review_error
        self.calls.append(("review", bad_case_id, payload))
        result = _case_detail()
        result["status"] = "REVIEWED"
        result["revision"] = 1
        return result

    async def link_source_detail(self, bad_case_id: str, payload):
        self.calls.append(("link_source", bad_case_id, payload))
        result = _case_detail()
        result["sources"].append(
            {
                "source_type": "feedback",
                "feedback_id": "10000000-0000-0000-0000-000000000002",
                "system_signal_id": None,
                "created_at": NOW,
            }
        )
        return result


def test_feedback_api_is_discriminated_server_owned_and_request_scoped(app, client) -> None:
    service = _FeedbackApiService()
    app.dependency_overrides[get_feedback_service] = lambda: service
    try:
        response = client.post(
            "/api/v1/feedback",
            headers={"X-Request-ID": "phase10-feedback-create"},
            json={
                "feedback_type": "ranking",
                "match_run_id": "run-phase10-api",
                "target_type": "top1",
                "subject_match_result_id": 1,
                "value": "wrong",
                "reason_code": "wrong_top1",
            },
        )
        assert response.status_code == 201
        assert response.headers["X-Request-ID"] == "phase10-feedback-create"
        body = response.json()
        assert body["request_id"] == "phase10-feedback-create"
        assert body["data"]["job_id"] == "job-historical"
        assert body["data"]["candidate_id"] == "candidate-historical"
        assert service.created[0].feedback_type == "ranking"

        invalid = client.post(
            "/api/v1/feedback",
            json={
                "feedback_type": "ranking",
                "match_run_id": "run-phase10-api",
                "target_type": "top1",
                "subject_match_result_id": 1,
                "value": "wrong",
                "reason_code": "wrong_top1",
                "candidate_id": "caller-spoof",
            },
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "validation_error"
        assert len(service.created) == 1
    finally:
        app.dependency_overrides.clear()


def test_feedback_api_maps_historical_attack_without_private_error_data(app, client) -> None:
    service = _FeedbackApiService(
        error=HistoricalTargetError(
            "Historical review target is invalid"
        )
    )
    app.dependency_overrides[get_feedback_service] = lambda: service
    try:
        response = client.post(
            "/api/v1/feedback",
            headers={"X-Request-ID": "phase10-feedback-error"},
            json={
                "feedback_type": "ranking",
                "match_run_id": "run-phase10-api",
                "target_type": "expected_candidate",
                "expected_candidate_reference": "expected_candidate:opaque-review-ref",
                "value": "wrong",
                "reason_code": "false_negative",
            },
        )
        assert response.status_code == 422
        assert response.headers["X-Request-ID"] == "phase10-feedback-error"
        assert response.json()["error"] == {
            "code": "historical_target_invalid",
            "message": "Historical review target is invalid",
            "details": None,
        }
        serialized = response.text.lower()
        assert "snapshot" not in serialized
        assert "select " not in serialized
        assert "candidate name" not in serialized
    finally:
        app.dependency_overrides.clear()


def test_bad_case_api_exposes_bounded_projection_and_typed_workflow(app, client) -> None:
    service = _BadCaseApiService()
    app.dependency_overrides[get_bad_case_review_service] = lambda: service
    try:
        created = client.post(
            "/api/v1/bad-cases",
            json={
                "source_type": "feedback",
                "feedback_id": "10000000-0000-0000-0000-000000000001",
                "symptom_code": "wrong_top1",
                "severity": "HIGH",
            },
        )
        assert created.status_code == 201

        listed = client.get("/api/v1/bad-cases?limit=20&offset=0")
        assert listed.status_code == 200
        assert listed.json()["data"]["total"] == 1
        assert "sources" not in listed.json()["data"]["items"][0]

        detail = client.get(
            "/api/v1/bad-cases/20000000-0000-0000-0000-000000000001?child_limit=25"
        )
        assert detail.status_code == 200
        assert detail.json()["data"]["child_limit"] == 25
        assert detail.json()["data"]["truncated_collections"] == ["transitions"]

        reviewed = client.post(
            "/api/v1/bad-cases/20000000-0000-0000-0000-000000000001/review",
            json={
                "command": "transition",
                "expected_status": "CREATED",
                "expected_revision": 0,
                "status": "REVIEWED",
                "transition_reason": "review_completed",
            },
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["data"]["status"] == "REVIEWED"
        assert reviewed.json()["data"]["revision"] == 1

        linked = client.post(
            "/api/v1/bad-cases/20000000-0000-0000-0000-000000000001/sources",
            json={
                "source_type": "feedback",
                "feedback_id": "10000000-0000-0000-0000-000000000002"
            },
        )
        assert linked.status_code == 200
        assert len(linked.json()["data"]["sources"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_bad_case_api_maps_stale_revision_to_conflict(app, client) -> None:
    service = _BadCaseApiService(
        review_error=ReviewConcurrencyError(
            "Review uses a stale BadCase status or revision"
        )
    )
    app.dependency_overrides[get_bad_case_review_service] = lambda: service
    try:
        response = client.post(
            "/api/v1/bad-cases/20000000-0000-0000-0000-000000000001/review",
            headers={"X-Request-ID": "phase10-stale-review"},
            json={
                "command": "transition",
                "expected_status": "CREATED",
                "expected_revision": 0,
                "status": "REVIEWED",
                "transition_reason": "review_completed",
            },
        )
        assert response.status_code == 409
        assert response.headers["X-Request-ID"] == "phase10-stale-review"
        assert response.json()["error"]["code"] == "review_concurrency_conflict"
    finally:
        app.dependency_overrides.clear()


def test_bad_case_api_not_found_is_safe_and_does_not_offer_generic_patch(app, client) -> None:
    service = _BadCaseApiService(
        get_error=Phase10NotFoundError("BadCase was not found")
    )
    app.dependency_overrides[get_bad_case_review_service] = lambda: service
    try:
        response = client.get("/api/v1/bad-cases/not-present")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "phase10_not_found"
        assert client.patch(
            "/api/v1/bad-cases/not-present", json={"status": "VERIFIED"}
        ).status_code == 405
    finally:
        app.dependency_overrides.clear()


def test_phase10_openapi_closes_feedback_union_and_documents_conflict(app) -> None:
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/feedback"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["discriminator"]["propertyName"] == "feedback_type"
    assert "422" in operation["responses"]
    for name in (
        "RankingFeedbackCreate",
        "ExplanationFeedbackCreate",
        "ProfileDataFeedbackCreate",
    ):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False

    create_case = schema["paths"]["/api/v1/bad-cases"]["post"]
    create_case_request = create_case["requestBody"]["content"]["application/json"][
        "schema"
    ]
    assert create_case_request["discriminator"]["propertyName"] == "source_type"
    for name in ("FeedbackBadCaseCreateCommand", "SystemSignalBadCaseCreateCommand"):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False

    review = schema["paths"]["/api/v1/bad-cases/{bad_case_id}/review"]["post"]
    review_request = review["requestBody"]["content"]["application/json"]["schema"]
    assert review_request["discriminator"]["propertyName"] == "command"
    for name in (
        "BadCaseTransitionCommand",
        "BadCaseAnalysisCommand",
        "BadCaseResolutionCommand",
    ):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False
    assert "409" in review["responses"]
    source = schema["paths"]["/api/v1/bad-cases/{bad_case_id}/sources"]["post"]
    source_request = source["requestBody"]["content"]["application/json"]["schema"]
    assert source_request["discriminator"]["propertyName"] == "source_type"
    for name in ("FeedbackBadCaseSourceCommand", "SystemSignalBadCaseSourceCommand"):
        assert schema["components"]["schemas"][name]["additionalProperties"] is False
    assert "patch" not in schema["paths"]["/api/v1/bad-cases/{bad_case_id}"]
    assert not any("export" in path for path in schema["paths"])


def test_openapi_exposes_required_contextual_feedback_target_locators(app) -> None:
    schema = app.openapi()
    match_result = schema["components"]["schemas"]["MatchResultResponse"]
    explanation = schema["components"]["schemas"]["MatchExplanationResponse"]

    assert "match_result_id" in match_result["properties"]
    assert "match_result_id" in match_result["required"]
    assert match_result["properties"]["match_result_id"]["type"] == "integer"
    assert "match_explanation_id" in explanation["properties"]
    assert "match_explanation_id" in explanation["required"]
    assert explanation["properties"]["match_explanation_id"]["type"] == "integer"


def test_bad_case_api_rejects_untyped_review_and_ambiguous_source_commands(app, client) -> None:
    service = _BadCaseApiService()
    app.dependency_overrides[get_bad_case_review_service] = lambda: service
    try:
        untyped_review = client.post(
            "/api/v1/bad-cases/20000000-0000-0000-0000-000000000001/review",
            json={
                "expected_status": "CREATED",
                "expected_revision": 0,
                "status": "REVIEWED",
                "transition_reason": "review_completed",
            },
        )
        assert untyped_review.status_code == 422

        ambiguous_source = client.post(
            "/api/v1/bad-cases/20000000-0000-0000-0000-000000000001/sources",
            json={
                "source_type": "feedback",
                "feedback_id": "10000000-0000-0000-0000-000000000002",
                "system_signal_id": "10000000-0000-0000-0000-000000000003",
            },
        )
        assert ambiguous_source.status_code == 422
        assert service.calls == []
    finally:
        app.dependency_overrides.clear()
