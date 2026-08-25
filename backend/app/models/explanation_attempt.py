from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExplanationGenerationAttemptModel(Base):
    __tablename__ = "explanation_generation_attempts"
    __table_args__ = (
        UniqueConstraint(
            "explanation_run_id",
            "attempt_number",
            name="uq_explanation_attempts_run_number",
        ),
        CheckConstraint(
            "attempt_number BETWEEN 1 AND 2",
            name="ck_explanation_attempts_number",
        ),
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_explanation_attempts_status",
        ),
        CheckConstraint(
            "error_category IS NULL OR error_category IN ("
            "'provider_timeout', 'provider_transport', 'provider_http_status', "
            "'malformed_response', 'invalid_output', 'grounding_failure', "
            "'provider_configuration', 'internal_error')",
            name="ck_explanation_attempts_error_category",
        ),
        CheckConstraint(
            "(status = 'RUNNING' AND completed_at IS NULL AND error_category IS NULL) OR "
            "(status = 'COMPLETED' AND completed_at IS NOT NULL AND error_category IS NULL) OR "
            "(status = 'FAILED' AND completed_at IS NOT NULL AND error_category IS NOT NULL)",
            name="ck_explanation_attempts_lifecycle",
        ),
        Index(
            "ix_explanation_attempts_run_id",
            "explanation_run_id",
        ),
        Index("ix_explanation_attempts_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    explanation_run_id: Mapped[str] = mapped_column(
        ForeignKey(
            "explanation_runs.explanation_run_id",
            name="fk_explanation_attempts_explanation_run_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_category: Mapped[Optional[str]] = mapped_column(String(40))
    provider_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    configured_model: Mapped[str] = mapped_column(String(160), nullable=False)
    observed_model: Mapped[Optional[str]] = mapped_column(String(160))
    provider_configuration_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


__all__ = ["ExplanationGenerationAttemptModel"]
