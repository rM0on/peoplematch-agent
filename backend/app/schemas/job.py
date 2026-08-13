from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import Field, field_validator, model_validator

from app.schemas.shared import (
    ContractModel,
    ProductStage,
    RemotePolicy,
    SchemaVersion,
    Seniority,
    SyntheticDataOrigin,
)


class JobArchetype(str, Enum):
    AI_MATCHING_ALGORITHM_ENGINEER = "ai_matching_algorithm_engineer"
    RECOMMENDATION_ALGORITHM_ENGINEER = "recommendation_algorithm_engineer"
    LLM_AGENT_ENGINEER = "llm_agent_engineer"
    AI_PRODUCT_ENGINEER = "ai_product_engineer"
    RAG_ENGINEER = "rag_engineer"
    SEARCH_RETRIEVAL_ENGINEER = "search_retrieval_engineer"
    APPLIED_ML_ENGINEER = "applied_ml_engineer"
    ML_PLATFORM_ENGINEER = "ml_platform_engineer"
    MLOPS_ENGINEER = "mlops_engineer"
    AI_INFRA_ENGINEER = "ai_infra_engineer"
    BACKEND_AI_ENGINEER = "backend_ai_engineer"
    FULL_STACK_AI_ENGINEER = "full_stack_ai_engineer"
    NLP_ALGORITHM_ENGINEER = "nlp_algorithm_engineer"
    AI_SECURITY_ENGINEER = "ai_security_engineer"
    DATA_ENGINEER = "data_engineer"
    ML_SYSTEMS_ENGINEER = "ml_systems_engineer"


class RequirementCategory(str, Enum):
    SKILL = "skill"
    PROJECT_EVIDENCE = "project_evidence"
    EXPERIENCE = "experience"
    ROLE_DIRECTION = "role_direction"
    LOCATION = "location"
    SENIORITY = "seniority"
    WORK_STYLE = "work_style"
    AI_TOOLING = "ai_tooling"


class JobRequirement(ContractModel):
    requirement_id: str = Field(pattern=r"^req_[a-z0-9_]+$")
    text: str = Field(min_length=5, max_length=240)
    category: RequirementCategory
    evidence_expectation: str = Field(min_length=8, max_length=300)


class JobLocation(ContractModel):
    cities: List[str] = Field(min_length=1, max_length=4)
    remote_policy: RemotePolicy
    relocation_supported: bool


class JobProfile(ContractModel):
    job_id: str = Field(pattern=r"^job_[a-z0-9_]+$")
    company_name: str = Field(min_length=3, max_length=100)
    role_title: str = Field(min_length=3, max_length=120)
    archetype: JobArchetype
    raw_jd: str = Field(min_length=60, max_length=6000)
    must_have: List[JobRequirement] = Field(min_length=1)
    nice_to_have: List[JobRequirement]
    role_direction: List[str] = Field(min_length=1)
    team_tags: List[str] = Field(min_length=1)
    location: JobLocation
    seniority_requirement: List[Seniority] = Field(min_length=1)
    product_stage: ProductStage
    evaluation_focus: List[str] = Field(min_length=1)
    data_origin: SyntheticDataOrigin
    schema_version: SchemaVersion

    @field_validator(
        "role_direction", "team_tags", "seniority_requirement", "evaluation_focus"
    )
    @classmethod
    def list_values_must_be_unique(cls, values: List[object]) -> List[object]:
        if len(set(values)) != len(values):
            raise ValueError("list values must be unique")
        return values

    @model_validator(mode="after")
    def requirement_ids_must_be_unique(self) -> "JobProfile":
        requirement_ids = [
            requirement.requirement_id
            for requirement in [*self.must_have, *self.nice_to_have]
        ]
        if len(set(requirement_ids)) != len(requirement_ids):
            raise ValueError("requirement_id values must be unique within a job")
        return self
