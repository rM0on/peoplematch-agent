from __future__ import annotations

import asyncio

import httpx
import pytest


pytestmark = pytest.mark.skipif(
    not __import__("os").environ.get("TEST_DATABASE_URL", "").startswith(
        "postgresql+asyncpg://"
    ),
    reason="requires TEST_DATABASE_URL with postgresql+asyncpg://",
)


def test_phase10_api_postgres_end_to_end_review_and_safe_export() -> None:
    async def scenario() -> None:
        from app.core.database import (
            get_engine,
            get_session_factory,
        )
        from app.main import create_app
        from app.services.bad_cases.service import BadCaseReviewService
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        fixture_engine, fixture_factory = await _engine_and_factory()
        app_engine = None
        try:
            await _truncate(fixture_engine)
            run_id, _job_id, _candidates, results, explanation = (
                await _completed_history(fixture_factory, "801", candidate_count=2)
            )
            app = create_app()
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://phase10.test"
            ) as client:
                invalid = await client.post(
                    "/api/v1/feedback",
                    json={
                        "feedback_type": "explanation",
                        "match_run_id": run_id,
                        "explanation_run_id": explanation.explanation_run_id,
                        "match_explanation_id": explanation.explanations[1].id,
                        "target_type": "match_reason",
                        "value": "unsupported",
                        "evidence_reference": (
                            "candidate:2:skill:0123456789abcdef0123456789abcde2"
                        ),
                        "candidate_id": "caller-spoof",
                    },
                )
                assert invalid.status_code == 422

                created_feedback = await client.post(
                    "/api/v1/feedback",
                    headers={"X-Request-ID": "phase10-pg-feedback"},
                    json={
                        "feedback_type": "explanation",
                        "match_run_id": run_id,
                        "explanation_run_id": explanation.explanation_run_id,
                        "match_explanation_id": explanation.explanations[1].id,
                        "target_type": "match_reason",
                        "value": "unsupported",
                        "evidence_reference": (
                            "candidate:2:skill:0123456789abcdef0123456789abcde2"
                        ),
                    },
                )
                assert created_feedback.status_code == 201, created_feedback.text
                feedback = created_feedback.json()["data"]
                assert feedback["candidate_id"] == results[1].candidate_id
                assert feedback["result_rank"] == 2
                feedback_id = feedback["feedback_id"]

                persisted_feedback = await client.get(f"/api/v1/feedback/{feedback_id}")
                assert persisted_feedback.status_code == 200
                assert persisted_feedback.json()["data"] == feedback

                created_case = await client.post(
                    "/api/v1/bad-cases",
                    json={
                        "source_type": "feedback",
                        "feedback_id": feedback_id,
                        "symptom_code": "unsupported_explanation",
                        "severity": "HIGH",
                    },
                )
                assert created_case.status_code == 201, created_case.text
                detail = created_case.json()["data"]
                case_id = detail["bad_case_id"]
                evidence_link_id = detail["evidence_links"][0]["evidence_link_id"]
                assert detail["child_limit"] == 100
                assert detail["truncated_collections"] == []

                stale = await client.post(
                    f"/api/v1/bad-cases/{case_id}/review",
                    json={
                        "command": "transition",
                        "expected_status": "CREATED",
                        "expected_revision": 99,
                        "status": "REVIEWED",
                        "transition_reason": "review_completed",
                    },
                )
                assert stale.status_code == 409
                assert stale.json()["error"]["code"] == "review_concurrency_conflict"

                payloads = (
                    {
                        "command": "transition",
                        "expected_status": "CREATED",
                        "expected_revision": 0,
                        "status": "REVIEWED",
                        "transition_reason": "review_completed",
                    },
                    {
                        "command": "analysis",
                        "expected_status": "REVIEWED",
                        "expected_revision": 1,
                        "status": "ROOT_CAUSE_IDENTIFIED",
                        "transition_reason": "root_cause_supported",
                        "analysis": {
                            "assessment": "confirmed",
                            "root_cause_type": "explanation",
                            "root_cause_code": "explanation_unsupported_claim",
                            "description": "Bounded case-specific assessment",
                            "supporting_evidence_link_id": evidence_link_id,
                        },
                    },
                    {
                        "command": "resolution",
                        "expected_status": "ROOT_CAUSE_IDENTIFIED",
                        "expected_revision": 2,
                        "status": "ACTION_PLANNED",
                        "transition_reason": "action_created",
                        "resolution": {
                            "action_type": "grounding_integrity_action",
                            "description": "Plan a bounded grounding repair",
                        },
                    },
                )
                for payload in payloads:
                    response = await client.post(
                        f"/api/v1/bad-cases/{case_id}/review", json=payload
                    )
                    assert response.status_code == 200, response.text
                    detail = response.json()["data"]

                action_id = detail["resolution_actions"][-1]["action_id"]
                resolved = await client.post(
                    f"/api/v1/bad-cases/{case_id}/review",
                    json={
                        "command": "resolution",
                        "expected_status": "ACTION_PLANNED",
                        "expected_revision": 3,
                        "status": "RESOLVED",
                        "transition_reason": "actions_completed",
                        "resolution": {
                            "action_type": "grounding_integrity_action",
                            "description": "Bounded case action completed",
                            "status": "completed",
                            "supersedes_action_id": action_id,
                            "safe_change_reference": "commit:phase10-api-801",
                        },
                    },
                )
                assert resolved.status_code == 200, resolved.text

                verify_without_artifact = await client.post(
                    f"/api/v1/bad-cases/{case_id}/review",
                    json={
                        "command": "transition",
                        "expected_status": "RESOLVED",
                        "expected_revision": 4,
                        "status": "VERIFIED",
                        "transition_reason": "verification_linked",
                    },
                )
                assert verify_without_artifact.status_code == 422

                verified = await client.post(
                    f"/api/v1/bad-cases/{case_id}/review",
                    json={
                        "command": "transition",
                        "expected_status": "RESOLVED",
                        "expected_revision": 4,
                        "status": "VERIFIED",
                        "transition_reason": "verification_linked",
                        "verification_reference": "commit:phase10-verify-801",
                    },
                )
                assert verified.status_code == 200, verified.text
                assert verified.json()["data"]["revision"] == 5

                listed = await client.get("/api/v1/bad-cases?limit=10&offset=0")
                assert listed.status_code == 200
                assert listed.json()["data"]["total"] == 1
                assert "evidence_links" not in listed.json()["data"]["items"][0]

                final_detail = await client.get(
                    f"/api/v1/bad-cases/{case_id}?child_limit=100"
                )
                assert final_detail.status_code == 200
                assert final_detail.json()["data"]["status"] == "VERIFIED"
                assert len(final_detail.json()["data"]["transitions"]) == 5

                linked_feedback = await client.post(
                    "/api/v1/feedback",
                    json={
                        "feedback_type": "explanation",
                        "match_run_id": run_id,
                        "explanation_run_id": explanation.explanation_run_id,
                        "match_explanation_id": explanation.explanations[1].id,
                        "target_type": "match_reason",
                        "value": "unsupported",
                        "evidence_reference": (
                            "candidate:2:skill:0123456789abcdef0123456789abcde2"
                        ),
                    },
                )
                assert linked_feedback.status_code == 201
                linked = await client.post(
                    f"/api/v1/bad-cases/{case_id}/sources",
                    json={
                        "source_type": "feedback",
                        "feedback_id": linked_feedback.json()["data"]["feedback_id"]
                    },
                )
                assert linked.status_code == 200, linked.text
                assert len(linked.json()["data"]["sources"]) == 2
                assert len(linked.json()["data"]["evidence_links"]) == 1

                second_feedback = await client.post(
                    "/api/v1/feedback",
                    json={
                        "feedback_type": "explanation",
                        "match_run_id": run_id,
                        "explanation_run_id": explanation.explanation_run_id,
                        "match_explanation_id": explanation.explanations[1].id,
                        "target_type": "match_reason",
                        "value": "unsupported",
                        "evidence_reference": (
                            "candidate:2:skill:0123456789abcdef0123456789abcde2"
                        ),
                    },
                )
                assert second_feedback.status_code == 201
                duplicate_case = await client.post(
                    "/api/v1/bad-cases",
                    json={
                        "source_type": "feedback",
                        "feedback_id": second_feedback.json()["data"]["feedback_id"],
                        "symptom_code": "unsupported_explanation",
                        "severity": "MEDIUM",
                    },
                )
                duplicate_id = duplicate_case.json()["data"]["bad_case_id"]
                duplicate = await client.post(
                    f"/api/v1/bad-cases/{duplicate_id}/review",
                    json={
                        "command": "transition",
                        "expected_status": "CREATED",
                        "expected_revision": 0,
                        "status": "DUPLICATE",
                        "transition_reason": "duplicate_linked",
                        "duplicate_of_bad_case_id": case_id,
                    },
                )
                assert duplicate.status_code == 200, duplicate.text
                reopened = await client.post(
                    f"/api/v1/bad-cases/{duplicate_id}/review",
                    json={
                        "command": "transition",
                        "expected_status": "DUPLICATE",
                        "expected_revision": 1,
                        "status": "REVIEWED",
                        "transition_reason": "case_reopened",
                    },
                )
                assert reopened.status_code == 200, reopened.text
                assert reopened.json()["data"]["status"] == "REVIEWED"
                assert [
                    item["to_status"]
                    for item in reopened.json()["data"]["transitions"]
                ] == ["DUPLICATE", "REVIEWED"]

            service = BadCaseReviewService(get_session_factory())
            export = await service.export_review(case_id)
            exported = export.model_dump(mode="json")
            assert exported["contract_version"] == "phase10_review_export_v1"
            assert exported["verification_state"] == "case_specific_verified"
            assert exported["evidence_kinds"] == ["skill"]
            serialized = export.model_dump_json().lower()
            for forbidden in (
                "bounded case-specific assessment",
                "bounded grounding repair",
                "candidate name",
                "resume",
                "ndcg",
                "mrr",
                "split",
            ):
                assert forbidden not in serialized
            app_engine = get_engine()
        finally:
            if app_engine is not None:
                await app_engine.dispose()
            await fixture_engine.dispose()

    asyncio.run(scenario())
