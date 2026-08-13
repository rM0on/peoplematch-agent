from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class JobProfileModel(TimestampMixin, Base):
    __tablename__ = "job_profiles"
    __table_args__ = (
        Index("ix_job_profiles_role_title", "role_title"),
        Index("ix_job_profiles_data_origin", "data_origin"),
    )

    job_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_title: Mapped[str] = mapped_column(String(120), nullable=False)
    raw_jd: Mapped[str] = mapped_column(Text, nullable=False)
    product_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    dataset_version: Mapped[Optional[str]] = mapped_column(String(32))
    dataset_archetype: Mapped[Optional[str]] = mapped_column(String(80))
    role_direction: Mapped[List[str]] = mapped_column(ARRAY(String(120)), nullable=False)
    team_tags: Mapped[List[str]] = mapped_column(ARRAY(String(120)), nullable=False)
    seniority_requirement: Mapped[List[str]] = mapped_column(
        ARRAY(String(32)), nullable=False
    )
    evaluation_focus: Mapped[List[str]] = mapped_column(
        ARRAY(String(160)), nullable=False
    )
    location: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    requirements: Mapped[List["JobRequirementModel"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobRequirementModel.position",
        lazy="selectin",
    )


class JobRequirementModel(Base):
    __tablename__ = "job_requirements"
    __table_args__ = (UniqueConstraint("job_id", "requirement_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("job_profiles.job_id", ondelete="CASCADE"), nullable=False
    )
    requirement_id: Mapped[str] = mapped_column(String(100), nullable=False)
    requirement_group: Mapped[str] = mapped_column(String(24), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    text: Mapped[str] = mapped_column(String(240), nullable=False)
    evidence_expectation: Mapped[str] = mapped_column(String(300), nullable=False)

    job: Mapped[JobProfileModel] = relationship(back_populates="requirements")
