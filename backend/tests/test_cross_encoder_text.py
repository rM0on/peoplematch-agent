from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _record(path: str, identifier: str) -> dict[str, object]:
    key = "candidate_id" if identifier.startswith("cand_") else "job_id"
    for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if payload[key] == identifier:
            return payload
    raise AssertionError(f"record {identifier} not found")


def _candidate():
    from app.schemas.candidate import CandidateProfile

    return CandidateProfile.model_validate(_record("data/samples/candidates.jsonl", "cand_001"))


def _job():
    from app.schemas.job import JobProfile

    return JobProfile.model_validate(_record("data/samples/jobs.jsonl", "job_001"))


def test_candidate_text_uses_only_allowlisted_sections_and_available_evidence() -> None:
    from app.services.cross_encoder.text import build_candidate_text

    candidate = _candidate()
    text = build_candidate_text(candidate)

    assert text.startswith("TARGET ROLES:")
    assert "SKILLS:" in text
    assert "PROJECT TECHNOLOGIES:" in text
    assert "PROJECT-CLAIMED SKILLS:" in text
    assert "VERIFIED EVIDENCE SKILLS:" in text
    assert "AI TOOLS:" in text
    assert "LOCATION:" in text
    assert "SENIORITY:" in text
    assert "WORK STYLE:" in text
    assert candidate.skills[0].name in text
    assert candidate.projects[0].technologies[0] in text
    assert candidate.projects[0].skills_demonstrated[0] in text
    assert candidate.ai_tools[0] in text
    assert all(e.supports_skills[0] in text for e in candidate.project_evidence if e.verification_status.value == "available")
    assert all(e.supports_skills[0] not in text for e in candidate.project_evidence if e.verification_status.value != "available")
    for excluded in (candidate.candidate_id, candidate.name, candidate.raw_text, candidate.projects[0].project_id):
        assert excluded not in text


def test_job_text_preserves_must_have_and_nice_to_have_boundaries() -> None:
    from app.services.cross_encoder.text import build_job_text

    job = _job()
    text = build_job_text(job)

    assert text.index("MUST HAVE:") < text.index("NICE TO HAVE:")
    assert job.role_title in text
    assert job.role_direction[0] in text
    assert job.must_have[0].text in text
    assert job.nice_to_have[0].text in text
    assert job.must_have[0].requirement_id not in text
    assert job.company_name not in text
    assert job.raw_jd not in text
    changed_job = job.model_copy(
        update={
            "evaluation_focus": ["EXCLUDED_EVALUATION_FOCUS"],
            "must_have": [
                job.must_have[0].model_copy(
                    update={"evidence_expectation": "EXCLUDED_EVIDENCE_EXPECTATION"}
                ),
                *job.must_have[1:],
            ],
        }
    )
    changed_text = build_job_text(changed_job)
    assert "EXCLUDED_EVALUATION_FOCUS" not in changed_text
    assert "EXCLUDED_EVIDENCE_EXPECTATION" not in changed_text


def test_text_is_byte_stable_and_pair_order_is_job_then_candidate() -> None:
    from app.services.cross_encoder.text import build_pair_text, build_job_text

    job = _job()
    candidate = _candidate()
    assert build_job_text(job) == build_job_text(job.model_copy(deep=True))
    pair = build_pair_text(job, candidate)
    assert pair.text_a == build_job_text(job)
    assert pair.text_b != pair.text_a
    assert pair.pair_order == "job_then_candidate"


def test_mutating_excluded_fields_does_not_change_candidate_text() -> None:
    from app.services.cross_encoder.text import build_candidate_text

    candidate = _candidate()
    baseline = build_candidate_text(candidate)
    mutated = candidate.model_copy(
        update={
            "candidate_id": "cand_999",
            "name": "Excluded Name",
            "raw_text": "Excluded raw profile text " * 10,
            "projects": [
                candidate.projects[0].model_copy(
                    update={
                        "name": "Excluded Project",
                        "summary": "Excluded project summary " * 20,
                    }
                ),
                *candidate.projects[1:],
            ],
        }
    )
    assert build_candidate_text(mutated) == baseline


def test_missing_and_described_evidence_never_becomes_verified_text() -> None:
    from app.services.cross_encoder.text import build_candidate_text

    candidate = _candidate()
    evidence = candidate.project_evidence[0]
    described = evidence.model_copy(update={"verification_status": "described", "supports_skills": ["described-only"]})
    missing = evidence.model_copy(update={"verification_status": "missing", "supports_skills": ["missing-only"]})
    mutated = candidate.model_copy(update={"project_evidence": [described, missing]})
    text = build_candidate_text(mutated)
    assert "described-only" not in text
    assert "missing-only" not in text


