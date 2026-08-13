from __future__ import annotations

import pytest
from pydantic import ValidationError


def _candidate_payload() -> dict[str, object]:
    return {
        "candidate_id": "cand_test",
        "name": "Candidate Test",
        "archetype": "llm_application_agent_engineer",
        "raw_text": "Built a sandbox agent workflow with tool calling and a deterministic evaluation harness.",
        "skills": [
            {
                "name": "Agent workflow",
                "category": "llm_application",
                "self_reported_level": "advanced",
            }
        ],
        "projects": [
            {
                "project_id": "prj_test_01",
                "name": "Sandbox Workflow Lab",
                "summary": "A local workflow prototype for testing tool calls.",
                "role": "Builder",
                "technologies": ["Python", "FastAPI"],
                "outcomes": ["Implemented deterministic workflow tests."],
                "skills_demonstrated": ["Agent workflow"],
            }
        ],
        "project_evidence": [
            {
                "evidence_id": "ev_test_01",
                "project_id": "prj_test_01",
                "supports_skills": ["Agent workflow"],
                "evidence_type": "tests",
                "statement": "The sandbox test suite exercises tool-call success and failure paths.",
                "artifact_ref": "sandbox://candidate/cand_test/project/prj_test_01/tests",
                "verification_status": "available",
            }
        ],
        "github_url": "https://example.invalid/candidate/cand_test",
        "ai_tools": ["structured outputs"],
        "target_roles": ["LLM Agent Engineer"],
        "preferred_locations": {
            "cities": ["Shanghai"],
            "remote_policy": "hybrid",
            "relocation_open": True,
        },
        "seniority": "mid",
        "work_style": {
            "team_stage_preference": ["zero_to_one"],
            "collaboration_style": "cross_functional",
        },
        "missing_fields": [],
        "overclaim_risk": {"level": "low", "reasons": []},
        "data_origin": "synthetic_sandbox",
        "schema_version": "1.0",
    }


def _job_payload() -> dict[str, object]:
    return {
        "job_id": "job_test",
        "company_name": "Northstar Labs",
        "role_title": "LLM Agent Engineer",
        "archetype": "llm_agent_engineer",
        "raw_jd": "Build local agent workflows, own evaluation, and work with product partners in a fictional early-stage team.",
        "must_have": [
            {
                "requirement_id": "req_test_01",
                "text": "Demonstrated agent workflow implementation",
                "category": "project_evidence",
                "evidence_expectation": "Code or tests from a sandbox project",
            }
        ],
        "nice_to_have": [],
        "role_direction": ["agent_product_delivery"],
        "team_tags": ["fictional_company", "small_team"],
        "location": {
            "cities": ["Shanghai"],
            "remote_policy": "hybrid",
            "relocation_supported": True,
        },
        "seniority_requirement": ["mid", "senior"],
        "product_stage": "zero_to_one",
        "evaluation_focus": ["project evidence", "workflow reliability"],
        "data_origin": "synthetic_sandbox",
        "schema_version": "1.0",
    }


def test_candidate_profile_accepts_evidence_aware_profile() -> None:
    from app.schemas.candidate import CandidateProfile

    profile = CandidateProfile.model_validate(_candidate_payload())

    assert profile.candidate_id == "cand_test"
    assert profile.project_evidence[0].supports_skills == ["Agent workflow"]
    assert profile.data_origin == "synthetic_sandbox"


def test_candidate_profile_rejects_broken_project_reference() -> None:
    from app.schemas.candidate import CandidateProfile

    payload = _candidate_payload()
    payload["project_evidence"][0]["project_id"] = "prj_missing"  # type: ignore[index]

    with pytest.raises(ValidationError, match="unknown project_id"):
        CandidateProfile.model_validate(payload)


def test_candidate_profile_rejects_non_synthetic_origin() -> None:
    from app.schemas.candidate import CandidateProfile

    payload = _candidate_payload()
    payload["data_origin"] = "private_resume"

    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(payload)


def test_job_profile_accepts_typed_requirements_and_location() -> None:
    from app.schemas.job import JobProfile

    profile = JobProfile.model_validate(_job_payload())

    assert profile.must_have[0].category.value == "project_evidence"
    assert profile.location.remote_policy.value == "hybrid"


def test_job_profile_rejects_duplicate_requirement_ids() -> None:
    from app.schemas.job import JobProfile

    payload = _job_payload()
    payload["nice_to_have"] = [dict(payload["must_have"][0])]  # type: ignore[index]

    with pytest.raises(ValidationError, match="requirement_id values must be unique"):
        JobProfile.model_validate(payload)


def test_relevance_grade_is_limited_to_zero_through_three() -> None:
    from app.schemas.labels import RelevanceLabel

    with pytest.raises(ValidationError):
        RelevanceLabel.model_validate(
            {
                "label_id": "lbl_test",
                "query_type": "job_to_candidate",
                "job_id": "job_test",
                "candidate_id": "cand_test",
                "relevance_grade": 4,
                "hard_negative": False,
                "mismatch_reasons": [],
                "rationale": "Out-of-range grade must be rejected.",
                "supporting_evidence_ids": [],
                "affected_requirement_ids": [],
                "confidence": 0.8,
                "annotation_source": "synthetic_curated",
                "split": "train",
                "schema_version": "1.0",
            }
        )


def test_pairwise_preference_rejects_identical_candidates() -> None:
    from app.schemas.labels import PairwisePreference

    with pytest.raises(ValidationError, match="winner and loser must differ"):
        PairwisePreference.model_validate(
            {
                "preference_id": "pref_test",
                "job_id": "job_test",
                "winner_candidate_id": "cand_test",
                "loser_candidate_id": "cand_test",
                "reason_codes": ["EVIDENCE_INSUFFICIENT"],
                "rationale": "A pair must compare distinct candidates.",
                "confidence": 0.8,
                "annotation_source": "synthetic_curated",
                "split": "train",
                "schema_version": "1.0",
            }
        )
