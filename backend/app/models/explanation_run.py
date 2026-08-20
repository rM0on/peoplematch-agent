from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.match_run import MatchResultModel, MatchRunModel


class ExplanationRunModel(Base):
    __tablename__ = "explanation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_explanation_runs_status",
        ),
        CheckConstraint(
            "requested_top_k BETWEEN 1 AND 10",
            name="ck_explanation_runs_requested_top_k",
        ),
        CheckConstraint(
            "effective_top_k IS NULL OR "
            "(effective_top_k BETWEEN 1 AND 10 AND effective_top_k <= requested_top_k)",
            name="ck_explanation_runs_effective_top_k",
        ),
        CheckConstraint(
            "attempt_count BETWEEN 0 AND 2",
            name="ck_explanation_runs_attempt_count",
        ),
        CheckConstraint(
            "explanation_count BETWEEN 0 AND 10",
            name="ck_explanation_runs_explanation_count",
        ),
        CheckConstraint(
            "NOT repaired OR attempt_count >= 2",
            name="ck_explanation_runs_repaired_attempts",
        ),
        CheckConstraint(
            "(evidence_bundle_version IS NULL AND "
            "evidence_bundle_fingerprint IS NULL AND evidence_bundle_json IS NULL) OR "
            "(evidence_bundle_version IS NOT NULL AND "
            "evidence_bundle_fingerprint IS NOT NULL AND evidence_bundle_json IS NOT NULL)",
            name="ck_explanation_runs_evidence_bundle_group",
        ),
        CheckConstraint(
            "(provider_evidence_version IS NULL AND "
            "provider_evidence_fingerprint IS NULL AND provider_evidence_json IS NULL) OR "
            "(provider_evidence_version IS NOT NULL AND "
            "provider_evidence_fingerprint IS NOT NULL AND provider_evidence_json IS NOT NULL)",
            name="ck_explanation_runs_provider_evidence_group",
        ),
        CheckConstraint(
            "(prompt_version IS NULL AND prompt_fingerprint IS NULL) OR "
            "(prompt_version IS NOT NULL AND prompt_fingerprint IS NOT NULL)",
            name="ck_explanation_runs_prompt_group",
        ),
        CheckConstraint(
            "status != 'RUNNING' OR "
            "(completed_at IS NULL AND error_code IS NULL AND "
            "error_detail_safe IS NULL AND explanation_count = 0 AND "
            "result_fingerprint IS NULL)",
            name="ck_explanation_runs_running_state",
        ),
        CheckConstraint(
            "status != 'FAILED' OR "
            "(completed_at IS NOT NULL AND error_code IS NOT NULL AND "
            "error_detail_safe IS NOT NULL AND explanation_count = 0 AND "
            "result_fingerprint IS NULL)",
            name="ck_explanation_runs_failed_state",
        ),
        CheckConstraint(
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
        Index("ix_explanation_runs_match_run_id", "match_run_id"),
        Index("ix_explanation_runs_status", "status"),
        Index("ix_explanation_runs_created_at", "created_at"),
    )

    explanation_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    match_run_id: Mapped[str] = mapped_column(
        ForeignKey(
            "match_runs.run_id",
            name="fk_explanation_runs_match_run_id_match_runs",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_top_k: Mapped[Optional[int]] = mapped_column(Integer)
    explanation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    evidence_bundle_version: Mapped[Optional[str]] = mapped_column(String(64))
    evidence_bundle_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    evidence_bundle_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, deferred=True, deferred_raiseload=True
    )
    provider_evidence_version: Mapped[Optional[str]] = mapped_column(String(64))
    provider_evidence_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    provider_evidence_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, deferred=True, deferred_raiseload=True
    )
    output_schema_version: Mapped[Optional[str]] = mapped_column(String(64))
    provider_kind: Mapped[Optional[str]] = mapped_column(String(40))
    provider_name: Mapped[Optional[str]] = mapped_column(String(80))
    configured_model: Mapped[Optional[str]] = mapped_column(String(160))
    observed_model: Mapped[Optional[str]] = mapped_column(String(160))
    provider_configuration_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64)
    )
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64))
    prompt_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    repaired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    result_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    error_code: Mapped[Optional[str]] = mapped_column(String(80))
    error_detail_safe: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    match_run: Mapped[MatchRunModel] = relationship(lazy="raise")
    explanations: Mapped[List["MatchExplanationModel"]] = relationship(
        back_populates="run",
        order_by="MatchExplanationModel.result_rank",
        lazy="raise",
    )


class MatchExplanationModel(Base):
    __tablename__ = "match_explanations"
    __table_args__ = (
        UniqueConstraint(
            "explanation_run_id",
            "candidate_id",
            name="uq_match_explanations_candidate",
        ),
        UniqueConstraint(
            "explanation_run_id",
            "result_rank",
            name="uq_match_explanations_rank",
        ),
        UniqueConstraint(
            "explanation_run_id",
            "match_result_id",
            name="uq_match_explanations_match_result",
        ),
        CheckConstraint(
            "result_rank >= 1", name="ck_match_explanations_result_rank"
        ),
        Index("ix_match_explanations_match_result_id", "match_result_id"),
        Index("ix_match_explanations_candidate_id", "candidate_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    explanation_run_id: Mapped[str] = mapped_column(
        ForeignKey(
            "explanation_runs.explanation_run_id",
            name="fk_match_explanations_explanation_run_id_explanation_runs",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    match_result_id: Mapped[int] = mapped_column(
        ForeignKey(
            "match_results.id",
            name="fk_match_explanations_match_result_id_match_results",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False)
    result_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    validated_output_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    candidate_output_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped[ExplanationRunModel] = relationship(
        back_populates="explanations", lazy="raise"
    )
    match_result: Mapped[MatchResultModel] = relationship(lazy="raise")
