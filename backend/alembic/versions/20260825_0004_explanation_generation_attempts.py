"""Add bounded Phase 9.4 explanation generation attempt audit.

Revision ID: 20260825_0004
Revises: 20260819_0003
Create Date: 2026-08-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260825_0004"
down_revision: str = "20260819_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "explanation_generation_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "explanation_run_id",
            sa.String(36),
            sa.ForeignKey(
                "explanation_runs.explanation_run_id",
                name="fk_explanation_attempts_explanation_run_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_category", sa.String(40)),
        sa.Column("provider_kind", sa.String(40), nullable=False),
        sa.Column("provider_name", sa.String(80), nullable=False),
        sa.Column("configured_model", sa.String(160), nullable=False),
        sa.Column("observed_model", sa.String(160)),
        sa.Column(
            "provider_configuration_fingerprint", sa.String(64), nullable=False
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "explanation_run_id",
            "attempt_number",
            name="uq_explanation_attempts_run_number",
        ),
        sa.CheckConstraint(
            "attempt_number BETWEEN 1 AND 2",
            name="ck_explanation_attempts_number",
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_explanation_attempts_status",
        ),
        sa.CheckConstraint(
            "error_category IS NULL OR error_category IN ("
            "'provider_timeout', 'provider_transport', 'provider_http_status', "
            "'malformed_response', 'invalid_output', 'grounding_failure', "
            "'provider_configuration', 'internal_error')",
            name="ck_explanation_attempts_error_category",
        ),
        sa.CheckConstraint(
            "(status = 'RUNNING' AND completed_at IS NULL AND error_category IS NULL) OR "
            "(status = 'COMPLETED' AND completed_at IS NOT NULL AND error_category IS NULL) OR "
            "(status = 'FAILED' AND completed_at IS NOT NULL AND error_category IS NOT NULL)",
            name="ck_explanation_attempts_lifecycle",
        ),
    )
    op.create_index(
        "ix_explanation_attempts_run_id",
        "explanation_generation_attempts",
        ["explanation_run_id"],
    )
    op.create_index(
        "ix_explanation_attempts_status",
        "explanation_generation_attempts",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_explanation_attempts_status",
        table_name="explanation_generation_attempts",
    )
    op.drop_index(
        "ix_explanation_attempts_run_id",
        table_name="explanation_generation_attempts",
    )
    op.drop_table("explanation_generation_attempts")
