from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CandidateProfileModel(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (
        Index("ix_candidate_profiles_seniority", "seniority"),
        Index("ix_candidate_profiles_data_origin", "data_origin"),
    )

    candidate_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    github_url: Mapped[Optional[str]] = mapped_column(String(300))
    seniority: Mapped[str] = mapped_column(String(32), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    dataset_version: Mapped[Optional[str]] = mapped_column(String(32))
    dataset_archetype: Mapped[Optional[str]] = mapped_column(String(80))
    ai_tools: Mapped[List[str]] = mapped_column(ARRAY(String(120)), nullable=False)
    target_roles: Mapped[List[str]] = mapped_column(ARRAY(String(160)), nullable=False)
    missing_fields: Mapped[List[str]] = mapped_column(ARRAY(String(120)), nullable=False)
    preferred_locations: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    work_style: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    overclaim_risk: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    skills: Mapped[List["CandidateSkillModel"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateSkillModel.position",
        lazy="selectin",
    )
    projects: Mapped[List["CandidateProjectModel"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateProjectModel.position",
        lazy="selectin",
    )
    evidence: Mapped[List["CandidateProjectEvidenceModel"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateProjectEvidenceModel.position",
        lazy="selectin",
        overlaps="project,evidence",
    )


class CandidateSkillModel(Base):
    __tablename__ = "candidate_skills"
    __table_args__ = (UniqueConstraint("candidate_id", "name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_profiles.candidate_id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    self_reported_level: Mapped[Optional[str]] = mapped_column(String(32))

    candidate: Mapped[CandidateProfileModel] = relationship(back_populates="skills")


class CandidateProjectModel(Base):
    __tablename__ = "candidate_projects"
    __table_args__ = (UniqueConstraint("candidate_id", "project_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_profiles.candidate_id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    technologies: Mapped[List[str]] = mapped_column(ARRAY(String(120)), nullable=False)
    outcomes: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False)
    skills_demonstrated: Mapped[List[str]] = mapped_column(
        ARRAY(String(120)), nullable=False
    )

    candidate: Mapped[CandidateProfileModel] = relationship(back_populates="projects")
    evidence: Mapped[List["CandidateProjectEvidenceModel"]] = relationship(
        back_populates="project", overlaps="candidate,evidence"
    )


class CandidateProjectEvidenceModel(Base):
    __tablename__ = "candidate_project_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["candidate_id", "project_id"],
            ["candidate_projects.candidate_id", "candidate_projects.project_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("candidate_id", "evidence_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_profiles.candidate_id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[str] = mapped_column(String(100), nullable=False)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    supports_skills: Mapped[List[str]] = mapped_column(
        ARRAY(String(120)), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(48), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)

    candidate: Mapped[CandidateProfileModel] = relationship(
        back_populates="evidence", overlaps="evidence,project"
    )
    project: Mapped[CandidateProjectModel] = relationship(
        back_populates="evidence", overlaps="candidate,evidence"
    )
