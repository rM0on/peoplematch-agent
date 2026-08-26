from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


_BAD_CASE_CATEGORIES = (
    "'wrong_top1', 'ranking_inversion', 'false_positive', 'false_negative', "
    "'constraint_conflict', 'uncertain_order', 'expected_candidate_not_recalled', "
    "'irrelevant_candidate_recalled', 'filter_exclusion_disagreement', "
    "'pool_truncation_concern', 'missing_support', 'incorrect_support_status', "
    "'project_skill_link_disagreement', 'requirement_coverage_disagreement', "
    "'unsupported_explanation', 'misleading_explanation', 'incomplete_explanation', "
    "'incorrect_gap_statement', 'incorrect_top1_comparison', "
    "'candidate_snapshot_issue', 'job_snapshot_issue', 'requirement_issue', "
    "'constraint_issue', 'history_integrity_failure', 'ownership_failure', "
    "'lifecycle_failure', 'provider_attempt_failure'"
)
_BAD_CASE_STATUSES = (
    "'CREATED', 'REVIEWED', 'ROOT_CAUSE_IDENTIFIED', 'ACTION_PLANNED', "
    "'RESOLVED', 'VERIFIED', 'DISMISSED', 'DUPLICATE'"
)
_ROOT_CAUSE_CODES = (
    "'ranking_wrong_top1', 'ranking_pairwise_inversion', 'ranking_false_positive', "
    "'ranking_false_negative', 'ranking_tie_break_issue', "
    "'ranking_constraint_policy_issue', 'retrieval_recall_miss', "
    "'retrieval_filter_exclusion', 'retrieval_dense_coverage_gap', "
    "'retrieval_sparse_coverage_gap', 'retrieval_fusion_issue', "
    "'retrieval_pool_truncation', 'retrieval_index_integrity', "
    "'feature_semantic_score_issue', 'feature_sparse_score_issue', "
    "'feature_skill_fit_issue', 'feature_project_evidence_issue', "
    "'feature_role_direction_issue', 'feature_location_issue', "
    "'feature_seniority_issue', 'feature_missing_penalty_issue', "
    "'feature_overclaim_penalty_issue', 'feature_availability_issue', "
    "'evidence_missing_project_support', 'evidence_status_incorrect', "
    "'evidence_skill_project_link_incorrect', "
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
    "'integrity_terminal_overwrite', 'integrity_attempt_audit'"
)
_ACTION_TYPES = (
    "'data_correction_proposal', 'retrieval_change_hypothesis', "
    "'filter_policy_hypothesis', 'fusion_policy_hypothesis', "
    "'pool_policy_hypothesis', 'feature_rule_hypothesis', "
    "'feature_contract_hypothesis', 'ranking_change_hypothesis', "
    "'ranking_contract_hypothesis', 'constraint_policy_hypothesis', "
    "'data_integrity_action', 'evidence_rule_hypothesis', "
    "'evidence_integrity_action', 'planning_policy_hypothesis', "
    "'template_change_hypothesis', 'grounding_integrity_action', "
    "'integrity_repair_action', 'documentation_action', 'no_change'"
)
_TRANSITION_REASONS = (
    "'review_completed', 'root_cause_supported', 'action_created', "
    "'actions_completed', 'verification_linked', 'case_dismissed', "
    "'duplicate_linked', 'case_reopened'"
)


