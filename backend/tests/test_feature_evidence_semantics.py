from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _profiles():
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobProfile

    candidate = CandidateProfile.model_validate(
        json.loads(
            (ROOT / "data/samples/candidates.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
    )
    job = JobProfile.model_validate(
        json.loads(
            (ROOT / "data/samples/jobs.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
    )
    return candidate, job


def _candidate_with_fastapi_evidence(status):
    from app.schemas.candidate import ProjectEvidence, SkillClaim

    candidate, _ = _profiles()
    project = candidate.projects[0].model_copy(
        update={"technologies": ["FastAPI"], "skills_demonstrated": ["FastAPI"]}
    )
    evidence = ProjectEvidence(
        evidence_id="ev_fastapi_semantics",
        project_id=project.project_id,
        supports_skills=["FastAPI"],
        evidence_type="tests",
        statement="Structured synthetic evidence status drives eligibility.",
        artifact_ref="sandbox://feature-test/evidence-semantics",
        verification_status=status,
    )
    return candidate.model_copy(
        update={
            "skills": [SkillClaim(name="FastAPI", category="backend")],
            "projects": [project],
            "project_evidence": [evidence],
        }
    )


def _requirement(requirement_id: str, category, text: str):
    from app.schemas.job import JobRequirement

    return JobRequirement(
        requirement_id=requirement_id,
        text=text,
        category=category,
        evidence_expectation="Reviewable structured synthetic evidence",
    )


def _job_with_requirements(*requirements):
    _, job = _profiles()
    return job.model_copy(update={"must_have": list(requirements), "nice_to_have": []})


@pytest.mark.parametrize(
    ("status", "expected_score", "expected_skills", "expected_requirement_ids"),
    [
        ("available", 1.0, ["FastAPI"], ["req_fastapi_skill"]),
        ("described", 0.0, [], []),
        ("missing", 0.0, [], []),
    ],
)
def test_only_available_evidence_can_create_positive_evidence_support(
    status: str,
    expected_score: float,
    expected_skills: list[str],
    expected_requirement_ids: list[str],
) -> None:
    from app.services.features.extractor import extract_pair_features

    candidate = _candidate_with_fastapi_evidence(status)
    job = _job_with_requirements(
        _requirement(
            "req_fastapi_skill", "skill", "Practical use of FastAPI"
        )
    )

    result = extract_pair_features(candidate, job)

    assert result.vector.project_evidence_score == expected_score
    assert result.diagnostics.matched_evidence_skills == expected_skills
    assert (
        result.diagnostics.evidence_supported_requirement_ids
        == expected_requirement_ids
    )


def test_missing_evidence_keeps_claimed_skill_and_verified_support_separate() -> None:
    from app.services.features.extractor import extract_pair_features

    candidate = _candidate_with_fastapi_evidence("missing")
    job = _job_with_requirements(
        _requirement(
            "req_fastapi_skill", "skill", "Practical use of FastAPI"
        )
    )

    result = extract_pair_features(candidate, job)

    assert result.vector.skill_fit_score == 1.0
    assert result.vector.missing_penalty == 0.0
    assert result.vector.project_evidence_score == 0.0
    assert result.diagnostics.matched_capabilities == ["FastAPI"]
    assert result.diagnostics.matched_evidence_skills == []
    assert result.diagnostics.evidence_supported_requirement_ids == []


def test_project_evidence_requirement_does_not_become_a_skill_requirement() -> None:
    from app.services.features.extractor import extract_pair_features

    requirement = _requirement(
        "req_fastapi_evidence",
        "project_evidence",
        "Provide reviewable evidence for FastAPI delivery",
    )
    job = _job_with_requirements(requirement)

    missing = extract_pair_features(
        _candidate_with_fastapi_evidence("missing"), job
    )
    available = extract_pair_features(
        _candidate_with_fastapi_evidence("available"), job
    )

    assert missing.vector.skill_fit_score is None
    assert missing.vector.missing_penalty is None
    assert missing.vector.project_evidence_score == 0.0
    assert missing.diagnostics.availability.skill_fit_score is False
    assert missing.diagnostics.availability.missing_penalty is False
    assert available.vector.skill_fit_score is None
    assert available.vector.missing_penalty is None
    assert available.vector.project_evidence_score == 1.0
    assert available.diagnostics.evidence_supported_requirement_ids == [
        requirement.requirement_id
    ]


def test_experience_requirement_is_out_of_scope_for_capability_features() -> None:
    from app.services.features.extractor import extract_pair_features

    candidate = _candidate_with_fastapi_evidence("available")
    job = _job_with_requirements(
        _requirement(
            "req_fastapi_experience",
            "experience",
            "Experience communicating FastAPI systems to product partners",
        )
    )

    result = extract_pair_features(candidate, job)

    assert result.vector.skill_fit_score is None
    assert result.vector.project_evidence_score is None
    assert result.vector.missing_penalty is None
    assert result.diagnostics.availability.skill_fit_score is False
    assert result.diagnostics.availability.project_evidence_score is False
    assert result.diagnostics.availability.missing_penalty is False
    assert result.diagnostics.matched_must_have_requirement_ids == []
    assert result.diagnostics.missing_must_have_requirement_ids == []
    assert result.diagnostics.evidence_supported_requirement_ids == []


def test_mixed_requirements_use_feature_specific_category_denominators() -> None:
    from app.services.features.extractor import extract_pair_features

    skill = _requirement(
        "req_fastapi_skill", "skill", "Practical use of FastAPI"
    )
    evidence = _requirement(
        "req_fastapi_evidence",
        "project_evidence",
        "Provide reviewable evidence for FastAPI delivery",
    )
    experience = _requirement(
        "req_partner_experience",
        "experience",
        "Experience communicating Kubernetes systems to product partners",
    )
    candidate = _candidate_with_fastapi_evidence("available")
    job = _job_with_requirements(skill, evidence, experience)

    result = extract_pair_features(candidate, job)

    assert result.vector.skill_fit_score == 1.0
    assert result.vector.project_evidence_score == 1.0
    assert result.vector.missing_penalty == 0.0
    assert result.diagnostics.matched_must_have_requirement_ids == [
        skill.requirement_id
    ]
    assert result.diagnostics.missing_must_have_requirement_ids == []
    assert result.diagnostics.evidence_supported_requirement_ids == [
        skill.requirement_id,
        evidence.requirement_id,
    ]
