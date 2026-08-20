from __future__ import annotations

import asyncio
import inspect

import pytest

from app.models.explanation_run import ExplanationRunModel
from app.repositories.explanation_run_repository import ExplanationRunRepository
from app.exceptions import ExplanationRunConflictError


class _NeverFactory:
    def __call__(self):
        raise AssertionError("invalid create input must fail before opening a session")


def _running_model(**overrides) -> ExplanationRunModel:
    values = {
        "explanation_run_id": "00000000-0000-0000-0000-000000000911",
        "match_run_id": "00000000-0000-0000-0000-000000000901",
        "request_id": "request-phase9-repository",
        "status": "RUNNING",
        "requested_top_k": 5,
        "effective_top_k": None,
        "explanation_count": 0,
        "attempt_count": 0,
        "repaired": False,
    }
    values.update(overrides)
    return ExplanationRunModel(**values)


def test_repository_exposes_only_phase91_lifecycle_operations() -> None:
    methods = {
        name
        for name, value in inspect.getmembers(
            ExplanationRunRepository, predicate=inspect.iscoroutinefunction
        )
        if not name.startswith("_")
    }
    assert {
        "create_running",
        "store_evidence",
        "finalize_completed",
        "finalize_failed",
        "get_by_explanation_run_id",
    } <= methods
    assert "regenerate" not in methods
    assert "call_provider" not in methods


def test_create_running_rejects_terminal_or_result_bearing_input_before_db() -> None:
    repository = ExplanationRunRepository(_NeverFactory())
    with pytest.raises(ExplanationRunConflictError):
        asyncio.run(repository.create_running(_running_model(status="FAILED")))
    with pytest.raises(ExplanationRunConflictError):
        asyncio.run(repository.create_running(_running_model(explanation_count=1)))


def test_repository_has_no_current_profile_or_ranking_dependencies() -> None:
    source = inspect.getsource(inspect.getmodule(ExplanationRunRepository))
    forbidden = (
        "CandidateRepository",
        "JobRepository",
        "RetrievalService",
        "FeatureEngineeringService",
        "RankingService",
        "CrossEncoderRerankingService",
        "Qdrant",
    )
    assert not any(value in source for value in forbidden)
