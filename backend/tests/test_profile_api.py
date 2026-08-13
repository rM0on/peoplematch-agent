from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _candidate_record():
    from app.schemas.candidate import CandidateProfile
    from app.schemas.persistence import CandidateRecord

    payload = json.loads(
        (REPOSITORY_ROOT / "data/samples/candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[4]
    )
    canonical = CandidateProfile.model_validate(payload)
    return CandidateRecord.model_validate(
        {**canonical.model_dump(mode="json"), "dataset_version": "1.0.0"}
    )


def _job_record():
    from app.schemas.job import JobProfile
    from app.schemas.persistence import JobRecord

    payload = json.loads(
        (REPOSITORY_ROOT / "data/samples/jobs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    canonical = JobProfile.model_validate(payload)
    return JobRecord.model_validate(
        {**canonical.model_dump(mode="json"), "dataset_version": "1.0.0"}
    )


class CandidateApiService:
    async def list(self, **kwargs):
        return [_candidate_record()], 48

    async def get(self, candidate_id: str):
        return _candidate_record()

    async def create(self, payload):
        record = _candidate_record().model_copy(
            update={
                "candidate_id": "cand_usr_created",
                "archetype": None,
                "data_origin": "user_created",
                "dataset_version": None,
            }
        )
        return record

    async def patch(self, candidate_id: str, payload):
        from app.exceptions import FrozenRecordError

        raise FrozenRecordError("Frozen dataset candidates are read-only")

    async def delete(self, candidate_id: str):
        return None


class JobApiService:
    async def list(self, **kwargs):
        return [_job_record()], 24

    async def get(self, job_id: str):
        return _job_record()

    async def create(self, payload):
        return _job_record().model_copy(
            update={
                "job_id": "job_usr_created",
                "archetype": None,
                "data_origin": "user_created",
                "dataset_version": None,
            }
        )

    async def patch(self, job_id: str, payload):
        return _job_record()

    async def delete(self, job_id: str):
        return None


def test_candidate_list_uses_paginated_envelope(app) -> None:
    from app.api.dependencies import get_candidate_service

    app.dependency_overrides[get_candidate_service] = lambda: CandidateApiService()
    with TestClient(app) as client:
        response = client.get("/api/v1/candidates?limit=5&offset=0&seniority=senior")

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 48
    assert response.json()["data"]["limit"] == 5
    assert response.json()["data"]["items"][0]["candidate_id"] == "cand_005"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_job_detail_preserves_requirements(app) -> None:
    from app.api.dependencies import get_job_service

    app.dependency_overrides[get_job_service] = lambda: JobApiService()
    with TestClient(app) as client:
        response = client.get("/api/v1/jobs/job_001")

    assert response.status_code == 200
    assert response.json()["data"]["job_id"] == "job_001"
    assert response.json()["data"]["must_have"][0]["requirement_id"] == "req_job_001_01"


def test_frozen_candidate_patch_returns_conflict_envelope(app) -> None:
    from app.api.dependencies import get_candidate_service

    app.dependency_overrides[get_candidate_service] = lambda: CandidateApiService()
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/candidates/cand_005", json={"name": "Candidate Changed"}
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "frozen_record"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
