from __future__ import annotations

import asyncio
import os

import httpx
import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql+asyncpg://"),
    reason="requires TEST_DATABASE_URL with postgresql+asyncpg://",
)


def setup_module() -> None:
    if os.environ.get("TEST_DATABASE_URL"):
        from tests.test_feedback_bad_case_repository_postgres import _alembic_head

        _alembic_head()


def test_public_historical_locators_round_trip_through_feedback_service() -> None:
    async def scenario() -> None:
        from app.core.database import get_engine
        from app.main import create_app
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
                await _completed_history(fixture_factory, "861", candidate_count=2)
            )
            other_run_id, *_ = await _completed_history(
                fixture_factory, "862", candidate_count=2
            )
            app = create_app()
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://phase10-locators.test"
            ) as client:
                run_response = await client.get(f"/api/v1/match-runs/{run_id}")
                assert run_response.status_code == 200, run_response.text
                public_result = run_response.json()["data"]["results"][0]
                assert public_result["match_result_id"] == results[0].id
                assert public_result["candidate_id"] == results[0].candidate_id
                assert public_result["result_rank"] == results[0].result_rank

                ranking_feedback = await client.post(
                    "/api/v1/feedback",
                    json={
                        "feedback_type": "ranking",
                        "match_run_id": run_id,
                        "target_type": "candidate_result",
                        "subject_match_result_id": public_result["match_result_id"],
                        "value": "correct",
                    },
                )
                assert ranking_feedback.status_code == 201, ranking_feedback.text
                persisted_ranking = await client.get(
                    f"/api/v1/feedback/{ranking_feedback.json()['data']['feedback_id']}"
                )
                assert persisted_ranking.status_code == 200
                assert persisted_ranking.json()["data"]["candidate_id"] == results[0].candidate_id

                explanation_response = await client.get(
                    f"/api/v1/explanation-runs/{explanation.explanation_run_id}"
                )
                assert explanation_response.status_code == 200, explanation_response.text
                public_explanation = explanation_response.json()["data"]["explanations"][0]
                assert public_explanation["match_explanation_id"] == explanation.explanations[0].id
                assert public_explanation["candidate_id"] == results[0].candidate_id
                assert public_explanation["result_rank"] == results[0].result_rank

                explanation_feedback = await client.post(
                    "/api/v1/feedback",
                    json={
                        "feedback_type": "explanation",
                        "match_run_id": run_id,
                        "explanation_run_id": explanation.explanation_run_id,
                        "match_explanation_id": public_explanation["match_explanation_id"],
                        "target_type": "summary",
                        "value": "grounded",
                    },
                )
                assert explanation_feedback.status_code == 201, explanation_feedback.text
                persisted_explanation = await client.get(
                    f"/api/v1/feedback/{explanation_feedback.json()['data']['feedback_id']}"
                )
                assert persisted_explanation.status_code == 200
                assert persisted_explanation.json()["data"]["candidate_id"] == results[0].candidate_id

                wrong_run_result = await client.post(
                    "/api/v1/feedback",
                    json={
                        "feedback_type": "ranking",
                        "match_run_id": other_run_id,
                        "target_type": "candidate_result",
                        "subject_match_result_id": public_result["match_result_id"],
                        "value": "correct",
                    },
                )
                assert wrong_run_result.status_code in {404, 422}
                assert wrong_run_result.json()["success"] is False

                wrong_run_explanation = await client.post(
                    "/api/v1/feedback",
                    json={
                        "feedback_type": "explanation",
                        "match_run_id": other_run_id,
                        "explanation_run_id": explanation.explanation_run_id,
                        "match_explanation_id": public_explanation["match_explanation_id"],
                        "target_type": "summary",
                        "value": "grounded",
                    },
                )
                assert wrong_run_explanation.status_code in {404, 422}
                assert wrong_run_explanation.json()["success"] is False
            app_engine = get_engine()
        finally:
            if app_engine is not None:
                await app_engine.dispose()
            await fixture_engine.dispose()

    asyncio.run(scenario())