def test_skills_category_and_evidence_type_are_not_semantic_ce_inputs() -> None:
    from app.services.cross_encoder.text import build_candidate_text

    candidate = _candidate()
    baseline = build_candidate_text(candidate)
    changed = candidate.model_copy(
        update={
            "skills": [
                candidate.skills[0].model_copy(update={"category": "security"}),
                *candidate.skills[1:],
            ],
            "project_evidence": [
                candidate.project_evidence[0].model_copy(update={"evidence_type": "tests"}),
                *candidate.project_evidence[1:],
            ],
        }
    )
    assert build_candidate_text(changed) == baseline


def test_candidate_construction_and_provenance_mutations_do_not_change_text() -> None:
    from app.services.cross_encoder.text import build_candidate_text

    candidate = _candidate()
    baseline = build_candidate_text(candidate)
    project = candidate.projects[0]
    evidence = candidate.project_evidence[0]
    mutated = candidate.model_copy(
        update={
            "candidate_id": "cand_999",
            "archetype": "overclaim_candidate",
            "projects": [
                project.model_copy(
                    update={
                        "name": "Excluded Name",
                        "summary": "Excluded summary " * 20,
                        "role": "Excluded role",
                        "outcomes": ["Excluded outcome"],
                    }
                ),
                *candidate.projects[1:],
            ],
            "project_evidence": [
                evidence.model_copy(update={"statement": "Excluded statement " * 20}),
                *candidate.project_evidence[1:],
            ],
        }
    )
    object.__setattr__(mutated, "data_origin", "user_created")
    object.__setattr__(mutated, "schema_version", "9.9")
    object.__setattr__(mutated, "dataset_version", "construction-only")
    object.__setattr__(mutated, "split", "test")
    object.__setattr__(mutated, "construction_metadata", {"archetype": "synthetic"})
    assert build_candidate_text(mutated) == baseline


def test_described_and_missing_payload_mutations_do_not_change_text() -> None:
    from app.services.cross_encoder.text import build_candidate_text

    candidate = _candidate()
    baseline = build_candidate_text(candidate)
    evidence = candidate.project_evidence[0]
    described = evidence.model_copy(
        update={
            "evidence_id": "ev_described_extra",
            "verification_status": "described",
            "supports_skills": [candidate.skills[0].name],
        }
    )
    missing = evidence.model_copy(
        update={
            "evidence_id": "ev_missing_extra",
            "verification_status": "missing",
            "supports_skills": [candidate.skills[0].name],
        }
    )
    mutated = candidate.model_copy(
        update={"project_evidence": [*candidate.project_evidence, described, missing]}
    )
    assert build_candidate_text(mutated) == baseline


def test_available_evidence_supports_skills_is_a_positive_control() -> None:
    from app.services.cross_encoder.text import build_candidate_text

    candidate = _candidate()
    available_index = next(
        index
        for index, evidence in enumerate(candidate.project_evidence)
        if evidence.verification_status.value == "available"
    )
    evidence = candidate.project_evidence[available_index]
    changed = evidence.model_copy(update={"supports_skills": ["changed-verified-skill"]})
    mutated = candidate.model_copy(
        update={
            "project_evidence": [
                changed if index == available_index else item
                for index, item in enumerate(candidate.project_evidence)
            ]
        }
    )
    before = build_candidate_text(candidate)
    after = build_candidate_text(mutated)
    assert before != after
    assert "VERIFIED EVIDENCE SKILLS: changed-verified-skill" in after


def test_job_construction_and_provenance_mutations_do_not_change_text() -> None:
    from app.services.cross_encoder.text import build_job_text

    job = _job()
    baseline = build_job_text(job)
    mutated = job.model_copy(
        update={
            "job_id": "job_999",
            "archetype": "data_engineer",
            "company_name": "Excluded Company",
            "raw_jd": "Excluded raw JD " * 40,
            "evaluation_focus": ["Excluded evaluation focus"],
            "must_have": [
                job.must_have[0].model_copy(
                    update={"evidence_expectation": "Excluded expectation"}
                ),
                *job.must_have[1:],
            ],
        }
    )
    object.__setattr__(mutated, "data_origin", "user_created")
    object.__setattr__(mutated, "schema_version", "9.9")
    object.__setattr__(mutated, "dataset_version", "construction-only")
    object.__setattr__(mutated, "split", "test")
    object.__setattr__(mutated, "construction_metadata", {"template": "synthetic"})
    assert build_job_text(mutated) == baseline