class BadCaseModel(Base):
    __tablename__ = "bad_cases"
    __table_args__ = (
        CheckConstraint(
            "case_contract_version = 'bad_case_v1'",
            name="ck_bad_cases_contract_version",
        ),
        CheckConstraint(
            "taxonomy_version = 'bad_case_taxonomy_v1'",
            name="ck_bad_cases_taxonomy_version",
        ),
        CheckConstraint(
            f"symptom_code IN ({_BAD_CASE_CATEGORIES})",
            name="ck_bad_cases_category",
        ),
        CheckConstraint(
            "symptom_family IN ('RANKING', 'RETRIEVAL', 'EVIDENCE', "
            "'EXPLANATION', 'DATA_QUALITY', 'INTEGRITY_OPERATIONS')",
            name="ck_bad_cases_symptom_family",
        ),
        CheckConstraint(
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
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_bad_cases_severity",
        ),
        CheckConstraint(
            f"status IN ({_BAD_CASE_STATUSES})", name="ck_bad_cases_status"
        ),
        CheckConstraint("revision >= 0", name="ck_bad_cases_revision"),
        CheckConstraint(
            "result_rank IS NULL OR result_rank >= 1",
            name="ck_bad_cases_result_rank",
        ),
        CheckConstraint(
            "(status = 'DUPLICATE' AND duplicate_of_bad_case_id IS NOT NULL) OR "
            "(status != 'DUPLICATE' AND duplicate_of_bad_case_id IS NULL)",
            name="ck_bad_cases_duplicate_owner",
        ),
        CheckConstraint(
            "related_case_id IS NULL OR (related_case_id != bad_case_id AND "
            "related_case_id IS DISTINCT FROM duplicate_of_bad_case_id)",
            name="ck_bad_cases_related_owner",
        ),
        Index("ix_bad_cases_match_run_id", "primary_match_run_id"),
        Index("ix_bad_cases_match_result_id", "primary_match_result_id"),
        Index("ix_bad_cases_explanation_run_id", "primary_explanation_run_id"),
        Index("ix_bad_cases_historical_job_id", "historical_job_id"),
        Index("ix_bad_cases_historical_candidate_id", "historical_candidate_id"),
        Index("ix_bad_cases_status", "status"),
        Index("ix_bad_cases_severity", "severity"),
        Index("ix_bad_cases_symptom_code", "symptom_code"),
        Index("ix_bad_cases_created_at", "created_at"),
    )

    bad_case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_match_run_id: Mapped[str] = mapped_column(
        ForeignKey("match_runs.run_id", ondelete="RESTRICT"), nullable=False
    )
    primary_match_result_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("match_results.id", ondelete="RESTRICT")
    )
    historical_job_id: Mapped[str] = mapped_column(String(80), nullable=False)
    historical_candidate_id: Mapped[Optional[str]] = mapped_column(String(80))
    result_rank: Mapped[Optional[int]] = mapped_column(Integer)
    primary_explanation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("explanation_runs.explanation_run_id", ondelete="RESTRICT")
    )
    primary_match_explanation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("match_explanations.id", ondelete="RESTRICT")
    )
    symptom_code: Mapped[str] = mapped_column(String(64), nullable=False)
    symptom_family: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    duplicate_of_bad_case_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT")
    )
    related_case_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    sources: Mapped[List["BadCaseSourceLinkModel"]] = relationship(
        back_populates="bad_case",
        order_by="BadCaseSourceLinkModel.id",
        lazy="raise",
    )
    evidence_links: Mapped[List["FeedbackEvidenceLinkModel"]] = relationship(
        back_populates="bad_case",
        order_by="FeedbackEvidenceLinkModel.id",
        lazy="raise",
    )
    analyses: Mapped[List["BadCaseAnalysisModel"]] = relationship(
        back_populates="bad_case",
        order_by="BadCaseAnalysisModel.revision_number",
        lazy="raise",
    )
    resolution_actions: Mapped[List["ResolutionActionModel"]] = relationship(
        back_populates="bad_case",
        order_by="ResolutionActionModel.id",
        lazy="raise",
    )
    transitions: Mapped[List["BadCaseTransitionModel"]] = relationship(
        back_populates="bad_case",
        order_by="BadCaseTransitionModel.id",
        lazy="raise",
    )


