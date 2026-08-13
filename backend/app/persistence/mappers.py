from __future__ import annotations

from app.models.candidate import (
    CandidateProfileModel,
    CandidateProjectEvidenceModel,
    CandidateProjectModel,
    CandidateSkillModel,
)
from app.models.job import JobProfileModel, JobRequirementModel
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobProfile
from app.schemas.persistence import CandidateRecord, DataOrigin, JobRecord


def candidate_model_from_profile(
    profile: CandidateProfile, *, dataset_version: str
) -> CandidateProfileModel:
    model = CandidateProfileModel(
        candidate_id=profile.candidate_id,
        name=profile.name,
        raw_text=profile.raw_text,
        github_url=profile.github_url,
        seniority=profile.seniority.value,
        data_origin=profile.data_origin,
        schema_version=profile.schema_version,
        dataset_version=dataset_version,
        dataset_archetype=profile.archetype.value,
        ai_tools=profile.ai_tools,
        target_roles=profile.target_roles,
        missing_fields=profile.missing_fields,
        preferred_locations=profile.preferred_locations.model_dump(mode="json"),
        work_style=profile.work_style.model_dump(mode="json"),
        overclaim_risk=profile.overclaim_risk.model_dump(mode="json"),
    )
    model.skills = [
        CandidateSkillModel(
            position=index,
            name=skill.name,
            category=skill.category.value,
            self_reported_level=(
                skill.self_reported_level.value if skill.self_reported_level else None
            ),
        )
        for index, skill in enumerate(profile.skills)
    ]
    model.projects = [
        CandidateProjectModel(
            position=index,
            project_id=project.project_id,
            name=project.name,
            summary=project.summary,
            role=project.role,
            technologies=project.technologies,
            outcomes=project.outcomes,
            skills_demonstrated=project.skills_demonstrated,
        )
        for index, project in enumerate(profile.projects)
    ]
    model.evidence = [
        CandidateProjectEvidenceModel(
            position=index,
            evidence_id=evidence.evidence_id,
            project_id=evidence.project_id,
            supports_skills=evidence.supports_skills,
            evidence_type=evidence.evidence_type.value,
            statement=evidence.statement,
            artifact_ref=evidence.artifact_ref,
            verification_status=evidence.verification_status.value,
        )
        for index, evidence in enumerate(profile.project_evidence)
    ]
    return model


def candidate_record_from_model(model: CandidateProfileModel) -> CandidateRecord:
    return CandidateRecord.model_validate(
        {
            "candidate_id": model.candidate_id,
            "name": model.name,
            "archetype": model.dataset_archetype,
            "raw_text": model.raw_text,
            "skills": [
                {
                    "name": skill.name,
                    "category": skill.category,
                    "self_reported_level": skill.self_reported_level,
                }
                for skill in model.skills
            ],
            "projects": [
                {
                    "project_id": project.project_id,
                    "name": project.name,
                    "summary": project.summary,
                    "role": project.role,
                    "technologies": project.technologies,
                    "outcomes": project.outcomes,
                    "skills_demonstrated": project.skills_demonstrated,
                }
                for project in model.projects
            ],
            "project_evidence": [
                {
                    "evidence_id": evidence.evidence_id,
                    "project_id": evidence.project_id,
                    "supports_skills": evidence.supports_skills,
                    "evidence_type": evidence.evidence_type,
                    "statement": evidence.statement,
                    "artifact_ref": evidence.artifact_ref,
                    "verification_status": evidence.verification_status,
                }
                for evidence in model.evidence
            ],
            "github_url": model.github_url,
            "ai_tools": model.ai_tools,
            "target_roles": model.target_roles,
            "preferred_locations": model.preferred_locations,
            "seniority": model.seniority,
            "work_style": model.work_style,
            "missing_fields": model.missing_fields,
            "overclaim_risk": model.overclaim_risk,
            "data_origin": model.data_origin,
            "schema_version": model.schema_version,
            "dataset_version": model.dataset_version,
        }
    )


