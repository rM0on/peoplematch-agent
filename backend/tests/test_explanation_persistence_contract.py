from __future__ import annotations

from pathlib import Path
import re

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.explanation_run import ExplanationRunModel, MatchExplanationModel


def _constraint_names(table, constraint_type) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type) and constraint.name
    }


def _unique_columns(table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_explanation_run_model_has_exact_phase91_fields() -> None:
    assert ExplanationRunModel.__tablename__ == "explanation_runs"
    assert set(ExplanationRunModel.__table__.columns.keys()) == {
        "explanation_run_id",
        "match_run_id",
        "request_id",
        "status",
        "requested_top_k",
        "effective_top_k",
        "explanation_count",
        "evidence_bundle_version",
        "evidence_bundle_fingerprint",
        "evidence_bundle_json",
        "provider_evidence_version",
        "provider_evidence_fingerprint",
        "provider_evidence_json",
        "output_schema_version",
        "provider_kind",
        "provider_name",
        "configured_model",
        "observed_model",
        "provider_configuration_fingerprint",
        "prompt_version",
        "prompt_fingerprint",
        "attempt_count",
        "repaired",
        "result_fingerprint",
        "error_code",
        "error_detail_safe",
        "created_at",
        "completed_at",
    }
    fk = next(iter(ExplanationRunModel.__table__.c.match_run_id.foreign_keys))
    assert fk.target_fullname == "match_runs.run_id"
    assert fk.ondelete == "RESTRICT"
    assert fk.constraint.name == "fk_explanation_runs_match_run_id_match_runs"


def test_explanation_run_constraints_have_stable_names() -> None:
    checks = _constraint_names(ExplanationRunModel.__table__, CheckConstraint)
    assert {
        "ck_explanation_runs_status",
        "ck_explanation_runs_requested_top_k",
        "ck_explanation_runs_effective_top_k",
        "ck_explanation_runs_attempt_count",
        "ck_explanation_runs_explanation_count",
        "ck_explanation_runs_repaired_attempts",
        "ck_explanation_runs_evidence_bundle_group",
        "ck_explanation_runs_provider_evidence_group",
        "ck_explanation_runs_prompt_group",
        "ck_explanation_runs_running_state",
        "ck_explanation_runs_failed_state",
        "ck_explanation_runs_completed_state",
    } <= checks


def test_match_explanation_has_historical_ownership_without_candidate_fk() -> None:
    assert MatchExplanationModel.__tablename__ == "match_explanations"
    assert set(MatchExplanationModel.__table__.columns.keys()) == {
        "id",
        "explanation_run_id",
        "match_result_id",
        "candidate_id",
        "result_rank",
        "output_schema_version",
        "validated_output_json",
        "candidate_output_fingerprint",
        "created_at",
    }
    run_fk = next(iter(MatchExplanationModel.__table__.c.explanation_run_id.foreign_keys))
    result_fk = next(iter(MatchExplanationModel.__table__.c.match_result_id.foreign_keys))
    assert run_fk.target_fullname == "explanation_runs.explanation_run_id"
    assert run_fk.ondelete == "RESTRICT"
    assert run_fk.constraint.name == (
        "fk_match_explanations_explanation_run_id_explanation_runs"
    )
    assert result_fk.target_fullname == "match_results.id"
    assert result_fk.ondelete == "RESTRICT"
    assert result_fk.constraint.name == "fk_match_explanations_match_result_id_match_results"
    assert not MatchExplanationModel.__table__.c.candidate_id.foreign_keys
    assert {
        ("explanation_run_id", "candidate_id"),
        ("explanation_run_id", "result_rank"),
        ("explanation_run_id", "match_result_id"),
    } <= _unique_columns(MatchExplanationModel.__table__)


def test_large_json_and_child_relationships_require_explicit_loading() -> None:
    mapper = ExplanationRunModel.__mapper__
    for name in ("evidence_bundle_json", "provider_evidence_json"):
        property_ = mapper.attrs[name]
        assert property_.deferred is True
        assert property_.raiseload is True
    assert mapper.relationships["explanations"].lazy == "raise"
    assert MatchExplanationModel.__mapper__.relationships["run"].lazy == "raise"
    assert MatchExplanationModel.__mapper__.relationships["match_result"].lazy == "raise"


def test_phase9_has_one_migration_with_phase8_parent_and_no_phase8_alter() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations = list((root / "alembic" / "versions").glob("20260819_0003*.py"))
    assert len(migrations) == 1
    text = migrations[0].read_text(encoding="utf-8")
    assert 'revision: str = "20260819_0003"' in text
    assert 'down_revision: str = "20260818_0002"' in text
    assert '"explanation_runs"' in text
    assert '"match_explanations"' in text
    assert "alter_column" not in text
    assert not re.search(r"op\.alter_table\(\s*[\"'](?:match_runs|match_results)", text)
    assert "fk_explanation_runs_match_run_id_match_runs" in text
    assert "fk_match_explanations_match_result_id_match_results" in text


def test_alembic_registers_phase9_models() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "app.models.explanation_run" in text
