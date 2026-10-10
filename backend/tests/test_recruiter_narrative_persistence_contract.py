from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_recruiter_narrative_is_append_only_separate_table_with_source_links():
    from app.models.recruiter_narrative import RecruiterNarrativeModel

    table = RecruiterNarrativeModel.__table__
    assert table.name == "recruiter_narratives"
    assert {"source_explanation_id", "explanation_run_id", "source_output_fingerprint", "ranking_fingerprint", "validated_content_json"} <= set(table.c.keys())
    assert any(
        constraint.name == "ck_recruiter_narratives_content_state"
        for constraint in table.constraints if isinstance(constraint, CheckConstraint)
    )


def test_recruiter_narrative_migration_is_additive_after_phase10():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    revision = script.get_revision(head)

    assert head == "20260925_0006"
    assert revision.down_revision == "20260826_0005"
