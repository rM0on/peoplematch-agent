"""Add independent recruiter narrative presentation records.

Revision ID: 20260925_0006
Revises: 20260826_0005
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260925_0006"
down_revision: str = "20260826_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recruiter_narratives",
        sa.Column("narrative_id", sa.String(36), primary_key=True),
        sa.Column("explanation_run_id", sa.String(36), sa.ForeignKey("explanation_runs.explanation_run_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_explanation_id", sa.BigInteger(), sa.ForeignKey("match_explanations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("candidate_id", sa.String(80), nullable=False),
        sa.Column("result_rank", sa.Integer(), nullable=False),
        sa.Column("source_output_fingerprint", sa.String(64), nullable=False),
        sa.Column("source_bundle_fingerprint", sa.String(64), nullable=False),
        sa.Column("ranking_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("validation_status", sa.String(16), nullable=False),
        sa.Column("validated_content_json", postgresql.JSONB()),
        sa.Column("content_fingerprint", sa.String(64)),
        sa.Column("error_code", sa.String(48)),
        sa.Column("provider_kind", sa.String(40), nullable=False),
        sa.Column("provider_name", sa.String(80), nullable=False),
        sa.Column("configured_model", sa.String(160), nullable=False),
        sa.Column("observed_model", sa.String(160)),
        sa.Column("provider_configuration_fingerprint", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("prompt_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('COMPLETED', 'FAILED')", name="ck_recruiter_narratives_status"),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND validation_status = 'PASSED' AND "
            "validated_content_json IS NOT NULL AND content_fingerprint IS NOT NULL AND error_code IS NULL) OR "
            "(status = 'FAILED' AND validation_status = 'FAILED' AND "
            "validated_content_json IS NULL AND content_fingerprint IS NULL AND error_code IS NOT NULL)",
            name="ck_recruiter_narratives_content_state",
        ),
    )
    op.create_index(
        "ix_recruiter_narratives_source_explanation_id",
        "recruiter_narratives",
        ["source_explanation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recruiter_narratives_source_explanation_id", table_name="recruiter_narratives")
    op.drop_table("recruiter_narratives")