class BadCaseSourceLinkModel(Base):
    __tablename__ = "bad_case_source_links"
    __table_args__ = (
        CheckConstraint(
            "(feedback_id IS NOT NULL AND system_signal_id IS NULL) OR "
            "(feedback_id IS NULL AND system_signal_id IS NOT NULL)",
            name="ck_bad_case_source_exactly_one",
        ),
        UniqueConstraint("bad_case_id", "feedback_id", name="uq_bad_case_feedback"),
        UniqueConstraint(
            "bad_case_id", "system_signal_id", name="uq_bad_case_system_signal"
        ),
        Index("ix_bad_case_source_links_case_id", "bad_case_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bad_case_id: Mapped[str] = mapped_column(
        ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"), nullable=False
    )
    feedback_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("feedback_records.feedback_id", ondelete="RESTRICT")
    )
    system_signal_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("system_signals.signal_id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bad_case: Mapped[BadCaseModel] = relationship(back_populates="sources")


class FeedbackEvidenceLinkModel(Base):
    __tablename__ = "feedback_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "(evidence_reference IS NOT NULL AND field_locator IS NULL) OR "
            "(evidence_reference IS NULL AND field_locator IS NOT NULL)",
            name="ck_feedback_evidence_link_exactly_one",
        ),
        CheckConstraint(
            "purpose IN ('supports_observation', 'disputed_reference', "
            "'missing_expected_evidence')",
            name="ck_feedback_evidence_links_purpose",
        ),
        CheckConstraint(
            "result_rank IS NULL OR result_rank >= 1",
            name="ck_feedback_evidence_links_rank",
        ),
        CheckConstraint(
            "evidence_kind IS NULL OR evidence_kind IN ('job_requirement', 'skill', "
            "'project', 'project_evidence', 'retrieval', 'feature', 'ranking', "
            "'diagnostic', 'comparison')",
            name="ck_feedback_evidence_links_kind",
        ),
        CheckConstraint(
            "field_locator IS NULL OR field_locator IN ('candidate.skills', "
            "'candidate.project_evidence', 'candidate.seniority', "
            "'candidate.location', 'candidate.role_direction', 'job.requirements', "
            "'job.requirement_priority', 'job.seniority', 'job.location', "
            "'job.expectations')",
            name="ck_feedback_evidence_links_field_locator",
        ),
        CheckConstraint(
            "(evidence_reference IS NOT NULL AND explanation_run_id IS NOT NULL AND "
            "evidence_kind IS NOT NULL AND ((candidate_id IS NULL AND result_rank IS NULL) OR "
            "(candidate_id IS NOT NULL AND result_rank IS NOT NULL))) OR "
            "(field_locator IS NOT NULL AND explanation_run_id IS NULL AND "
            "evidence_kind IS NULL AND ((field_locator LIKE 'candidate.%' AND "
            "candidate_id IS NOT NULL AND result_rank IS NOT NULL) OR "
            "(field_locator LIKE 'job.%' AND candidate_id IS NULL AND result_rank IS NULL)))",
            name="ck_feedback_evidence_links_owner",
        ),
        UniqueConstraint(
            "bad_case_id",
            "explanation_run_id",
            "evidence_reference",
            "purpose",
            name="uq_feedback_evidence_reference",
        ),
        UniqueConstraint(
            "bad_case_id",
            "field_locator",
            "purpose",
            name="uq_feedback_field_locator",
        ),
        UniqueConstraint(
            "id", "bad_case_id", name="uq_feedback_evidence_link_owner"
        ),
        CheckConstraint(
            "(field_locator IS NOT NULL AND purpose = 'missing_expected_evidence') OR "
            "(evidence_reference IS NOT NULL AND purpose IN ("
            "'supports_observation', 'disputed_reference'))",
            name="ck_feedback_evidence_links_purpose_shape",
        ),
        CheckConstraint(
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
        Index("ix_feedback_evidence_links_case_id", "bad_case_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bad_case_id: Mapped[str] = mapped_column(
        ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"), nullable=False
    )
    explanation_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("explanation_runs.explanation_run_id", ondelete="RESTRICT")
    )
    evidence_reference: Mapped[Optional[str]] = mapped_column(String(200))
    field_locator: Mapped[Optional[str]] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_kind: Mapped[Optional[str]] = mapped_column(String(64))
    candidate_id: Mapped[Optional[str]] = mapped_column(String(80))
    result_rank: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bad_case: Mapped[BadCaseModel] = relationship(back_populates="evidence_links")


