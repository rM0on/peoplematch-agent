from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RecruiterNarrativeModel(Base):
    """Append-only presentation artifact derived from one validated explanation."""

    __tablename__ = "recruiter_narratives"
    __table_args__ = (
        CheckConstraint("status IN ('COMPLETED', 'FAILED')", name="ck_recruiter_narratives_status"),
        CheckConstraint(
            "(status = 'COMPLETED' AND validation_status = 'PASSED' AND "
            "validated_content_json IS NOT NULL AND content_fingerprint IS NOT NULL AND error_code IS NULL) OR "
            "(status = 'FAILED' AND validation_status = 'FAILED' AND "
            "validated_content_json IS NULL AND content_fingerprint IS NULL AND error_code IS NOT NULL)",
            name="ck_recruiter_narratives_content_state",
        ),
        Index("ix_recruiter_narratives_source_explanation_id", "source_explanation_id"),
    )

    narrative_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    explanation_run_id: Mapped[str] = mapped_column(
        ForeignKey("explanation_runs.explanation_run_id", ondelete="RESTRICT"), nullable=False
    )
    source_explanation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("match_explanations.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False)
    result_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    source_output_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_bundle_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ranking_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False)
    validated_content_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    content_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    error_code: Mapped[Optional[str]] = mapped_column(String(48))
    provider_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    configured_model: Mapped[str] = mapped_column(String(160), nullable=False)
    observed_model: Mapped[Optional[str]] = mapped_column(String(160))
    provider_configuration_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["RecruiterNarrativeModel"]