def job_model_from_profile(profile: JobProfile, *, dataset_version: str) -> JobProfileModel:
    model = JobProfileModel(
        job_id=profile.job_id,
        company_name=profile.company_name,
        role_title=profile.role_title,
        raw_jd=profile.raw_jd,
        product_stage=profile.product_stage.value,
        data_origin=profile.data_origin,
        schema_version=profile.schema_version,
        dataset_version=dataset_version,
        dataset_archetype=profile.archetype.value,
        role_direction=profile.role_direction,
        team_tags=profile.team_tags,
        seniority_requirement=[value.value for value in profile.seniority_requirement],
        evaluation_focus=profile.evaluation_focus,
        location=profile.location.model_dump(mode="json"),
    )
    model.requirements = [
        JobRequirementModel(
            requirement_id=requirement.requirement_id,
            requirement_group=group,
            position=index,
            category=requirement.category.value,
            text=requirement.text,
            evidence_expectation=requirement.evidence_expectation,
        )
        for group, requirements in (
            ("must_have", profile.must_have),
            ("nice_to_have", profile.nice_to_have),
        )
        for index, requirement in enumerate(requirements)
    ]
    return model


def job_record_from_model(model: JobProfileModel) -> JobRecord:
    def requirements(group: str) -> list[dict[str, str]]:
        return [
            {
                "requirement_id": requirement.requirement_id,
                "text": requirement.text,
                "category": requirement.category,
                "evidence_expectation": requirement.evidence_expectation,
            }
            for requirement in model.requirements
            if requirement.requirement_group == group
        ]

    return JobRecord.model_validate(
        {
            "job_id": model.job_id,
            "company_name": model.company_name,
            "role_title": model.role_title,
            "archetype": model.dataset_archetype,
            "raw_jd": model.raw_jd,
            "must_have": requirements("must_have"),
            "nice_to_have": requirements("nice_to_have"),
            "role_direction": model.role_direction,
            "team_tags": model.team_tags,
            "location": model.location,
            "seniority_requirement": model.seniority_requirement,
            "product_stage": model.product_stage,
            "evaluation_focus": model.evaluation_focus,
            "data_origin": model.data_origin,
            "schema_version": model.schema_version,
            "dataset_version": model.dataset_version,
        }
    )


def candidate_model_from_record(record: CandidateRecord) -> CandidateProfileModel:
    model = CandidateProfileModel(
        candidate_id=record.candidate_id,
        name=record.name,
        raw_text=record.raw_text,
        github_url=record.github_url,
        seniority=record.seniority.value,
        data_origin=record.data_origin.value,
        schema_version=record.schema_version,
        dataset_version=record.dataset_version,
        dataset_archetype=record.archetype.value if record.archetype else None,
        ai_tools=record.ai_tools,
        target_roles=record.target_roles,
        missing_fields=record.missing_fields,
        preferred_locations=record.preferred_locations.model_dump(mode="json"),
        work_style=record.work_style.model_dump(mode="json"),
        overclaim_risk=record.overclaim_risk.model_dump(mode="json"),
    )
    model.skills = [CandidateSkillModel(position=i, **s.model_dump(mode="json")) for i, s in enumerate(record.skills)]
    model.projects = [CandidateProjectModel(position=i, **p.model_dump(mode="json")) for i, p in enumerate(record.projects)]
    model.evidence = [CandidateProjectEvidenceModel(position=i, **e.model_dump(mode="json")) for i, e in enumerate(record.project_evidence)]
    return model


def job_model_from_record(record: JobRecord) -> JobProfileModel:
    model = JobProfileModel(
        job_id=record.job_id,
        company_name=record.company_name,
        role_title=record.role_title,
        raw_jd=record.raw_jd,
        product_stage=record.product_stage.value,
        data_origin=record.data_origin.value,
        schema_version=record.schema_version,
        dataset_version=record.dataset_version,
        dataset_archetype=record.archetype.value if record.archetype else None,
        role_direction=record.role_direction,
        team_tags=record.team_tags,
        seniority_requirement=[v.value for v in record.seniority_requirement],
        evaluation_focus=record.evaluation_focus,
        location=record.location.model_dump(mode="json"),
    )
    model.requirements = [
        JobRequirementModel(
            requirement_id=req.requirement_id,
            requirement_group=group,
            position=i,
            category=req.category.value,
            text=req.text,
            evidence_expectation=req.evidence_expectation,
        )
        for group, values in (("must_have", record.must_have), ("nice_to_have", record.nice_to_have))
        for i, req in enumerate(values)
    ]
    return model