class BadCaseAnalysisModel(Base):
    __tablename__ = "bad_case_analyses"
    __table_args__ = (
        UniqueConstraint(
            "bad_case_id", "revision_number", name="uq_bad_case_analysis_revision"
        ),
        UniqueConstraint("id", "bad_case_id", name="uq_bad_case_analysis_owner"),
        ForeignKeyConstraint(
            ["supporting_evidence_link_id", "bad_case_id"],
            ["feedback_evidence_links.id", "feedback_evidence_links.bad_case_id"],
            name="fk_bad_case_analyses_support_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "revision_number >= 1", name="ck_bad_case_analyses_revision"
        ),
        CheckConstraint(
            "assessment IN ('suspected', 'supported', 'confirmed', 'rejected')",
            name="ck_bad_case_analyses_assessment",
        ),
        CheckConstraint(
            "root_cause_type IN ('ranking', 'retrieval', 'feature', 'evidence', "
            "'explanation', 'data_quality', 'integrity')",
            name="ck_bad_case_analyses_root_cause_type",
        ),
        CheckConstraint(
            f"root_cause_code IN ({_ROOT_CAUSE_CODES})",
            name="ck_bad_case_analyses_root_cause_code",
        ),
        CheckConstraint(
            "(root_cause_type = 'ranking' AND root_cause_code LIKE 'ranking_%') OR "
            "(root_cause_type = 'retrieval' AND root_cause_code LIKE 'retrieval_%') OR "
            "(root_cause_type = 'feature' AND root_cause_code LIKE 'feature_%') OR "
            "(root_cause_type = 'evidence' AND root_cause_code LIKE 'evidence_%') OR "
            "(root_cause_type = 'explanation' AND root_cause_code LIKE 'explanation_%') OR "
            "(root_cause_type = 'data_quality' AND root_cause_code LIKE 'data_%') OR "
            "(root_cause_type = 'integrity' AND root_cause_code LIKE 'integrity_%')",
            name="ck_bad_case_analyses_root_cause_compatibility",
        ),
        CheckConstraint(
            "assessment NOT IN ('supported', 'confirmed') OR "
            "supporting_evidence_link_id IS NOT NULL",
            name="ck_bad_case_analyses_support",
        ),
        Index("ix_bad_case_analyses_case_id", "bad_case_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bad_case_id: Mapped[str] = mapped_column(
        ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    assessment: Mapped[str] = mapped_column(String(16), nullable=False)
    root_cause_type: Mapped[str] = mapped_column(String(24), nullable=False)
    root_cause_code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    supporting_evidence_link_id: Mapped[Optional[int]] = mapped_column(
        BigInteger
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bad_case: Mapped[BadCaseModel] = relationship(back_populates="analyses")


class ResolutionActionModel(Base):
    __tablename__ = "resolution_actions"
    __table_args__ = (
        UniqueConstraint("id", "bad_case_id", name="uq_resolution_action_owner"),
        ForeignKeyConstraint(
            ["supersedes_action_id", "bad_case_id"],
            ["resolution_actions.id", "resolution_actions.bad_case_id"],
            name="fk_resolution_actions_supersedes_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"action_type IN ({_ACTION_TYPES})",
            name="ck_resolution_actions_action_type",
        ),
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'cancelled', "
            "'superseded')",
            name="ck_resolution_actions_status",
        ),
        CheckConstraint(
            "(status IN ('planned', 'in_progress') AND completed_at IS NULL) OR "
            "(status IN ('completed', 'cancelled', 'superseded') AND "
            "completed_at IS NOT NULL)",
            name="ck_resolution_actions_lifecycle",
        ),
        CheckConstraint(
            "supersedes_action_id IS NULL OR supersedes_action_id != id",
            name="ck_resolution_actions_self_supersession",
        ),
        Index("ix_resolution_actions_case_id", "bad_case_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bad_case_id: Mapped[str] = mapped_column(
        ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    supersedes_action_id: Mapped[Optional[int]] = mapped_column(
        BigInteger
    )
    safe_change_reference: Mapped[Optional[str]] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    bad_case: Mapped[BadCaseModel] = relationship(back_populates="resolution_actions")


class BadCaseTransitionModel(Base):
    __tablename__ = "bad_case_transitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["analysis_id", "bad_case_id"],
            ["bad_case_analyses.id", "bad_case_analyses.bad_case_id"],
            name="fk_bad_case_transitions_analysis_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["action_id", "bad_case_id"],
            ["resolution_actions.id", "resolution_actions.bad_case_id"],
            name="fk_bad_case_transitions_action_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"from_status IN ({_BAD_CASE_STATUSES}) AND "
            f"to_status IN ({_BAD_CASE_STATUSES})",
            name="ck_bad_case_transitions_status",
        ),
        CheckConstraint(
            "new_revision = previous_revision + 1",
            name="ck_bad_case_transitions_revision",
        ),
        CheckConstraint(
            "from_status != to_status",
            name="ck_bad_case_transitions_status_change",
        ),
        CheckConstraint(
            f"reason IN ({_TRANSITION_REASONS})",
            name="ck_bad_case_transitions_reason",
        ),
        CheckConstraint(
            "origin IN ('manual_review', 'system_rule')",
            name="ck_bad_case_transitions_origin",
        ),
        CheckConstraint(
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
        CheckConstraint(
            "(to_status = 'VERIFIED' AND verification_reference IS NOT NULL) OR "
            "(to_status != 'VERIFIED' AND verification_reference IS NULL)",
            name="ck_bad_case_transitions_verification",
        ),
        UniqueConstraint(
            "bad_case_id", "new_revision", name="uq_bad_case_transition_revision"
        ),
        Index("ix_bad_case_transitions_case_id", "bad_case_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bad_case_id: Mapped[str] = mapped_column(
        ForeignKey("bad_cases.bad_case_id", ondelete="RESTRICT"), nullable=False
    )
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    origin: Mapped[str] = mapped_column(String(24), nullable=False)
    analysis_id: Mapped[Optional[int]] = mapped_column(
        BigInteger
    )
    action_id: Mapped[Optional[int]] = mapped_column(
        BigInteger
    )
    previous_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    new_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    verification_reference: Mapped[Optional[str]] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bad_case: Mapped[BadCaseModel] = relationship(back_populates="transitions")


__all__ = [
    "BadCaseAnalysisModel",
    "BadCaseModel",
    "BadCaseSourceLinkModel",
    "BadCaseTransitionModel",
    "FeedbackEvidenceLinkModel",
    "ResolutionActionModel",
]
