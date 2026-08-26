"""Add Phase 10 feedback and bad-case management records.

Revision ID: 20260826_0005
Revises: 20260825_0004
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260826_0005"
down_revision: str = "20260825_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback_records",
        sa.Column("feedback_id", sa.String(36), primary_key=True),
        sa.Column("contract_version", sa.String(64), nullable=False),
        sa.Column("feedback_type", sa.String(24), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column(
            "match_run_id",
            sa.String(36),
            sa.ForeignKey("match_runs.run_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "match_result_id",
            sa.BigInteger(),
            sa.ForeignKey("match_results.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "comparison_match_result_id",
            sa.BigInteger(),
            sa.ForeignKey("match_results.id", ondelete="RESTRICT"),
        ),
        sa.Column("candidate_id", sa.String(80)),
        sa.Column("comparison_candidate_id", sa.String(80)),
        sa.Column("result_rank", sa.Integer()),
        sa.Column("comparison_result_rank", sa.Integer()),
        sa.Column("expected_candidate_reference", sa.String(160)),
        sa.Column("job_id", sa.String(80), nullable=False),
        sa.Column(
            "explanation_run_id",
            sa.String(36),
            sa.ForeignKey(
                "explanation_runs.explanation_run_id", ondelete="RESTRICT"
            ),
        ),
        sa.Column(
            "match_explanation_id",
            sa.BigInteger(),
            sa.ForeignKey("match_explanations.id", ondelete="RESTRICT"),
        ),
        sa.Column("value", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(80)),
        sa.Column("field_locator", sa.String(80)),
        sa.Column("evidence_reference", sa.String(200)),
        sa.Column("comment", sa.String(500)),
        sa.Column(
            "supersedes_feedback_id",
            sa.String(36),
            sa.ForeignKey("feedback_records.feedback_id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "contract_version = 'feedback_record_v1'",
            name="ck_feedback_records_contract_version",
        ),
        sa.CheckConstraint(
            "feedback_type IN ('ranking', 'explanation', 'profile_data')",
            name="ck_feedback_records_type",
        ),
        sa.CheckConstraint(
            "target_type IN ("
            "'overall_ranking', 'top1', 'candidate_result', 'pairwise', "
            "'summary', 'match_reason', 'risk', 'missing_requirement', "
            "'interview_question', 'top1_comparison', 'rewrite_operation', "
            "'candidate_profile', 'job_profile', 'expected_candidate')",
            name="ck_feedback_records_target_type",
        ),
        sa.CheckConstraint("origin = 'human'", name="ck_feedback_records_origin"),
        sa.CheckConstraint(
            "result_rank IS NULL OR result_rank >= 1",
            name="ck_feedback_records_result_rank",
        ),
        sa.CheckConstraint(
            "comparison_result_rank IS NULL OR comparison_result_rank >= 1",
            name="ck_feedback_records_comparison_rank",
        ),
        sa.CheckConstraint(
            "value IN ('correct', 'wrong', 'uncertain', 'insufficient_evidence', "
            "'grounded', 'unsupported', 'misleading', 'incomplete', "
            "'missing_skill', 'incorrect_skill', 'missing_project_evidence', "
            "'incorrect_project_evidence_status', 'incorrect_seniority', "
            "'incorrect_location', 'incorrect_role_direction', "
            "'unclear_requirement', 'missing_requirement', "
            "'incorrect_requirement_priority', 'incorrect_seniority_requirement', "
            "'incorrect_location_constraint', 'missing_expectation')",
            name="ck_feedback_records_value",
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code IN ('wrong_top1', "
            "'ranking_inversion', 'false_positive', 'false_negative', "
            "'constraint_conflict', 'evidence_coverage_disagreement')",
            name="ck_feedback_records_reason_code",
        ),
        sa.CheckConstraint(
            "field_locator IS NULL OR field_locator IN ('candidate.skills', "
            "'candidate.project_evidence', 'candidate.seniority', "
            "'candidate.location', 'candidate.role_direction', 'job.requirements', "
            "'job.requirement_priority', 'job.seniority', 'job.location', "
            "'job.expectations')",
            name="ck_feedback_records_field_locator",
        ),
        sa.CheckConstraint(
            "expected_candidate_reference IS NULL OR "
            "expected_candidate_reference LIKE 'expected_candidate:%'",
            name="ck_feedback_records_expected_candidate_reference",
        ),
        sa.CheckConstraint(
            "feedback_type != 'ranking' OR value != 'wrong' OR ("
            "(target_type = 'overall_ranking' AND reason_code IN ("
            "'constraint_conflict', 'evidence_coverage_disagreement')) OR "
            "(target_type = 'top1' AND reason_code = 'wrong_top1') OR "
            "(target_type = 'candidate_result' AND reason_code IN ("
            "'false_positive', 'constraint_conflict', "
            "'evidence_coverage_disagreement')) OR "
            "(target_type = 'pairwise' AND reason_code IN ("
            "'ranking_inversion', 'constraint_conflict', "
            "'evidence_coverage_disagreement')) OR "
            "(target_type = 'expected_candidate' AND "
            "reason_code = 'false_negative'))",
            name="ck_feedback_records_ranking_reason_compatibility",
        ),
        sa.CheckConstraint(
            "feedback_type != 'profile_data' OR ("
            "(value IN ('missing_skill', 'incorrect_skill') AND "
            "field_locator = 'candidate.skills') OR "
            "(value IN ('missing_project_evidence', "
            "'incorrect_project_evidence_status') AND "
            "field_locator = 'candidate.project_evidence') OR "
            "(value = 'incorrect_seniority' AND "
            "field_locator = 'candidate.seniority') OR "
            "(value = 'incorrect_location' AND "
            "field_locator = 'candidate.location') OR "
            "(value = 'incorrect_role_direction' AND "
            "field_locator = 'candidate.role_direction') OR "
            "(value IN ('unclear_requirement', 'missing_requirement') AND "
            "field_locator = 'job.requirements') OR "
            "(value = 'incorrect_requirement_priority' AND "
            "field_locator = 'job.requirement_priority') OR "
            "(value = 'incorrect_seniority_requirement' AND "
            "field_locator = 'job.seniority') OR "
            "(value = 'incorrect_location_constraint' AND "
            "field_locator = 'job.location') OR "
            "(value = 'missing_expectation' AND "
            "field_locator = 'job.expectations'))",
            name="ck_feedback_records_profile_issue_compatibility",
        ),
        sa.CheckConstraint(
            "feedback_id != supersedes_feedback_id",
            name="ck_feedback_records_self_supersession",
        ),
        sa.CheckConstraint(
            "(feedback_type = 'ranking' AND explanation_run_id IS NULL AND "
            "match_explanation_id IS NULL AND field_locator IS NULL AND "
            "evidence_reference IS NULL AND ("
            "(target_type = 'overall_ranking' AND match_result_id IS NULL AND "
            "comparison_match_result_id IS NULL AND candidate_id IS NULL AND "
            "comparison_candidate_id IS NULL AND result_rank IS NULL AND "
            "comparison_result_rank IS NULL AND expected_candidate_reference IS NULL) OR "
            "(target_type IN ('top1', 'candidate_result') AND match_result_id IS NOT NULL AND "
            "comparison_match_result_id IS NULL AND candidate_id IS NOT NULL AND "
            "comparison_candidate_id IS NULL AND result_rank IS NOT NULL AND "
            "comparison_result_rank IS NULL AND expected_candidate_reference IS NULL) OR "
            "(target_type = 'pairwise' AND match_result_id IS NOT NULL AND "
            "comparison_match_result_id IS NOT NULL AND "
            "match_result_id != comparison_match_result_id AND candidate_id IS NOT NULL AND "
            "comparison_candidate_id IS NOT NULL AND candidate_id != comparison_candidate_id AND "
            "result_rank IS NOT NULL AND comparison_result_rank IS NOT NULL AND "
            "expected_candidate_reference IS NULL) OR "
            "(target_type = 'expected_candidate' AND match_result_id IS NULL AND "
            "comparison_match_result_id IS NULL AND candidate_id IS NULL AND "
            "comparison_candidate_id IS NULL AND result_rank IS NULL AND "
            "comparison_result_rank IS NULL AND expected_candidate_reference IS NOT NULL)) AND "
            "((value = 'wrong' AND reason_code IS NOT NULL) OR "
            "(value IN ('correct', 'uncertain', 'insufficient_evidence') AND reason_code IS NULL))) OR "
            "(feedback_type = 'explanation' AND target_type IN ('summary', 'match_reason', "
            "'risk', 'missing_requirement', 'interview_question', 'top1_comparison', "
            "'rewrite_operation') AND explanation_run_id IS NOT NULL AND "
            "match_explanation_id IS NOT NULL AND match_result_id IS NOT NULL AND "
            "candidate_id IS NOT NULL AND result_rank IS NOT NULL AND "
            "comparison_match_result_id IS NULL AND comparison_candidate_id IS NULL AND "
            "comparison_result_rank IS NULL AND expected_candidate_reference IS NULL AND "
            "reason_code IS NULL AND field_locator IS NULL AND "
            "value IN ('grounded', 'unsupported', 'misleading', 'incomplete')) OR "
            "(feedback_type = 'profile_data' AND explanation_run_id IS NULL AND "
            "match_explanation_id IS NULL AND comparison_match_result_id IS NULL AND "
            "comparison_candidate_id IS NULL AND comparison_result_rank IS NULL AND "
            "expected_candidate_reference IS NULL AND reason_code IS NULL AND "
            "evidence_reference IS NULL AND field_locator IS NOT NULL AND ("
            "(target_type = 'candidate_profile' AND match_result_id IS NOT NULL AND "
            "candidate_id IS NOT NULL AND result_rank IS NOT NULL) OR "
            "(target_type = 'job_profile' AND match_result_id IS NULL AND "
            "candidate_id IS NULL AND result_rank IS NULL)))",
            name="ck_feedback_records_semantic_shape",
        ),
    )
    op.create_index("ix_feedback_records_match_run_id", "feedback_records", ["match_run_id"])
    op.create_index(
        "ix_feedback_records_explanation_run_id",
        "feedback_records",
        ["explanation_run_id"],
    )
    op.create_index("ix_feedback_records_type", "feedback_records", ["feedback_type"])
    op.create_index("ix_feedback_records_created_at", "feedback_records", ["created_at"])

    op.create_table(
        "system_signals",
        sa.Column("signal_id", sa.String(36), primary_key=True),
        sa.Column("contract_version", sa.String(64), nullable=False),
        sa.Column(
            "match_run_id",
            sa.String(36),
            sa.ForeignKey("match_runs.run_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "explanation_run_id",
            sa.String(36),
            sa.ForeignKey(
                "explanation_runs.explanation_run_id", ondelete="RESTRICT"
            ),
        ),
        sa.Column("signal_code", sa.String(64), nullable=False),
        sa.Column("source_stage", sa.String(64), nullable=False),
        sa.Column("source_error_code", sa.String(80)),
        sa.Column("occurrence_identity", sa.String(160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "match_run_id",
            "signal_code",
            "occurrence_identity",
            name="uq_system_signals_occurrence",
        ),
        sa.CheckConstraint(
            "contract_version = 'system_signal_v1'",
            name="ck_system_signals_contract_version",
        ),
        sa.CheckConstraint(
            "signal_code IN ("
            "'snapshot_fingerprint_mismatch', 'result_fingerprint_mismatch', "
            "'cross_owner_reference', 'terminal_lifecycle_violation', "
            "'explanation_grounding_failure', 'attempt_audit_mismatch')",
            name="ck_system_signals_code",
        ),
        sa.CheckConstraint(
            "source_stage IN ('match_run', 'evidence', 'explanation', 'persistence')",
            name="ck_system_signals_source_stage",
        ),
    )
    op.create_index("ix_system_signals_match_run_id", "system_signals", ["match_run_id"])
    op.create_index(
        "ix_system_signals_explanation_run_id",
        "system_signals",
        ["explanation_run_id"],
    )
    op.create_index("ix_system_signals_created_at", "system_signals", ["created_at"])

    op.create_table(
        "bad_cases",
        sa.Column("bad_case_id", sa.String(36), primary_key=True),
        sa.Column("case_contract_version", sa.String(64), nullable=False),
        sa.Column("taxonomy_version", sa.String(64), nullable=False),
        sa.Column(
            "primary_match_run_id",
            sa.String(36),
            sa.ForeignKey("match_runs.run_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "primary_match_result_id",
            sa.BigInteger(),
            sa.ForeignKey("match_results.id", ondelete="RESTRICT"),
        ),
        sa.Column("historical_job_id", sa.String(80), nullable=False),
        sa.Column("historical_candidate_id", sa.String(80)),
        sa.Column("result_rank", sa.Integer()),
        sa.Column(
            "primary_explanation_run_id",
            sa.String(36),
            sa.ForeignKey(
                "explanation_runs.explanation_run_id", ondelete="RESTRICT"
            ),
        ),
        sa.Column(
            "primary_match_explanation_id",
            sa.BigInteger(),
            sa.ForeignKey("match_explanations.id", ondelete="RESTRICT"),
        ),
        sa.Column("symptom_code", sa.String(64), nullable=False),
        sa.Column("symptom_family", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "duplicate_of_bad_case_id",
            sa.String(36),
            sa.ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "related_case_id",
            sa.String(36),
            sa.ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "case_contract_version = 'bad_case_v1'",
            name="ck_bad_cases_contract_version",
        ),
        sa.CheckConstraint(
            "taxonomy_version = 'bad_case_taxonomy_v1'",
            name="ck_bad_cases_taxonomy_version",
        ),
        sa.CheckConstraint(
            "symptom_code IN ('wrong_top1', 'ranking_inversion', 'false_positive', "
            "'false_negative', 'constraint_conflict', 'uncertain_order', "
            "'expected_candidate_not_recalled', 'irrelevant_candidate_recalled', "
            "'filter_exclusion_disagreement', 'pool_truncation_concern', "
            "'missing_support', 'incorrect_support_status', "
            "'project_skill_link_disagreement', 'requirement_coverage_disagreement', "
            "'unsupported_explanation', 'misleading_explanation', "
            "'incomplete_explanation', 'incorrect_gap_statement', "
            "'incorrect_top1_comparison', 'candidate_snapshot_issue', "
            "'job_snapshot_issue', 'requirement_issue', 'constraint_issue', "
            "'history_integrity_failure', 'ownership_failure', 'lifecycle_failure', "
            "'provider_attempt_failure')",
            name="ck_bad_cases_category",
        ),
        sa.CheckConstraint(
            "symptom_family IN ('RANKING', 'RETRIEVAL', 'EVIDENCE', "
            "'EXPLANATION', 'DATA_QUALITY', 'INTEGRITY_OPERATIONS')",
            name="ck_bad_cases_symptom_family",
        ),
        sa.CheckConstraint(
            "(symptom_family = 'RANKING' AND symptom_code IN ('wrong_top1', "
            "'ranking_inversion', 'false_positive', 'false_negative', "
            "'constraint_conflict', 'uncertain_order')) OR "
            "(symptom_family = 'RETRIEVAL' AND symptom_code IN ("
            "'expected_candidate_not_recalled', 'irrelevant_candidate_recalled', "
            "'filter_exclusion_disagreement', 'pool_truncation_concern')) OR "
            "(symptom_family = 'EVIDENCE' AND symptom_code IN ('missing_support', "
            "'incorrect_support_status', 'project_skill_link_disagreement', "
            "'requirement_coverage_disagreement')) OR "
            "(symptom_family = 'EXPLANATION' AND symptom_code IN ("
            "'unsupported_explanation', 'misleading_explanation', "
            "'incomplete_explanation', 'incorrect_gap_statement', "
            "'incorrect_top1_comparison')) OR "
            "(symptom_family = 'DATA_QUALITY' AND symptom_code IN ("
            "'candidate_snapshot_issue', 'job_snapshot_issue', 'requirement_issue', "
            "'constraint_issue')) OR "
            "(symptom_family = 'INTEGRITY_OPERATIONS' AND symptom_code IN ("
            "'history_integrity_failure', 'ownership_failure', 'lifecycle_failure', "
            "'provider_attempt_failure'))",
            name="ck_bad_cases_symptom_family_consistency",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_bad_cases_severity",
        ),
        sa.CheckConstraint(
            "status IN ('CREATED', 'REVIEWED', 'ROOT_CAUSE_IDENTIFIED', "
            "'ACTION_PLANNED', 'RESOLVED', 'VERIFIED', 'DISMISSED', 'DUPLICATE')",
            name="ck_bad_cases_status",
        ),
        sa.CheckConstraint("revision >= 0", name="ck_bad_cases_revision"),
        sa.CheckConstraint(
            "result_rank IS NULL OR result_rank >= 1",
            name="ck_bad_cases_result_rank",
        ),
        sa.CheckConstraint(
            "(status = 'DUPLICATE' AND duplicate_of_bad_case_id IS NOT NULL) OR "
            "(status != 'DUPLICATE' AND duplicate_of_bad_case_id IS NULL)",
            name="ck_bad_cases_duplicate_owner",
        ),
        sa.CheckConstraint(
            "related_case_id IS NULL OR (related_case_id != bad_case_id AND "
            "related_case_id IS DISTINCT FROM duplicate_of_bad_case_id)",
            name="ck_bad_cases_related_owner",
        ),
    )
    op.create_index("ix_bad_cases_match_run_id", "bad_cases", ["primary_match_run_id"])
    op.create_index(
        "ix_bad_cases_match_result_id", "bad_cases", ["primary_match_result_id"]
    )
    op.create_index(
        "ix_bad_cases_explanation_run_id", "bad_cases", ["primary_explanation_run_id"]
    )
    op.create_index(
        "ix_bad_cases_historical_job_id", "bad_cases", ["historical_job_id"]
    )
    op.create_index(
        "ix_bad_cases_historical_candidate_id",
        "bad_cases",
        ["historical_candidate_id"],
    )
    op.create_index("ix_bad_cases_status", "bad_cases", ["status"])
    op.create_index("ix_bad_cases_severity", "bad_cases", ["severity"])
    op.create_index("ix_bad_cases_symptom_code", "bad_cases", ["symptom_code"])
    op.create_index("ix_bad_cases_created_at", "bad_cases", ["created_at"])

    op.create_table(
        "bad_case_source_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "bad_case_id",
            sa.String(36),
            sa.ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "feedback_id",
            sa.String(36),
            sa.ForeignKey("feedback_records.feedback_id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "system_signal_id",
            sa.String(36),
            sa.ForeignKey("system_signals.signal_id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(feedback_id IS NOT NULL AND system_signal_id IS NULL) OR "
            "(feedback_id IS NULL AND system_signal_id IS NOT NULL)",
            name="ck_bad_case_source_exactly_one",
        ),
        sa.UniqueConstraint(
            "bad_case_id", "feedback_id", name="uq_bad_case_feedback"
        ),
        sa.UniqueConstraint(
            "bad_case_id", "system_signal_id", name="uq_bad_case_system_signal"
        ),
    )
    op.create_index(
        "ix_bad_case_source_links_case_id", "bad_case_source_links", ["bad_case_id"]
    )

    op.create_table(
        "feedback_evidence_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "bad_case_id",
            sa.String(36),
            sa.ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "explanation_run_id",
            sa.String(36),
            sa.ForeignKey(
                "explanation_runs.explanation_run_id", ondelete="RESTRICT"
            ),
        ),
        sa.Column("evidence_reference", sa.String(200)),
        sa.Column("field_locator", sa.String(80)),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("evidence_kind", sa.String(64)),
        sa.Column("candidate_id", sa.String(80)),
        sa.Column("result_rank", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(evidence_reference IS NOT NULL AND field_locator IS NULL) OR "
            "(evidence_reference IS NULL AND field_locator IS NOT NULL)",
            name="ck_feedback_evidence_link_exactly_one",
        ),
        sa.CheckConstraint(
            "purpose IN ('supports_observation', 'disputed_reference', "
            "'missing_expected_evidence')",
            name="ck_feedback_evidence_links_purpose",
        ),
        sa.CheckConstraint(
            "result_rank IS NULL OR result_rank >= 1",
            name="ck_feedback_evidence_links_rank",
        ),
        sa.CheckConstraint(
            "evidence_kind IS NULL OR evidence_kind IN ('job_requirement', 'skill', "
            "'project', 'project_evidence', 'retrieval', 'feature', 'ranking', "
            "'diagnostic', 'comparison')",
            name="ck_feedback_evidence_links_kind",
        ),
        sa.CheckConstraint(
            "field_locator IS NULL OR field_locator IN ('candidate.skills', "
            "'candidate.project_evidence', 'candidate.seniority', "
            "'candidate.location', 'candidate.role_direction', 'job.requirements', "
            "'job.requirement_priority', 'job.seniority', 'job.location', "
            "'job.expectations')",
            name="ck_feedback_evidence_links_field_locator",
        ),
        sa.CheckConstraint(
            "(evidence_reference IS NOT NULL AND explanation_run_id IS NOT NULL AND "
            "evidence_kind IS NOT NULL AND ((candidate_id IS NULL AND result_rank IS NULL) OR "
            "(candidate_id IS NOT NULL AND result_rank IS NOT NULL))) OR "
            "(field_locator IS NOT NULL AND explanation_run_id IS NULL AND "
            "evidence_kind IS NULL AND ((field_locator LIKE 'candidate.%' AND "
            "candidate_id IS NOT NULL AND result_rank IS NOT NULL) OR "
            "(field_locator LIKE 'job.%' AND candidate_id IS NULL AND result_rank IS NULL)))",
            name="ck_feedback_evidence_links_owner",
        ),
        sa.UniqueConstraint(
            "bad_case_id",
            "explanation_run_id",
            "evidence_reference",
            "purpose",
            name="uq_feedback_evidence_reference",
        ),
        sa.UniqueConstraint(
            "bad_case_id",
            "field_locator",
            "purpose",
            name="uq_feedback_field_locator",
        ),
        sa.UniqueConstraint(
            "id", "bad_case_id", name="uq_feedback_evidence_link_owner"
        ),
        sa.CheckConstraint(
            "(field_locator IS NOT NULL AND purpose = 'missing_expected_evidence') OR "
            "(evidence_reference IS NOT NULL AND purpose IN ("
            "'supports_observation', 'disputed_reference'))",
            name="ck_feedback_evidence_links_purpose_shape",
        ),
        sa.CheckConstraint(
            "evidence_reference IS NULL OR ("
            "(evidence_kind = 'job_requirement' AND candidate_id IS NULL AND "
            "result_rank IS NULL AND evidence_reference LIKE 'job_requirement:%') OR "
            "(candidate_id IS NOT NULL AND result_rank IS NOT NULL AND ("
            "(evidence_kind = 'skill' AND evidence_reference LIKE "
            "'candidate:' || CAST(result_rank AS VARCHAR) || ':skill:%') OR "
            "(evidence_kind = 'project' AND evidence_reference LIKE "
            "'candidate:' || CAST(result_rank AS VARCHAR) || ':project:%') OR "
            "(evidence_kind = 'project_evidence' AND evidence_reference LIKE "
            "'candidate:' || CAST(result_rank AS VARCHAR) || ':project_evidence:%') OR "
            "(evidence_kind = 'retrieval' AND evidence_reference LIKE "
            "'retrieval:' || CAST(result_rank AS VARCHAR) || ':%') OR "
            "(evidence_kind = 'feature' AND evidence_reference LIKE "
            "'feature:' || CAST(result_rank AS VARCHAR) || ':%') OR "
            "(evidence_kind = 'ranking' AND evidence_reference LIKE "
            "'ranking:' || CAST(result_rank AS VARCHAR) || ':%') OR "
            "(evidence_kind = 'diagnostic' AND evidence_reference LIKE "
            "'diagnostic:' || CAST(result_rank AS VARCHAR) || ':%') OR "
            "(evidence_kind = 'comparison' AND evidence_reference LIKE "
            "'comparison:' || CAST(result_rank AS VARCHAR) || ':top1:%'))))",
            name="ck_feedback_evidence_links_namespace_owner",
        ),
    )
    op.create_index(
        "ix_feedback_evidence_links_case_id", "feedback_evidence_links", ["bad_case_id"]
    )

    op.create_table(
        "bad_case_analyses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "bad_case_id",
            sa.String(36),
            sa.ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("assessment", sa.String(16), nullable=False),
        sa.Column("root_cause_type", sa.String(24), nullable=False),
        sa.Column("root_cause_code", sa.String(80), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column(
            "supporting_evidence_link_id",
            sa.BigInteger(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "bad_case_id", "revision_number", name="uq_bad_case_analysis_revision"
        ),
        sa.UniqueConstraint("id", "bad_case_id", name="uq_bad_case_analysis_owner"),
        sa.ForeignKeyConstraint(
            ["supporting_evidence_link_id", "bad_case_id"],
            ["feedback_evidence_links.id", "feedback_evidence_links.bad_case_id"],
            name="fk_bad_case_analyses_support_owner",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "revision_number >= 1", name="ck_bad_case_analyses_revision"
        ),
        sa.CheckConstraint(
            "assessment IN ('suspected', 'supported', 'confirmed', 'rejected')",
            name="ck_bad_case_analyses_assessment",
        ),
        sa.CheckConstraint(
            "root_cause_type IN ('ranking', 'retrieval', 'feature', 'evidence', "
            "'explanation', 'data_quality', 'integrity')",
            name="ck_bad_case_analyses_root_cause_type",
        ),
        sa.CheckConstraint(
            "root_cause_code IN ('ranking_wrong_top1', 'ranking_pairwise_inversion', "
            "'ranking_false_positive', 'ranking_false_negative', "
            "'ranking_tie_break_issue', 'ranking_constraint_policy_issue', "
            "'retrieval_recall_miss', 'retrieval_filter_exclusion', "
            "'retrieval_dense_coverage_gap', 'retrieval_sparse_coverage_gap', "
            "'retrieval_fusion_issue', 'retrieval_pool_truncation', "
            "'retrieval_index_integrity', 'feature_semantic_score_issue', "
            "'feature_sparse_score_issue', 'feature_skill_fit_issue', "
            "'feature_project_evidence_issue', 'feature_role_direction_issue', "
            "'feature_location_issue', 'feature_seniority_issue', "
            "'feature_missing_penalty_issue', 'feature_overclaim_penalty_issue', "
            "'feature_availability_issue', 'evidence_missing_project_support', "
            "'evidence_status_incorrect', 'evidence_skill_project_link_incorrect', "
            "'evidence_requirement_alignment_incorrect', "
            "'evidence_claim_promoted_without_support', 'evidence_owner_mismatch', "
            "'explanation_unsupported_claim', 'explanation_misleading_template', "
            "'explanation_incomplete_selection', 'explanation_incorrect_gap', "
            "'explanation_comparison_mismatch', 'explanation_reference_ownership', "
            "'explanation_clarity_issue', 'data_candidate_skill_missing', "
            "'data_candidate_skill_incorrect', 'data_project_evidence_missing', "
            "'data_candidate_seniority_incorrect', 'data_candidate_location_incorrect', "
            "'data_job_requirement_unclear', 'data_job_requirement_missing', "
            "'data_job_requirement_priority_incorrect', 'data_job_level_incorrect', "
            "'data_job_expectation_missing', 'integrity_snapshot_fingerprint', "
            "'integrity_result_fingerprint', 'integrity_cross_owner_reference', "
            "'integrity_terminal_overwrite', 'integrity_attempt_audit')",
            name="ck_bad_case_analyses_root_cause_code",
        ),
        sa.CheckConstraint(
            "(root_cause_type = 'ranking' AND root_cause_code LIKE 'ranking_%') OR "
            "(root_cause_type = 'retrieval' AND root_cause_code LIKE 'retrieval_%') OR "
            "(root_cause_type = 'feature' AND root_cause_code LIKE 'feature_%') OR "
            "(root_cause_type = 'evidence' AND root_cause_code LIKE 'evidence_%') OR "
            "(root_cause_type = 'explanation' AND root_cause_code LIKE 'explanation_%') OR "
            "(root_cause_type = 'data_quality' AND root_cause_code LIKE 'data_%') OR "
            "(root_cause_type = 'integrity' AND root_cause_code LIKE 'integrity_%')",
            name="ck_bad_case_analyses_root_cause_compatibility",
        ),
        sa.CheckConstraint(
            "assessment NOT IN ('supported', 'confirmed') OR "
            "supporting_evidence_link_id IS NOT NULL",
            name="ck_bad_case_analyses_support",
        ),
    )
    op.create_index("ix_bad_case_analyses_case_id", "bad_case_analyses", ["bad_case_id"])

    op.create_table(
        "resolution_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "bad_case_id",
            sa.String(36),
            sa.ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(80), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "supersedes_action_id",
            sa.BigInteger(),
        ),
        sa.Column("safe_change_reference", sa.String(160)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "action_type IN ('data_correction_proposal', "
            "'retrieval_change_hypothesis', 'filter_policy_hypothesis', "
            "'fusion_policy_hypothesis', 'pool_policy_hypothesis', "
            "'feature_rule_hypothesis', 'feature_contract_hypothesis', "
            "'ranking_change_hypothesis', 'ranking_contract_hypothesis', "
            "'constraint_policy_hypothesis', 'data_integrity_action', "
            "'evidence_rule_hypothesis', 'evidence_integrity_action', "
            "'planning_policy_hypothesis', 'template_change_hypothesis', "
            "'grounding_integrity_action', 'integrity_repair_action', "
            "'documentation_action', 'no_change')",
            name="ck_resolution_actions_action_type",
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'cancelled', "
            "'superseded')",
            name="ck_resolution_actions_status",
        ),
        sa.CheckConstraint(
            "(status IN ('planned', 'in_progress') AND completed_at IS NULL) OR "
            "(status IN ('completed', 'cancelled', 'superseded') AND "
            "completed_at IS NOT NULL)",
            name="ck_resolution_actions_lifecycle",
        ),
        sa.CheckConstraint(
            "supersedes_action_id IS NULL OR supersedes_action_id != id",
            name="ck_resolution_actions_self_supersession",
        ),
        sa.UniqueConstraint("id", "bad_case_id", name="uq_resolution_action_owner"),
        sa.ForeignKeyConstraint(
            ["supersedes_action_id", "bad_case_id"],
            ["resolution_actions.id", "resolution_actions.bad_case_id"],
            name="fk_resolution_actions_supersedes_owner",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_resolution_actions_case_id", "resolution_actions", ["bad_case_id"])

    op.create_table(
        "bad_case_transitions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "bad_case_id",
            sa.String(36),
            sa.ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(32), nullable=False),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.Column(
            "analysis_id",
            sa.BigInteger(),
        ),
        sa.Column(
            "action_id",
            sa.BigInteger(),
        ),
        sa.Column("previous_revision", sa.Integer(), nullable=False),
        sa.Column("new_revision", sa.Integer(), nullable=False),
        sa.Column("verification_reference", sa.String(160)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_status IN ('CREATED', 'REVIEWED', 'ROOT_CAUSE_IDENTIFIED', "
            "'ACTION_PLANNED', 'RESOLVED', 'VERIFIED', 'DISMISSED', 'DUPLICATE') "
            "AND to_status IN ('CREATED', 'REVIEWED', 'ROOT_CAUSE_IDENTIFIED', "
            "'ACTION_PLANNED', 'RESOLVED', 'VERIFIED', 'DISMISSED', 'DUPLICATE')",
            name="ck_bad_case_transitions_status",
        ),
        sa.CheckConstraint(
            "new_revision = previous_revision + 1",
            name="ck_bad_case_transitions_revision",
        ),
        sa.CheckConstraint(
            "from_status != to_status",
            name="ck_bad_case_transitions_status_change",
        ),
        sa.CheckConstraint(
            "reason IN ('review_completed', 'root_cause_supported', 'action_created', "
            "'actions_completed', 'verification_linked', 'case_dismissed', "
            "'duplicate_linked', 'case_reopened')",
            name="ck_bad_case_transitions_reason",
        ),
        sa.CheckConstraint(
            "origin IN ('manual_review', 'system_rule')",
            name="ck_bad_case_transitions_origin",
        ),
        sa.CheckConstraint(
            "(from_status = 'CREATED' AND to_status = 'REVIEWED' AND "
            "reason = 'review_completed') OR "
            "(from_status = 'REVIEWED' AND to_status = 'ROOT_CAUSE_IDENTIFIED' AND "
            "reason = 'root_cause_supported') OR "
            "(from_status = 'ROOT_CAUSE_IDENTIFIED' AND to_status = 'ACTION_PLANNED' AND "
            "reason = 'action_created') OR "
            "(from_status = 'ACTION_PLANNED' AND to_status = 'RESOLVED' AND "
            "reason = 'actions_completed') OR "
            "(from_status = 'RESOLVED' AND to_status = 'VERIFIED' AND "
            "reason = 'verification_linked' AND verification_reference IS NOT NULL) OR "
            "(from_status IN ('CREATED', 'REVIEWED', 'ROOT_CAUSE_IDENTIFIED', "
            "'ACTION_PLANNED') AND to_status = 'DISMISSED' AND "
            "reason = 'case_dismissed') OR "
            "(from_status IN ('CREATED', 'REVIEWED') AND to_status = 'DUPLICATE' AND "
            "reason = 'duplicate_linked') OR "
            "(to_status = 'REVIEWED' AND from_status IN ('RESOLVED', 'VERIFIED', "
            "'DISMISSED', 'DUPLICATE') AND reason = 'case_reopened')",
            name="ck_bad_case_transitions_reason_compatibility",
        ),
        sa.CheckConstraint(
            "(to_status = 'VERIFIED' AND verification_reference IS NOT NULL) OR "
            "(to_status != 'VERIFIED' AND verification_reference IS NULL)",
            name="ck_bad_case_transitions_verification",
        ),
        sa.UniqueConstraint(
            "bad_case_id", "new_revision", name="uq_bad_case_transition_revision"
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id", "bad_case_id"],
            ["bad_case_analyses.id", "bad_case_analyses.bad_case_id"],
            name="fk_bad_case_transitions_analysis_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["action_id", "bad_case_id"],
            ["resolution_actions.id", "resolution_actions.bad_case_id"],
            name="fk_bad_case_transitions_action_owner",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_bad_case_transitions_case_id", "bad_case_transitions", ["bad_case_id"])


def downgrade() -> None:
    op.drop_index("ix_bad_case_transitions_case_id", table_name="bad_case_transitions")
    op.drop_table("bad_case_transitions")
    op.drop_index("ix_resolution_actions_case_id", table_name="resolution_actions")
    op.drop_table("resolution_actions")
    op.drop_index("ix_bad_case_analyses_case_id", table_name="bad_case_analyses")
    op.drop_table("bad_case_analyses")
    op.drop_index(
        "ix_feedback_evidence_links_case_id", table_name="feedback_evidence_links"
    )
    op.drop_table("feedback_evidence_links")
    op.drop_index("ix_bad_case_source_links_case_id", table_name="bad_case_source_links")
    op.drop_table("bad_case_source_links")
    op.drop_index("ix_bad_cases_created_at", table_name="bad_cases")
    op.drop_index("ix_bad_cases_symptom_code", table_name="bad_cases")
    op.drop_index("ix_bad_cases_severity", table_name="bad_cases")
    op.drop_index("ix_bad_cases_status", table_name="bad_cases")
    op.drop_index("ix_bad_cases_historical_candidate_id", table_name="bad_cases")
    op.drop_index("ix_bad_cases_historical_job_id", table_name="bad_cases")
    op.drop_index("ix_bad_cases_explanation_run_id", table_name="bad_cases")
    op.drop_index("ix_bad_cases_match_result_id", table_name="bad_cases")
    op.drop_index("ix_bad_cases_match_run_id", table_name="bad_cases")
    op.drop_table("bad_cases")
    op.drop_index("ix_system_signals_created_at", table_name="system_signals")
    op.drop_index("ix_system_signals_explanation_run_id", table_name="system_signals")
    op.drop_index("ix_system_signals_match_run_id", table_name="system_signals")
    op.drop_table("system_signals")
    op.drop_index("ix_feedback_records_created_at", table_name="feedback_records")
    op.drop_index("ix_feedback_records_type", table_name="feedback_records")
    op.drop_index("ix_feedback_records_explanation_run_id", table_name="feedback_records")
    op.drop_index("ix_feedback_records_match_run_id", table_name="feedback_records")
    op.drop_table("feedback_records")
