from __future__ import annotations

import inspect
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint


def test_phase94_attempt_audit_migration_is_additive_and_bounded() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations = list((root / "alembic" / "versions").glob("20260825_0004*.py"))

    assert len(migrations) == 1
    text = migrations[0].read_text(encoding="utf-8")
    assert 'revision: str = "20260825_0004"' in text
    assert 'down_revision: str = "20260819_0003"' in text
    assert '"explanation_generation_attempts"' in text
    assert "attempt_number BETWEEN 1 AND 2" in text
    assert "UNIQUE" in text.upper() or "UniqueConstraint" in text
    assert "fk_explanation_attempts_explanation_run_id" in text
    assert "ondelete=\"RESTRICT\"" in text
    assert "alter_column" not in text
    assert not any(
        prohibited in text.lower()
        for prohibited in (
            "raw_prompt",
            "prompt_json",
            "provider_response",
            "response_body",
            "api_key",
            "authorization",
            "evidence_json",
            "private_payload",
            "stack_trace",
        )
    )

def test_attempt_audit_model_has_only_approved_metadata_columns() -> None:
    from app.models.explanation_attempt import ExplanationGenerationAttemptModel

    assert set(ExplanationGenerationAttemptModel.__table__.columns.keys()) == {
        "id",
        "explanation_run_id",
        "attempt_number",
        "status",
        "error_category",
        "provider_kind",
        "provider_name",
        "configured_model",
        "observed_model",
        "provider_configuration_fingerprint",
        "started_at",
        "completed_at",
    }
    constraints = ExplanationGenerationAttemptModel.__table__.constraints
    assert any(isinstance(item, UniqueConstraint) for item in constraints)
    checks = " ".join(
        str(item.sqltext)
        for item in constraints
        if isinstance(item, CheckConstraint)
    )
    assert "attempt_number" in checks and "1" in checks and "2" in checks
    assert "status" in checks
    assert "error_category" in checks


def test_attempt_repository_owns_lifecycle_lock_and_never_stores_payloads() -> None:
    from app.repositories.explanation_attempt_repository import (
        ExplanationAttemptRepository,
    )

    methods = {
        name
        for name, member in inspect.getmembers(
            ExplanationAttemptRepository, inspect.iscoroutinefunction
        )
        if not name.startswith("_")
    }
    assert {"start_attempt", "finish_attempt", "list_attempts"} <= methods

    source = inspect.getsource(inspect.getmodule(ExplanationAttemptRepository))
    assert "with_for_update" in source
    assert "ExplanationRunStatus.RUNNING" in source or 'status != "RUNNING"' in source
    assert "attempt_number" in source
    assert "1, 2" in source or "attempt_number > 2" in source
    assert not any(
        prohibited in source.lower()
        for prohibited in (
            "raw_prompt",
            "prompt_json",
            "provider_response",
            "response_body",
            "api_key",
            "authorization",
            "evidence_bundle_json",
            "provider_evidence_json",
            "stack_trace",
        )
    )
