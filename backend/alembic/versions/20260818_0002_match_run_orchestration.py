"""Add durable match-run orchestration and traceability.

Revision ID: 20260818_0002
Revises: 20260813_0001
Create Date: 2026-08-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260818_0002"
down_revision: str = "20260813_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "match_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("requested_job_id", sa.String(80), nullable=False),
        sa.Column("job_id", sa.String(80), sa.ForeignKey("job_profiles.job_id", ondelete="RESTRICT")),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("ranking_variant", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("request_parameters", postgresql.JSONB(), nullable=False),
        sa.Column("workflow_version", sa.String(64), nullable=False),
        sa.Column("workflow_fingerprint", sa.String(64), nullable=False),
        sa.Column("ranking_input_contract_version", sa.String(64), nullable=False),
        sa.Column("ranking_input_fingerprint", sa.String(64)),
        sa.Column("ranking_input_snapshot", postgresql.JSONB()),
        sa.Column("retrieval_document_version", sa.String(64), nullable=True),
        sa.Column("retrieval_configuration_fingerprint", sa.String(64), nullable=True),
        sa.Column("retrieval_provenance", postgresql.JSONB()),
        sa.Column("feature_version", sa.String(64), nullable=True),
        sa.Column("feature_fingerprint", sa.String(64), nullable=True),
        sa.Column("ranker_version", sa.String(64), nullable=True),
        sa.Column("ranker_model_sha256", sa.String(64), nullable=True),
        sa.Column("ce_provenance", postgresql.JSONB()),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_fingerprint", sa.String(64)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_detail_safe", sa.String(500)),
        sa.CheckConstraint("status IN ('RUNNING', 'COMPLETED', 'FAILED')", name="ck_match_runs_status"),
        sa.CheckConstraint("ranking_variant IN ('ltr', 'cross_encoder_experiment')", name="ck_match_runs_ranking_variant"),
        sa.CheckConstraint("result_count >= 0", name="ck_match_runs_result_count"),
    )
    op.create_index("ix_match_runs_job_id", "match_runs", ["job_id"])
    op.create_index("ix_match_runs_status", "match_runs", ["status"])
    op.create_index("ix_match_runs_ranking_variant", "match_runs", ["ranking_variant"])
    op.create_index("ix_match_runs_created_at", "match_runs", ["created_at"])

    op.create_table(
        "match_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("match_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.String(80), sa.ForeignKey("candidate_profiles.candidate_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("result_rank", sa.Integer(), nullable=False),
        sa.Column("candidate_input_contract_version", sa.String(64), nullable=False),
        sa.Column("candidate_input_fingerprint", sa.String(64), nullable=False),
        sa.Column("candidate_input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("retrieval_rank", sa.Integer(), nullable=False),
        sa.Column("matched_channels", postgresql.ARRAY(sa.String(16)), nullable=False),
        sa.Column("dense_rank", sa.Integer()),
        sa.Column("dense_score", sa.Float(53)),
        sa.Column("sparse_rank", sa.Integer()),
        sa.Column("sparse_score", sa.Float(53)),
        sa.Column("fusion_score", sa.Float(53)),
        sa.Column("semantic_score", sa.Float(53)),
        sa.Column("skill_fit_score", sa.Float(53)),
        sa.Column("project_evidence_score", sa.Float(53)),
        sa.Column("role_direction_score", sa.Float(53)),
        sa.Column("ai_tool_score", sa.Float(53)),
        sa.Column("location_score", sa.Float(53)),
        sa.Column("seniority_score", sa.Float(53)),
        sa.Column("missing_penalty", sa.Float(53)),
        sa.Column("overclaim_penalty", sa.Float(53)),
        sa.Column("feature_diagnostics_contract_version", sa.String(64), nullable=False),
        sa.Column("feature_diagnostics", postgresql.JSONB(), nullable=False),
        sa.Column("ltr_rank", sa.Integer(), nullable=False),
        sa.Column("ltr_score_raw", sa.Float(53), nullable=False),
        sa.Column("cross_encoder_rank", sa.Integer()),
        sa.Column("cross_encoder_score_raw", sa.Float(53)),
        sa.UniqueConstraint("run_id", "candidate_id", name="uq_match_results_candidate"),
        sa.UniqueConstraint("run_id", "result_rank", name="uq_match_results_rank"),
        sa.CheckConstraint("result_rank >= 1", name="ck_match_results_result_rank"),
        sa.CheckConstraint("ltr_rank >= 1", name="ck_match_results_ltr_rank"),
        sa.CheckConstraint("cross_encoder_rank IS NULL OR cross_encoder_rank >= 1", name="ck_match_results_ce_rank"),
    )
    op.create_index("ix_match_results_candidate_id", "match_results", ["candidate_id"])

    op.create_table(
        "run_steps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("match_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Float(53)),
        sa.Column("input_refs", postgresql.JSONB(), nullable=False),
        sa.Column("output_refs", postgresql.JSONB()),
        sa.Column("contract_version", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_detail_safe", sa.String(500)),
        sa.UniqueConstraint("run_id", "sequence", name="uq_run_steps_sequence"),
        sa.CheckConstraint("sequence >= 1", name="ck_run_steps_sequence"),
        sa.CheckConstraint("status IN ('RUNNING', 'COMPLETED', 'FAILED')", name="ck_run_steps_status"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_run_steps_duration"),
    )


def downgrade() -> None:
    op.drop_table("run_steps")
    op.drop_index("ix_match_results_candidate_id", table_name="match_results")
    op.drop_table("match_results")
    op.drop_index("ix_match_runs_created_at", table_name="match_runs")
    op.drop_index("ix_match_runs_ranking_variant", table_name="match_runs")
    op.drop_index("ix_match_runs_status", table_name="match_runs")
    op.drop_index("ix_match_runs_job_id", table_name="match_runs")
    op.drop_table("match_runs")