def apply_candidate_record(
    model: CandidateProfileModel,
    record: CandidateRecord,
    *,
    changed_fields: set[str],
) -> None:
    scalar_values = {
        "name": record.name,
        "raw_text": record.raw_text,
        "github_url": record.github_url,
        "seniority": record.seniority.value,
        "ai_tools": record.ai_tools,
        "target_roles": record.target_roles,
        "missing_fields": record.missing_fields,
        "preferred_locations": record.preferred_locations.model_dump(mode="json"),
        "work_style": record.work_style.model_dump(mode="json"),
        "overclaim_risk": record.overclaim_risk.model_dump(mode="json"),
    }
    for field, value in scalar_values.items():
        if field in changed_fields:
            setattr(model, field, value)

    if "skills" in changed_fields:
        existing_skills = {skill.name: skill for skill in model.skills}
        updated_skills = []
        for index, skill in enumerate(record.skills):
            skill_model = existing_skills.get(skill.name)
            if skill_model is None:
                skill_model = CandidateSkillModel()
            skill_model.position = index
            skill_model.name = skill.name
            skill_model.category = skill.category.value
            skill_model.self_reported_level = (
                skill.self_reported_level.value if skill.self_reported_level else None
            )
            updated_skills.append(skill_model)
        model.skills = updated_skills

    updated_projects = None
    if "projects" in changed_fields:
        existing_projects = {project.project_id: project for project in model.projects}
        updated_projects = []
        for index, project in enumerate(record.projects):
            project_model = existing_projects.get(project.project_id)
            if project_model is None:
                project_model = CandidateProjectModel()
            project_model.position = index
            project_model.project_id = project.project_id
            project_model.name = project.name
            project_model.summary = project.summary
            project_model.role = project.role
            project_model.technologies = project.technologies
            project_model.outcomes = project.outcomes
            project_model.skills_demonstrated = project.skills_demonstrated
            updated_projects.append(project_model)

    if "project_evidence" in changed_fields:
        existing_evidence = {
            evidence.evidence_id: evidence for evidence in model.evidence
        }
        updated_evidence = []
        for index, evidence in enumerate(record.project_evidence):
            evidence_model = existing_evidence.get(evidence.evidence_id)
            if evidence_model is None:
                evidence_model = CandidateProjectEvidenceModel()
            evidence_model.position = index
            evidence_model.evidence_id = evidence.evidence_id
            evidence_model.project_id = evidence.project_id
            evidence_model.supports_skills = evidence.supports_skills
            evidence_model.evidence_type = evidence.evidence_type.value
            evidence_model.statement = evidence.statement
            evidence_model.artifact_ref = evidence.artifact_ref
            evidence_model.verification_status = evidence.verification_status.value
            updated_evidence.append(evidence_model)
        model.evidence = updated_evidence

    if updated_projects is not None:
        model.projects = updated_projects


def apply_job_record(
    model: JobProfileModel,
    record: JobRecord,
    *,
    changed_fields: set[str],
) -> None:
    scalar_values = {
        "company_name": record.company_name,
        "role_title": record.role_title,
        "raw_jd": record.raw_jd,
        "product_stage": record.product_stage.value,
        "role_direction": record.role_direction,
        "team_tags": record.team_tags,
        "seniority_requirement": [value.value for value in record.seniority_requirement],
        "evaluation_focus": record.evaluation_focus,
        "location": record.location.model_dump(mode="json"),
    }
    for field, value in scalar_values.items():
        if field in changed_fields:
            setattr(model, field, value)

    if {"must_have", "nice_to_have"} & changed_fields:
        existing_requirements = {
            requirement.requirement_id: requirement
            for requirement in model.requirements
        }
        updated_requirements = []
        for group, requirements in (
            ("must_have", record.must_have),
            ("nice_to_have", record.nice_to_have),
        ):
            for index, requirement in enumerate(requirements):
                requirement_model = existing_requirements.get(
                    requirement.requirement_id
                )
                if requirement_model is None:
                    requirement_model = JobRequirementModel()
                requirement_model.requirement_id = requirement.requirement_id
                requirement_model.requirement_group = group
                requirement_model.position = index
                requirement_model.category = requirement.category.value
                requirement_model.text = requirement.text
                requirement_model.evidence_expectation = (
                    requirement.evidence_expectation
                )
                updated_requirements.append(requirement_model)
        model.requirements = updated_requirements
