from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from app.schemas.candidate import (
    CandidateLocationPreference,
    OverclaimRisk,
    Project,
    ProjectEvidence,
    SkillClaim,
    WorkStyle,
)
from app.schemas.job import JobLocation, JobRequirement
from app.schemas.shared import ContractModel, ProductStage, Seniority


class CandidateCreate(ContractModel):
    name: str = Field(min_length=3, max_length=80)
    raw_text: str = Field(min_length=40, max_length=5000)
    skills: List[SkillClaim] = Field(min_length=1)
    projects: List[Project] = Field(min_length=1)
    project_evidence: List[ProjectEvidence]
    github_url: Optional[str] = None
    ai_tools: List[str]
    target_roles: List[str] = Field(min_length=1)
    preferred_locations: CandidateLocationPreference
    seniority: Seniority
    work_style: WorkStyle
    missing_fields: List[str]
    overclaim_risk: OverclaimRisk


class CandidatePatch(ContractModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=80)
    raw_text: Optional[str] = Field(default=None, min_length=40, max_length=5000)
    skills: Optional[List[SkillClaim]] = None
    projects: Optional[List[Project]] = None
    project_evidence: Optional[List[ProjectEvidence]] = None
    github_url: Optional[str] = None
    ai_tools: Optional[List[str]] = None
    target_roles: Optional[List[str]] = None
    preferred_locations: Optional[CandidateLocationPreference] = None
    seniority: Optional[Seniority] = None
    work_style: Optional[WorkStyle] = None
    missing_fields: Optional[List[str]] = None
    overclaim_risk: Optional[OverclaimRisk] = None


class JobCreate(ContractModel):
    company_name: str = Field(min_length=3, max_length=100)
    role_title: str = Field(min_length=3, max_length=120)
    raw_jd: str = Field(min_length=60, max_length=6000)
    must_have: List[JobRequirement] = Field(min_length=1)
    nice_to_have: List[JobRequirement]
    role_direction: List[str] = Field(min_length=1)
    team_tags: List[str] = Field(min_length=1)
    location: JobLocation
    seniority_requirement: List[Seniority] = Field(min_length=1)
    product_stage: ProductStage
    evaluation_focus: List[str] = Field(min_length=1)


class JobPatch(ContractModel):
    company_name: Optional[str] = Field(default=None, min_length=3, max_length=100)
    role_title: Optional[str] = Field(default=None, min_length=3, max_length=120)
    raw_jd: Optional[str] = Field(default=None, min_length=60, max_length=6000)
    must_have: Optional[List[JobRequirement]] = None
    nice_to_have: Optional[List[JobRequirement]] = None
    role_direction: Optional[List[str]] = None
    team_tags: Optional[List[str]] = None
    location: Optional[JobLocation] = None
    seniority_requirement: Optional[List[Seniority]] = None
    product_stage: Optional[ProductStage] = None
    evaluation_focus: Optional[List[str]] = None
