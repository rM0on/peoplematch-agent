from __future__ import annotations

from pathlib import Path
import asyncio
from types import SimpleNamespace

from sqlalchemy import UniqueConstraint

from app.models.match_run import MatchResultModel, MatchRunModel, RunStepModel
from app.repositories.match_run_repository import MatchRunRepository


def _unique_columns(table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_match_run_tables_have_explicit_audit_fields() -> None:
    assert MatchRunModel.__tablename__ == "match_runs"
    assert set(MatchRunModel.__table__.columns.keys()) == {
        "run_id",
        "requested_job_id",
        "job_id",
        "request_id",
        "ranking_variant",
        "status",
        "created_at",
        "started_at",
        "completed_at",
        "request_parameters",
        "workflow_version",
        "workflow_fingerprint",
        "ranking_input_contract_version",
        "ranking_input_fingerprint",
        "ranking_input_snapshot",
        "retrieval_document_version",
        "retrieval_configuration_fingerprint",
        "retrieval_provenance",
        "feature_version",
        "feature_fingerprint",
        "ranker_version",
        "ranker_model_sha256",
        "ce_provenance",
        "result_count",
        "result_fingerprint",
        "error_code",
        "error_detail_safe",
    }
    job_fk = next(iter(MatchRunModel.__table__.c.job_id.foreign_keys))
    assert job_fk.target_fullname == "job_profiles.job_id"
    assert job_fk.ondelete == "RESTRICT"


def test_match_result_has_frozen_features_and_per_run_constraints() -> None:
    expected_features = {
        "semantic_score",
        "sparse_score",
        "skill_fit_score",
        "project_evidence_score",
        "role_direction_score",
        "ai_tool_score",
        "location_score",
        "seniority_score",
        "missing_penalty",
        "overclaim_penalty",
    }
    assert expected_features <= set(MatchResultModel.__table__.columns.keys())
    assert {("run_id", "candidate_id"), ("run_id", "result_rank")} <= _unique_columns(
        MatchResultModel.__table__
    )
    candidate_fk = next(iter(MatchResultModel.__table__.c.candidate_id.foreign_keys))
    assert candidate_fk.ondelete == "RESTRICT"
    assert "final_match_score" not in MatchResultModel.__table__.columns
    assert "probability" not in MatchResultModel.__table__.columns


def test_run_steps_are_sequence_constrained_and_have_safe_refs() -> None:
    assert ("run_id", "sequence") in _unique_columns(RunStepModel.__table__)
    assert {"input_refs", "output_refs", "duration_ms", "error_detail_safe"} <= set(
        RunStepModel.__table__.columns.keys()
    )
    assert "traceback" not in RunStepModel.__table__.columns


def test_phase8_has_exactly_one_migration_with_expected_parent() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations = list((root / "alembic" / "versions").glob("20260818_0002*.py"))
    assert len(migrations) == 1
    text = migrations[0].read_text(encoding="utf-8")
    assert 'revision: str = "20260818_0002"' in text
    assert 'down_revision: str = "20260813_0001"' in text
    assert '"match_runs"' in text
    assert '"match_results"' in text
    assert '"run_steps"' in text
    assert "explanation" not in text.lower()


def test_list_query_does_not_eager_load_historical_children() -> None:
    statements = []

    class ScalarResult:
        def __init__(self, value):
            self.value = value

        def unique(self):
            return self

        def all(self):
            return []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def scalar(self, statement):
            statements.append(statement)
            return 0

        async def scalars(self, statement):
            statements.append(statement)
            return ScalarResult([])

    class Factory:
        def __call__(self):
            return Session()

    asyncio.run(
        MatchRunRepository(Factory()).list_runs(
            limit=20, offset=0, job_id=None, status=None, ranking_variant=None
        )
    )
    assert len(statements) == 2
    assert statements[1]._with_options == ()
