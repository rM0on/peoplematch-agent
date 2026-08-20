"""Add Phase 9 evidence-grounded explanation persistence.

Revision ID: 20260819_0003
Revises: 20260818_0002
Create Date: 2026-08-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260819_0003"
down_revision: str = "20260818_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "explanation_runs",
        sa.Column("explanation_run_id", sa.String(36), primary_key=True),
        sa.Column(
            "match_run_id",
            sa.String(36),
            sa.ForeignKey(
                "match_runs.run_id",
                name="fk_explanation_runs_match_run_id_match_runs",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_top_k", sa.Integer(), nullable=False),
        sa.Column("effective_top_k", sa.Integer()),
        sa.Column("explanation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_bundle_version", sa.String(64)),
        sa.Column("evidence_bundle_fingerprint", sa.String(64)),
        sa.Column("evidence_bundle_json", postgresql.JSONB()),
        sa.Column("provider_evidence_version", sa.String(64)),
        sa.Column("provider_evidence_fingerprint", sa.String(64)),
        sa.Column("provider_evidence_json", postgresql.JSONB()),
        sa.Column("output_schema_version", sa.String(64)),
        sa.Column("provider_kind", sa.String(40)),
        sa.Column("provider_name", sa.String(80)),
        sa.Column("configured_model", sa.String(160)),
        sa.Column("observed_model", sa.String(160)),
        sa.Column("provider_configuration_fingerprint", sa.String(64)),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("prompt_fingerprint", sa.String(64)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repaired", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("result_fingerprint", sa.String(64)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_detail_safe", sa.String(500)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_explanation_runs_status",
        ),
        sa.CheckConstraint(
            "requested_top_k BETWEEN 1 AND 10",
            name="ck_explanation_runs_requested_top_k",
        ),
        sa.CheckConstraint(
            "effective_top_k IS NULL OR "
            "(effective_top_k BETWEEN 1 AND 10 AND effective_top_k <= requested_top_k)",
            name="ck_explanation_runs_effective_top_k",
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND 2",
            name="ck_explanation_runs_attempt_count",
        ),
        sa.CheckConstraint(
            "explanation_count BETWEEN 0 AND 10",
            name="ck_explanation_runs_explanation_count",
        ),
        sa.CheckConstraint(
            "NOT repaired OR attempt_count >= 2",
            name="ck_explanation_runs_repaired_attempts",
        ),
        sa.CheckConstraint(
            "(evidence_bundle_version IS NULL AND "
            "evidence_bundle_fingerprint IS NULL AND evidence_bundle_json IS NULL) OR "
            "(evidence_bundle_version IS NOT NULL AND "
            "evidence_bundle_fingerprint IS NOT NULL AND evidence_bundle_json IS NOT NULL)",
            name="ck_explanation_runs_evidence_bundle_group",
        ),
        sa.CheckConstraint(
            "(provider_evidence_version IS NULL AND "
            "provider_evidence_fingerprint IS NULL AND provider_evidence_json IS NULL) OR "
            "(provider_evidence_version IS NOT NULL AND "
            "provider_evidence_fingerprint IS NOT NULL AND provider_evidence_json IS NOT NULL)",
            name="ck_explanation_runs_provider_evidence_group",
        ),
        sa.CheckConstraint(
            "(prompt_version IS NULL AND prompt_fingerprint IS NULL) OR "
            "(prompt_version IS NOT NULL AND prompt_fingerprint IS NOT NULL)",
            name="ck_explanation_runs_prompt_group",
        ),
        sa.CheckConstraint(
            "status != 'RUNNING' OR "
            "(completed_at IS NULL AND error_code IS NULL AND "
            "error_detail_safe IS NULL AND explanation_count = 0 AND "
            "result_fingerprint IS NULL)",
            name="ck_explanation_runs_running_state",
        ),
        sa.CheckConstraint(
            "status != 'FAILED' OR "
            "(completed_at IS NOT NULL AND error_code IS NOT NULL AND "
            "error_detail_safe IS NOT NULL AND explanation_count = 0 AND "
            "result_fingerprint IS NULL)",
            name="ck_explanation_runs_failed_state",
        ),
        sa.CheckConstraint(
            "status != 'COMPLETED' OR "
            "(completed_at IS NOT NULL AND effective_top_k IS NOT NULL AND "
            "explanation_count = effective_top_k AND explanation_count > 0 AND "
            "evidence_bundle_version IS NOT NULL AND "
            "evidence_bundle_fingerprint IS NOT NULL AND evidence_bundle_json IS NOT NULL AND "
            "provider_evidence_version IS NOT NULL AND "
            "provider_evidence_fingerprint IS NOT NULL AND provider_evidence_json IS NOT NULL AND "
            "output_schema_version IS NOT NULL AND provider_kind IS NOT NULL AND "
            "provider_name IS NOT NULL AND configured_model IS NOT NULL AND "
            "provider_configuration_fingerprint IS NOT NULL AND "
            "prompt_version IS NOT NULL AND prompt_fingerprint IS NOT NULL AND "
            "attempt_count >= 1 AND result_fingerprint IS NOT NULL AND "
            "error_code IS NULL AND error_detail_safe IS NULL)",
            name="ck_explanation_runs_completed_state",
        ),
    )
    op.create_index(
        "ix_explanation_runs_match_run_id", "explanation_runs", ["match_run_id"]
    )
    op.create_index("ix_explanation_runs_status", "explanation_runs", ["status"])
    op.create_index(
        "ix_explanation_runs_created_at", "explanation_runs", ["created_at"]
    )

    op.create_table(
        "match_explanations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "explanation_run_id",
            sa.String(36),
            sa.ForeignKey(
                "explanation_runs.explanation_run_id",
                name="fk_match_explanations_explanation_run_id_explanation_runs",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "match_result_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "match_results.id",
                name="fk_match_explanations_match_result_id_match_results",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("candidate_id", sa.String(80), nullable=False),
        sa.Column("result_rank", sa.Integer(), nullable=False),
        sa.Column("output_schema_version", sa.String(64), nullable=False),
        sa.Column("validated_output_json", postgresql.JSONB(), nullable=False),
        sa.Column("candidate_output_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "explanation_run_id",
            "candidate_id",
            name="uq_match_explanations_candidate",
        ),
        sa.UniqueConstraint(
            "explanation_run_id",
            "result_rank",
            name="uq_match_explanations_rank",
        ),
        sa.UniqueConstraint(
            "explanation_run_id",
            "match_result_id",
            name="uq_match_explanations_match_result",
        ),
        sa.CheckConstraint(
            "result_rank >= 1", name="ck_match_explanations_result_rank"
        ),
    )
    op.create_index(
        "ix_match_explanations_match_result_id",
        "match_explanations",
        ["match_result_id"],
    )
    op.create_index(
        "ix_match_explanations_candidate_id",
        "match_explanations",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_match_explanations_candidate_id", table_name="match_explanations"
    )
    op.drop_index(
        "ix_match_explanations_match_result_id", table_name="match_explanations"
    )
    op.drop_table("match_explanations")
    op.drop_index("ix_explanation_runs_created_at", table_name="explanation_runs")
    op.drop_index("ix_explanation_runs_status", table_name="explanation_runs")
    op.drop_index("ix_explanation_runs_match_run_id", table_name="explanation_runs")
    op.drop_table("explanation_runs")
