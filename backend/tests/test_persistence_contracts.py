from __future__ import annotations

import json
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _load_jsonl_record(path: Path, record_id: str, id_field: str) -> dict[str, object]:
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if payload[id_field] == record_id:
            return payload
    raise AssertionError(f"{record_id} not found in {path}")


def test_candidate_models_are_normalized_and_cascade_nested_rows() -> None:
    from app.models.candidate import (
        CandidateProfileModel,
        CandidateProjectEvidenceModel,
        CandidateProjectModel,
        CandidateSkillModel,
    )

    assert CandidateProfileModel.__tablename__ == "candidate_profiles"
    assert CandidateSkillModel.__tablename__ == "candidate_skills"
    assert CandidateProjectModel.__tablename__ == "candidate_projects"
    assert CandidateProjectEvidenceModel.__tablename__ == "candidate_project_evidence"
    assert CandidateProfileModel.__table__.c.dataset_version.nullable
    assert CandidateProfileModel.__table__.c.dataset_archetype.nullable
    assert CandidateProfileModel.skills.property.cascade.delete_orphan
    assert CandidateProfileModel.projects.property.cascade.delete_orphan
    assert CandidateProfileModel.evidence.property.cascade.delete_orphan
    assert CandidateProjectModel.__table__.primary_key.columns.keys() == ["id"]
    assert CandidateProjectEvidenceModel.__table__.primary_key.columns.keys() == ["id"]
    assert {
        tuple(constraint.columns.keys())
        for constraint in CandidateProjectModel.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    } == {("candidate_id", "project_id")}
    assert {
        tuple(constraint.columns.keys())
        for constraint in CandidateProjectEvidenceModel.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    } == {("candidate_id", "evidence_id")}


def test_job_models_normalize_requirements() -> None:
    from app.models.job import JobProfileModel, JobRequirementModel

    assert JobProfileModel.__tablename__ == "job_profiles"
    assert JobRequirementModel.__tablename__ == "job_requirements"
    assert JobProfileModel.__table__.c.dataset_version.nullable
    assert JobProfileModel.__table__.c.dataset_archetype.nullable
    assert JobProfileModel.requirements.property.cascade.delete_orphan
    assert JobRequirementModel.__table__.primary_key.columns.keys() == ["id"]
    assert {
        tuple(constraint.columns.keys())
        for constraint in JobRequirementModel.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    } == {("job_id", "requirement_id")}


def _candidate_record_payload(*, data_origin: str, github_url: str | None) -> dict[str, object]:
    payload = _load_jsonl_record(
        REPOSITORY_ROOT / "data" / "samples" / "candidates.jsonl",
        "cand_005",
        "candidate_id",
    )
    payload["data_origin"] = data_origin
    payload["github_url"] = github_url
    payload["dataset_version"] = "1.0.0" if data_origin == "synthetic_sandbox" else None
    if data_origin != "synthetic_sandbox":
        payload["archetype"] = None
    return payload


@pytest.mark.parametrize(
    "github_url",
    [
        "https://github.com/example/test",
        "https://evil.com/?q=example.invalid",
        "https://example.invalid.evil.com/test",
    ],
)
def test_candidate_record_rejects_non_synthetic_host_for_synthetic_origin(
    github_url: str,
) -> None:
    from app.schemas.persistence import CandidateRecord

    with pytest.raises(ValueError, match="synthetic reference"):
        CandidateRecord.model_validate(
            _candidate_record_payload(
                data_origin="synthetic_sandbox",
                github_url=github_url,
            )
        )


def test_candidate_record_accepts_example_invalid_for_synthetic_origin() -> None:
    from app.schemas.persistence import CandidateRecord

    record = CandidateRecord.model_validate(
        _candidate_record_payload(
            data_origin="synthetic_sandbox",
            github_url="https://example.invalid/candidate/cand_005",
        )
    )

    assert record.github_url == "https://example.invalid/candidate/cand_005"


def test_candidate_record_accepts_sandbox_reference_for_synthetic_origin() -> None:
    from app.schemas.persistence import CandidateRecord

    record = CandidateRecord.model_validate(
        _candidate_record_payload(
            data_origin="synthetic_sandbox",
            github_url="sandbox://candidate/test",
        )
    )

    assert record.github_url == "sandbox://candidate/test"


@pytest.mark.parametrize("data_origin", ["user_created", "llm_parsed"])
def test_candidate_record_accepts_https_url_for_non_synthetic_origin(
    data_origin: str,
) -> None:
    from app.schemas.persistence import CandidateRecord

    record = CandidateRecord.model_validate(
        _candidate_record_payload(
            data_origin=data_origin,
            github_url="https://example.com/synthetic-profile",
        )
    )

    assert record.github_url == "https://example.com/synthetic-profile"


def test_frozen_candidate_mapper_roundtrip_preserves_canonical_contract() -> None:
    from app.persistence.mappers import candidate_model_from_profile, candidate_record_from_model
    from app.schemas.candidate import CandidateProfile

    payload = _load_jsonl_record(
        REPOSITORY_ROOT / "data" / "samples" / "candidates.jsonl",
        "cand_005",
        "candidate_id",
    )
    canonical = CandidateProfile.model_validate(payload)

    model = candidate_model_from_profile(canonical, dataset_version="1.0.0")
    restored = candidate_record_from_model(model)

    assert restored.to_canonical_profile() == canonical


def test_frozen_job_mapper_roundtrip_preserves_canonical_contract() -> None:
    from app.persistence.mappers import job_model_from_profile, job_record_from_model
    from app.schemas.job import JobProfile

    payload = _load_jsonl_record(
        REPOSITORY_ROOT / "data" / "samples" / "jobs.jsonl",
        "job_001",
        "job_id",
    )
    canonical = JobProfile.model_validate(payload)

    model = job_model_from_profile(canonical, dataset_version="1.0.0")
    restored = job_record_from_model(model)

    assert restored.to_canonical_profile() == canonical
