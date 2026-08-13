from __future__ import annotations

import json
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _candidate_payload(candidate_id: str = "cand_005") -> dict[str, object]:
    for line in (REPOSITORY_ROOT / "data/samples/candidates.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        payload = json.loads(line)
        if payload["candidate_id"] == candidate_id:
            return payload
    raise AssertionError(candidate_id)


def _job_payload(job_id: str = "job_001") -> dict[str, object]:
    for line in (REPOSITORY_ROOT / "data/samples/jobs.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        payload = json.loads(line)
        if payload["job_id"] == job_id:
            return payload
    raise AssertionError(job_id)


class FakeSession:
    @asynccontextmanager
    async def begin(self):
        yield

    @asynccontextmanager
    async def begin_nested(self):
        yield

    async def flush(self) -> None:
        return None


class FakeCandidateRepository:
    def __init__(self, model=None) -> None:
        self.model = model

    async def exists(self, candidate_id: str) -> bool:
        return self.model is not None and self.model.candidate_id == candidate_id

    async def get_by_id(self, candidate_id: str):
        if self.model is not None and self.model.candidate_id == candidate_id:
            return self.model
        return None

    def create(self, model) -> None:
        self.model = model

    def update(self, model) -> None:
        self.model = model

    async def delete(self, model) -> None:
        self.model = None


class FakeJobRepository:
    def __init__(self, model=None) -> None:
        self.model = model

    async def exists(self, job_id: str) -> bool:
        return self.model is not None and self.model.job_id == job_id

    async def get_by_id(self, job_id: str):
        if self.model is not None and self.model.job_id == job_id:
            return self.model
        return None

    def create(self, model) -> None:
        self.model = model

    def update(self, model) -> None:
        self.model = model

    async def delete(self, model) -> None:
        self.model = None


def test_candidate_service_generates_user_prefixed_id() -> None:
    from app.schemas.mutations import CandidateCreate
    from app.services.candidate_service import CandidateService

    payload = _candidate_payload()
    for key in ("candidate_id", "archetype", "data_origin", "schema_version"):
        payload.pop(key)
    service = CandidateService(FakeSession(), FakeCandidateRepository())

    created = asyncio.run(service.create(CandidateCreate.model_validate(payload)))

    assert created.candidate_id.startswith("cand_usr_")
    assert created.data_origin.value == "user_created"
    assert created.dataset_version is None
    assert created.archetype is None


def test_candidate_service_blocks_frozen_mutation() -> None:
    from app.exceptions import FrozenRecordError
    from app.persistence.mappers import candidate_model_from_profile
    from app.schemas.candidate import CandidateProfile
    from app.schemas.mutations import CandidatePatch
    from app.services.candidate_service import CandidateService

    model = candidate_model_from_profile(
        CandidateProfile.model_validate(_candidate_payload()), dataset_version="1.0.0"
    )
    service = CandidateService(FakeSession(), FakeCandidateRepository(model))

    with pytest.raises(FrozenRecordError):
        asyncio.run(service.patch("cand_005", CandidatePatch(name="Changed")))


def test_job_service_blocks_frozen_delete() -> None:
    from app.exceptions import FrozenRecordError
    from app.persistence.mappers import job_model_from_profile
    from app.schemas.job import JobProfile
    from app.services.job_service import JobService

    model = job_model_from_profile(
        JobProfile.model_validate(_job_payload()), dataset_version="1.0.0"
    )
    service = JobService(FakeSession(), FakeJobRepository(model))

    with pytest.raises(FrozenRecordError):
        asyncio.run(service.delete("job_001"))


def test_candidate_service_returns_not_found() -> None:
    from app.exceptions import ProfileNotFoundError
    from app.services.candidate_service import CandidateService

    service = CandidateService(FakeSession(), FakeCandidateRepository())

    with pytest.raises(ProfileNotFoundError):
        asyncio.run(service.get("cand_missing"))


def test_candidate_service_rejects_cross_field_domain_violation() -> None:
    from app.exceptions import DomainValidationError
    from app.schemas.mutations import CandidateCreate
    from app.services.candidate_service import CandidateService

    payload = _candidate_payload()
    for key in ("candidate_id", "archetype", "data_origin", "schema_version"):
        payload.pop(key)
    payload["project_evidence"][0]["project_id"] = "prj_missing"
    service = CandidateService(FakeSession(), FakeCandidateRepository())

    with pytest.raises(DomainValidationError):
        asyncio.run(service.create(CandidateCreate.model_validate(payload)))
