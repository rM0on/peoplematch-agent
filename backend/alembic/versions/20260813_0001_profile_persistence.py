"""Add canonical candidate and job persistence tables.

Revision ID: 20260813_0001
Revises:
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260813_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("candidate_id", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("github_url", sa.String(300)),
        sa.Column("seniority", sa.String(32), nullable=False),
        sa.Column("data_origin", sa.String(32), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("dataset_version", sa.String(32)),
        sa.Column("dataset_archetype", sa.String(80)),
        sa.Column("ai_tools", postgresql.ARRAY(sa.String(120)), nullable=False),
        sa.Column("target_roles", postgresql.ARRAY(sa.String(160)), nullable=False),
        sa.Column("missing_fields", postgresql.ARRAY(sa.String(120)), nullable=False),
        sa.Column("preferred_locations", postgresql.JSONB(), nullable=False),
        sa.Column("work_style", postgresql.JSONB(), nullable=False),
        sa.Column("overclaim_risk", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_candidate_profiles_seniority", "candidate_profiles", ["seniority"])
    op.create_index("ix_candidate_profiles_data_origin", "candidate_profiles", ["data_origin"])
    op.create_table(
        "candidate_skills",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.String(80), sa.ForeignKey("candidate_profiles.candidate_id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("category", sa.String(48), nullable=False),
        sa.Column("self_reported_level", sa.String(32)),
        sa.UniqueConstraint("candidate_id", "name"),
    )
    op.create_table(
        "candidate_projects",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.String(80), sa.ForeignKey("candidate_profiles.candidate_id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("role", sa.String(120), nullable=False),
        sa.Column("technologies", postgresql.ARRAY(sa.String(120)), nullable=False),
        sa.Column("outcomes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("skills_demonstrated", postgresql.ARRAY(sa.String(120)), nullable=False),
        sa.UniqueConstraint("candidate_id", "project_id"),
    )
    op.create_table(
        "candidate_project_evidence",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.String(80), sa.ForeignKey("candidate_profiles.candidate_id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_id", sa.String(100), nullable=False),
        sa.Column("project_id", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("supports_skills", postgresql.ARRAY(sa.String(120)), nullable=False),
        sa.Column("evidence_type", sa.String(48), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("artifact_ref", sa.String(300), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.UniqueConstraint("candidate_id", "evidence_id"),
        sa.ForeignKeyConstraint(["candidate_id", "project_id"], ["candidate_projects.candidate_id", "candidate_projects.project_id"], ondelete="CASCADE"),
    )
    op.create_table(
        "job_profiles",
        sa.Column("job_id", sa.String(80), primary_key=True),
        sa.Column("company_name", sa.String(100), nullable=False),
        sa.Column("role_title", sa.String(120), nullable=False),
        sa.Column("raw_jd", sa.Text(), nullable=False),
        sa.Column("product_stage", sa.String(32), nullable=False),
        sa.Column("data_origin", sa.String(32), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("dataset_version", sa.String(32)),
        sa.Column("dataset_archetype", sa.String(80)),
        sa.Column("role_direction", postgresql.ARRAY(sa.String(120)), nullable=False),
        sa.Column("team_tags", postgresql.ARRAY(sa.String(120)), nullable=False),
        sa.Column("seniority_requirement", postgresql.ARRAY(sa.String(32)), nullable=False),
        sa.Column("evaluation_focus", postgresql.ARRAY(sa.String(160)), nullable=False),
        sa.Column("location", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_job_profiles_role_title", "job_profiles", ["role_title"])
    op.create_index("ix_job_profiles_data_origin", "job_profiles", ["data_origin"])
    op.create_table(
        "job_requirements",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(80), sa.ForeignKey("job_profiles.job_id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_id", sa.String(100), nullable=False),
        sa.Column("requirement_group", sa.String(24), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(48), nullable=False),
        sa.Column("text", sa.String(240), nullable=False),
        sa.Column("evidence_expectation", sa.String(300), nullable=False),
        sa.UniqueConstraint("job_id", "requirement_id"),
    )


def downgrade() -> None:
    op.drop_table("job_requirements")
    op.drop_index("ix_job_profiles_data_origin", table_name="job_profiles")
    op.drop_index("ix_job_profiles_role_title", table_name="job_profiles")
    op.drop_table("job_profiles")
    op.drop_table("candidate_project_evidence")
    op.drop_table("candidate_projects")
    op.drop_table("candidate_skills")
    op.drop_index("ix_candidate_profiles_data_origin", table_name="candidate_profiles")
    op.drop_index("ix_candidate_profiles_seniority", table_name="candidate_profiles")
    op.drop_table("candidate_profiles")
