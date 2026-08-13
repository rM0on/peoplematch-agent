from __future__ import annotations

from typing import Annotated, List, Optional

from pydantic import Field, StringConstraints, ValidationInfo, model_validator

from app.schemas.candidate import (
    CandidateLocationPreference,
    OverclaimRisk,
    Project,
    ProjectEvidence,
    SkillClaim,
    WorkStyle,
)
from app.schemas.job import JobLocation, JobRequirement
from app.schemas.persistence import CandidateRecord, DataOrigin, JobRecord
from app.schemas.shared import ContractModel, ProductStage, Seniority


class CandidateExtractionDraft(ContractModel):
    name: str = Field(min_length=3, max_length=80)
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

    @model_validator(mode="after")
    def reuse_candidate_domain_validation(
        self, info: ValidationInfo
    ) -> "CandidateExtractionDraft":
        context = info.context if isinstance(info.context, dict) else {}
        data_origin = context.get("data_origin", DataOrigin.MOCK_PARSED)
        CandidateRecord.model_validate(
            {
                "candidate_id": "cand_parse_validation",
                "raw_text": "Server-owned extraction validation source text placeholder.",
                **self.model_dump(mode="json"),
                "archetype": None,
                "data_origin": data_origin,
                "schema_version": "1.0",
                "dataset_version": None,
            }
        )
        return self


class JobExtractionDraft(ContractModel):
    company_name: str = Field(min_length=3, max_length=100)
    role_title: str = Field(min_length=3, max_length=120)
    must_have: List[JobRequirement] = Field(min_length=1)
    nice_to_have: List[JobRequirement]
    role_direction: List[str] = Field(min_length=1)
    team_tags: List[str] = Field(min_length=1)
    location: JobLocation
    seniority_requirement: List[Seniority] = Field(min_length=1)
    product_stage: ProductStage
    evaluation_focus: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def reuse_job_domain_validation(self) -> "JobExtractionDraft":
        JobRecord.model_validate(
            {
                "job_id": "job_parse_validation",
                "raw_jd": "Server-owned extraction validation source text placeholder for job descriptions.",
                **self.model_dump(mode="json"),
                "archetype": None,
                "data_origin": DataOrigin.MOCK_PARSED,
                "schema_version": "1.0",
                "dataset_version": None,
            }
        )
        return self


class CandidateParseRequest(ContractModel):
    text: Annotated[
        str,
        StringConstraints(strip_whitespace=False, min_length=40, max_length=5000),
    ]
    persist: bool = False


class JobParseRequest(ContractModel):
    text: Annotated[
        str,
        StringConstraints(strip_whitespace=False, min_length=60, max_length=6000),
    ]
    persist: bool = False


class ExtractionMetadata(ContractModel):
    provider: str
    provider_kind: str
    attempts: int = Field(ge=1)
    repaired: bool
    persisted: bool
    input_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class CandidateParseData(ContractModel):
    draft: CandidateExtractionDraft
    record: Optional[CandidateRecord] = None
    extraction: ExtractionMetadata


class JobParseData(ContractModel):
    draft: JobExtractionDraft
    record: Optional[JobRecord] = None
    extraction: ExtractionMetadata
