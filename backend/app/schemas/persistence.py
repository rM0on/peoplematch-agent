from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import AnyHttpUrl, TypeAdapter, ValidationError, model_validator

from app.schemas.candidate import (
    CandidateArchetype,
    CandidateLocationPreference,
    CandidateProfile,
    OverclaimRisk,
    Project,
    ProjectEvidence,
    SkillClaim,
    WorkStyle,
)
from app.schemas.job import JobArchetype, JobLocation, JobProfile, JobRequirement
from app.schemas.shared import ContractModel, ProductStage, SchemaVersion, Seniority


class DataOrigin(str, Enum):
    SYNTHETIC_SANDBOX = "synthetic_sandbox"
    USER_CREATED = "user_created"
    LLM_PARSED = "llm_parsed"


class CandidateRecord(ContractModel):
    candidate_id: str
    name: str
    archetype: Optional[CandidateArchetype] = None
    raw_text: str
    skills: List[SkillClaim]
    projects: List[Project]
    project_evidence: List[ProjectEvidence]
    github_url: Optional[str] = None
    ai_tools: List[str]
    target_roles: List[str]
    preferred_locations: CandidateLocationPreference
    seniority: Seniority
    work_style: WorkStyle
    missing_fields: List[str]
    overclaim_risk: OverclaimRisk
    data_origin: DataOrigin
    schema_version: SchemaVersion = "1.0"
    dataset_version: Optional[str] = None

    @model_validator(mode="after")
    def nested_references_must_be_valid(self) -> "CandidateRecord":
        if self.github_url is not None:
            if self.data_origin == DataOrigin.SYNTHETIC_SANDBOX:
                if not self.github_url.startswith("sandbox://"):
                    try:
                        parsed_url = TypeAdapter(AnyHttpUrl).validate_python(
                            self.github_url
                        )
                    except ValidationError as exc:
                        raise ValueError(
                            "github_url must be a synthetic reference"
                        ) from exc
                    if parsed_url.host != "example.invalid":
                        raise ValueError("github_url must be a synthetic reference")
            else:
                try:
                    TypeAdapter(AnyHttpUrl).validate_python(self.github_url)
                except ValidationError as exc:
                    raise ValueError(
                        "github_url must be a valid http or https URL"
                    ) from exc
        project_ids = [project.project_id for project in self.projects]
        evidence_ids = [evidence.evidence_id for evidence in self.project_evidence]
        if len(set(project_ids)) != len(project_ids):
            raise ValueError("project_id values must be unique within a candidate")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence_id values must be unique within a candidate")
        claimed_skills = {skill.name for skill in self.skills}
        for evidence in self.project_evidence:
            if evidence.project_id not in set(project_ids):
                raise ValueError(f"evidence {evidence.evidence_id} references unknown project_id")
            if not set(evidence.supports_skills) <= claimed_skills:
                raise ValueError(f"evidence {evidence.evidence_id} supports unclaimed skills")
        return self

    def to_canonical_profile(self) -> CandidateProfile:
        if self.data_origin != DataOrigin.SYNTHETIC_SANDBOX or self.archetype is None:
            raise ValueError("only frozen sandbox records have a Phase 1 canonical profile")
        payload = self.model_dump(exclude={"dataset_version"})
        payload["data_origin"] = "synthetic_sandbox"
        return CandidateProfile.model_validate(payload)


class JobRecord(ContractModel):
    job_id: str
    company_name: str
    role_title: str
    archetype: Optional[JobArchetype] = None
    raw_jd: str
    must_have: List[JobRequirement]
    nice_to_have: List[JobRequirement]
    role_direction: List[str]
    team_tags: List[str]
    location: JobLocation
    seniority_requirement: List[Seniority]
    product_stage: ProductStage
    evaluation_focus: List[str]
    data_origin: DataOrigin
    schema_version: SchemaVersion = "1.0"
    dataset_version: Optional[str] = None

    @model_validator(mode="after")
    def requirement_ids_must_be_unique(self) -> "JobRecord":
        ids = [requirement.requirement_id for requirement in [*self.must_have, *self.nice_to_have]]
        if len(set(ids)) != len(ids):
            raise ValueError("requirement_id values must be unique within a job")
        return self

    def to_canonical_profile(self) -> JobProfile:
        if self.data_origin != DataOrigin.SYNTHETIC_SANDBOX or self.archetype is None:
            raise ValueError("only frozen sandbox records have a Phase 1 canonical profile")
        payload = self.model_dump(exclude={"dataset_version"})
        payload["data_origin"] = "synthetic_sandbox"
        return JobProfile.model_validate(payload)
