from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MatchRunModel(Base):
    __tablename__ = "match_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_match_runs_status",
        ),
        CheckConstraint(
            "ranking_variant IN ('ltr', 'cross_encoder_experiment')",
            name="ck_match_runs_ranking_variant",
        ),
        CheckConstraint("result_count >= 0", name="ck_match_runs_result_count"),
        Index("ix_match_runs_job_id", "job_id"),
        Index("ix_match_runs_status", "status"),
        Index("ix_match_runs_ranking_variant", "ranking_variant"),
        Index("ix_match_runs_created_at", "created_at"),
    )

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requested_job_id: Mapped[str] = mapped_column(String(80), nullable=False)
    job_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("job_profiles.job_id", ondelete="RESTRICT")
    )
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    ranking_variant: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    request_parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ranking_input_contract_version: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    ranking_input_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    ranking_input_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    retrieval_document_version: Mapped[Optional[str]] = mapped_column(String(64))
    retrieval_configuration_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64)
    )
    retrieval_provenance: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    feature_version: Mapped[Optional[str]] = mapped_column(String(64))
    feature_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    ranker_version: Mapped[Optional[str]] = mapped_column(String(64))
    ranker_model_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    ce_provenance: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    error_code: Mapped[Optional[str]] = mapped_column(String(80))
    error_detail_safe: Mapped[Optional[str]] = mapped_column(String(500))

    results: Mapped[List["MatchResultModel"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="MatchResultModel.result_rank",
        lazy="raise",
    )
    steps: Mapped[List["RunStepModel"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RunStepModel.sequence",
        lazy="raise",
    )


class MatchResultModel(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("run_id", "candidate_id", name="uq_match_results_candidate"),
        UniqueConstraint("run_id", "result_rank", name="uq_match_results_rank"),
        CheckConstraint("result_rank >= 1", name="ck_match_results_result_rank"),
        CheckConstraint("ltr_rank >= 1", name="ck_match_results_ltr_rank"),
        CheckConstraint(
            "cross_encoder_rank IS NULL OR cross_encoder_rank >= 1",
            name="ck_match_results_ce_rank",
        ),
        Index("ix_match_results_candidate_id", "candidate_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("match_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_profiles.candidate_id", ondelete="RESTRICT"),
        nullable=False,
    )
    result_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_input_contract_version: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    candidate_input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    retrieval_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_channels: Mapped[List[str]] = mapped_column(
        ARRAY(String(16)), nullable=False
    )
    dense_rank: Mapped[Optional[int]] = mapped_column(Integer)
    dense_score: Mapped[Optional[float]] = mapped_column(Float(53))
    sparse_rank: Mapped[Optional[int]] = mapped_column(Integer)
    sparse_score: Mapped[Optional[float]] = mapped_column(Float(53))
    fusion_score: Mapped[Optional[float]] = mapped_column(Float(53))
    semantic_score: Mapped[Optional[float]] = mapped_column(Float(53))
    skill_fit_score: Mapped[Optional[float]] = mapped_column(Float(53))
    project_evidence_score: Mapped[Optional[float]] = mapped_column(Float(53))
    role_direction_score: Mapped[Optional[float]] = mapped_column(Float(53))
    ai_tool_score: Mapped[Optional[float]] = mapped_column(Float(53))
    location_score: Mapped[Optional[float]] = mapped_column(Float(53))
    seniority_score: Mapped[Optional[float]] = mapped_column(Float(53))
    missing_penalty: Mapped[Optional[float]] = mapped_column(Float(53))
    overclaim_penalty: Mapped[Optional[float]] = mapped_column(Float(53))
    feature_diagnostics_contract_version: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    feature_diagnostics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ltr_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    ltr_score_raw: Mapped[float] = mapped_column(Float(53), nullable=False)
    cross_encoder_rank: Mapped[Optional[int]] = mapped_column(Integer)
    cross_encoder_score_raw: Mapped[Optional[float]] = mapped_column(Float(53))

    run: Mapped[MatchRunModel] = relationship(back_populates="results")


class RunStepModel(Base):
    __tablename__ = "run_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_run_steps_sequence"),
        CheckConstraint("sequence >= 1", name="ck_run_steps_sequence"),
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_run_steps_status",
        ),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_run_steps_duration"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("match_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[float]] = mapped_column(Float(53))
    input_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_refs: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(80))
    error_detail_safe: Mapped[Optional[str]] = mapped_column(String(500))

    run: Mapped[MatchRunModel] = relationship(back_populates="steps")
