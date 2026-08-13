from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.shared import (
    ContractModel,
    RemotePolicy,
    SchemaVersion,
    Seniority,
    SyntheticDataOrigin,
)


class CandidateArchetype(str, Enum):
    LLM_APPLICATION_AGENT_ENGINEER = "llm_application_agent_engineer"
    RECOMMENDATION_RANKING_ENGINEER = "recommendation_ranking_engineer"
    ML_INFRA_MLOPS_ENGINEER = "ml_infra_mlops_engineer"
    AI_PRODUCT_ENGINEER = "ai_product_engineer"
    RAG_SEARCH_ENGINEER = "rag_search_engineer"
    NLP_MODEL_ALGORITHM_ENGINEER = "nlp_model_algorithm_engineer"
    AI_SECURITY_ENGINEER = "ai_security_engineer"
    BACKEND_DISTRIBUTED_SYSTEMS_ENGINEER = "backend_distributed_systems_engineer"
    DATA_ENGINEER = "data_engineer"
    FRONTEND_AI_PRODUCT_ENGINEER = "frontend_ai_product_engineer"
    EARLY_CAREER_STRONG_PROJECT = "early_career_strong_project"
    OVERCLAIM_CANDIDATE = "overclaim_candidate"


class SkillCategory(str, Enum):
    LLM_APPLICATION = "llm_application"
    RECOMMENDATION = "recommendation"
    RETRIEVAL_SEARCH = "retrieval_search"
    ML_INFRA = "ml_infra"
    MODEL_ALGORITHM = "model_algorithm"
    SECURITY = "security"
    BACKEND = "backend"
    DATA = "data"
    FRONTEND = "frontend"
    PRODUCT_DELIVERY = "product_delivery"
    EVALUATION = "evaluation"
    AI_TOOLING = "ai_tooling"


class SelfReportedLevel(str, Enum):
    FAMILIAR = "familiar"
    PRACTICED = "practiced"
    ADVANCED = "advanced"


class SkillClaim(ContractModel):
    name: str = Field(min_length=2, max_length=80)
    category: SkillCategory
    self_reported_level: Optional[SelfReportedLevel] = None


class Project(ContractModel):
    project_id: str = Field(pattern=r"^prj_[a-z0-9_]+$")
    name: str = Field(min_length=3, max_length=120)
    summary: str = Field(min_length=20, max_length=600)
    role: str = Field(min_length=2, max_length=120)
    technologies: List[str] = Field(min_length=1)
    outcomes: List[str] = Field(min_length=1)
    skills_demonstrated: List[str] = Field(min_length=1)

    @field_validator("technologies", "outcomes", "skills_demonstrated")
    @classmethod
    def values_must_be_unique(cls, values: List[str]) -> List[str]:
        if len(set(values)) != len(values):
            raise ValueError("list values must be unique")
        return values


class EvidenceType(str, Enum):
    CODE = "code"
    TESTS = "tests"
    EVALUATION_REPORT = "evaluation_report"
    ARCHITECTURE_DOC = "architecture_doc"
    README = "readme"
    WORKFLOW_TRACE = "workflow_trace"
    DATASET = "dataset"
    DEMO = "demo"
    EXPERIMENT_REPORT = "experiment_report"


class VerificationStatus(str, Enum):
    AVAILABLE = "available"
    DESCRIBED = "described"
    MISSING = "missing"


class ProjectEvidence(ContractModel):
    evidence_id: str = Field(pattern=r"^ev_[a-z0-9_]+$")
    project_id: str = Field(pattern=r"^prj_[a-z0-9_]+$")
    supports_skills: List[str] = Field(min_length=1)
    evidence_type: EvidenceType
    statement: str = Field(min_length=20, max_length=500)
    artifact_ref: str = Field(min_length=12, max_length=300)
    verification_status: VerificationStatus

    @field_validator("artifact_ref")
    @classmethod
    def artifact_must_be_synthetic(cls, value: str) -> str:
        if not value.startswith("sandbox://"):
            raise ValueError("artifact_ref must use the sandbox:// scheme")
        return value


class CandidateLocationPreference(ContractModel):
    cities: List[str] = Field(min_length=1, max_length=4)
    remote_policy: RemotePolicy
    relocation_open: bool


class WorkStyle(ContractModel):
    team_stage_preference: List[str] = Field(min_length=1, max_length=3)
    collaboration_style: str = Field(min_length=3, max_length=100)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OverclaimRisk(ContractModel):
    level: RiskLevel
    reasons: List[str]

    @model_validator(mode="after")
    def risk_reason_is_explainable(self) -> "OverclaimRisk":
        if self.level in {RiskLevel.MEDIUM, RiskLevel.HIGH} and not self.reasons:
            raise ValueError("medium or high overclaim risk requires a reason")
        return self

class CandidateProfile(ContractModel):
    candidate_id: str = Field(pattern=r"^cand_[a-z0-9_]+$")
    name: str = Field(min_length=3, max_length=80)
    archetype: CandidateArchetype
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
    data_origin: SyntheticDataOrigin
    schema_version: SchemaVersion

    @field_validator("github_url")
    @classmethod
    def github_reference_must_not_point_to_a_real_person(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is None:
            return value
        if not (value.startswith("sandbox://") or "example.invalid" in value):
            raise ValueError("github_url must be a synthetic reference")
        return value

    @model_validator(mode="after")
    def references_must_be_internal_and_unique(self) -> "CandidateProfile":
        project_ids = [project.project_id for project in self.projects]
        if len(set(project_ids)) != len(project_ids):
            raise ValueError("project_id values must be unique within a candidate")

        evidence_ids = [evidence.evidence_id for evidence in self.project_evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence_id values must be unique within a candidate")

        known_projects = set(project_ids)
        claimed_skills = {skill.name for skill in self.skills}
        for evidence in self.project_evidence:
            if evidence.project_id not in known_projects:
                raise ValueError(
                    f"evidence {evidence.evidence_id} references unknown project_id "
                    f"{evidence.project_id}"
                )
            unknown_skills = set(evidence.supports_skills) - claimed_skills
            if unknown_skills:
                raise ValueError(
                    f"evidence {evidence.evidence_id} supports unclaimed skills: "
                    f"{sorted(unknown_skills)}"
                )
        return self
