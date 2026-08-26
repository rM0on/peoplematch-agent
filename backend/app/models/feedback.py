from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FeedbackRecordModel(Base):
    __tablename__ = "feedback_records"
    __table_args__ = (
        CheckConstraint(
            "contract_version = 'feedback_record_v1'",
            name="ck_feedback_records_contract_version",
        ),
        CheckConstraint(
            "feedback_type IN ('ranking', 'explanation', 'profile_data')",
            name="ck_feedback_records_type",
        ),
        CheckConstraint(
            "target_type IN ("
            "'overall_ranking', 'top1', 'candidate_result', 'pairwise', "
            "'summary', 'match_reason', 'risk', 'missing_requirement', "
            "'interview_question', 'top1_comparison', 'rewrite_operation', "
            "'candidate_profile', 'job_profile', 'expected_candidate')",
            name="ck_feedback_records_target_type",
        ),
        CheckConstraint("origin = 'human'", name="ck_feedback_records_origin"),
        CheckConstraint(
            "result_rank IS NULL OR result_rank >= 1",
            name="ck_feedback_records_result_rank",
        ),
        CheckConstraint(
            "comparison_result_rank IS NULL OR comparison_result_rank >= 1",
            name="ck_feedback_records_comparison_rank",
        ),
        CheckConstraint(
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
        CheckConstraint(
            "reason_code IS NULL OR reason_code IN ('wrong_top1', "
            "'ranking_inversion', 'false_positive', 'false_negative', "
            "'constraint_conflict', 'evidence_coverage_disagreement')",
            name="ck_feedback_records_reason_code",
        ),
        CheckConstraint(
            "field_locator IS NULL OR field_locator IN ('candidate.skills', "
            "'candidate.project_evidence', 'candidate.seniority', "
            "'candidate.location', 'candidate.role_direction', 'job.requirements', "
            "'job.requirement_priority', 'job.seniority', 'job.location', "
            "'job.expectations')",
            name="ck_feedback_records_field_locator",
        ),
        CheckConstraint(
            "expected_candidate_reference IS NULL OR "
            "expected_candidate_reference LIKE 'expected_candidate:%'",
            name="ck_feedback_records_expected_candidate_reference",
        ),
        CheckConstraint(
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
        CheckConstraint(
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
        CheckConstraint(
            "feedback_id != supersedes_feedback_id",
            name="ck_feedback_records_self_supersession",
        ),
        CheckConstraint(
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
        Index("ix_feedback_records_match_run_id", "match_run_id"),
        Index("ix_feedback_records_explanation_run_id", "explanation_run_id"),
        Index("ix_feedback_records_type", "feedback_type"),
        Index("ix_feedback_records_created_at", "created_at"),
    )

    feedback_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(24), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    match_run_id: Mapped[str] = mapped_column(
        ForeignKey("match_runs.run_id", ondelete="RESTRICT"), nullable=False
    )
    match_result_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("match_results.id", ondelete="RESTRICT")
    )
    comparison_match_result_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("match_results.id", ondelete="RESTRICT")
    )
    candidate_id: Mapped[Optional[str]] = mapped_column(String(80))
    comparison_candidate_id: Mapped[Optional[str]] = mapped_column(String(80))
    result_rank: Mapped[Optional[int]] = mapped_column(Integer)
    comparison_result_rank: Mapped[Optional[int]] = mapped_column(Integer)
    expected_candidate_reference: Mapped[Optional[str]] = mapped_column(String(160))
    job_id: Mapped[str] = mapped_column(String(80), nullable=False)
    explanation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("explanation_runs.explanation_run_id", ondelete="RESTRICT")
    )
    match_explanation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("match_explanations.id", ondelete="RESTRICT")
    )
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[Optional[str]] = mapped_column(String(80))
    field_locator: Mapped[Optional[str]] = mapped_column(String(80))
    evidence_reference: Mapped[Optional[str]] = mapped_column(String(200))
    comment: Mapped[Optional[str]] = mapped_column(String(500))
    supersedes_feedback_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("feedback_records.feedback_id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SystemSignalModel(Base):
    __tablename__ = "system_signals"
    __table_args__ = (
        UniqueConstraint(
            "match_run_id",
            "signal_code",
            "occurrence_identity",
            name="uq_system_signals_occurrence",
        ),
        CheckConstraint(
            "contract_version = 'system_signal_v1'",
            name="ck_system_signals_contract_version",
        ),
        CheckConstraint(
            "signal_code IN ("
            "'snapshot_fingerprint_mismatch', 'result_fingerprint_mismatch', "
            "'cross_owner_reference', 'terminal_lifecycle_violation', "
            "'explanation_grounding_failure', 'attempt_audit_mismatch')",
            name="ck_system_signals_code",
        ),
        CheckConstraint(
            "source_stage IN ('match_run', 'evidence', 'explanation', 'persistence')",
            name="ck_system_signals_source_stage",
        ),
        Index("ix_system_signals_match_run_id", "match_run_id"),
        Index("ix_system_signals_explanation_run_id", "explanation_run_id"),
        Index("ix_system_signals_created_at", "created_at"),
    )

    signal_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    match_run_id: Mapped[str] = mapped_column(
        ForeignKey("match_runs.run_id", ondelete="RESTRICT"), nullable=False
    )
    explanation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("explanation_runs.explanation_run_id", ondelete="RESTRICT")
    )
    signal_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    source_error_code: Mapped[Optional[str]] = mapped_column(String(80))
    occurrence_identity: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["FeedbackRecordModel", "SystemSignalModel"]
