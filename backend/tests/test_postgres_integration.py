from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


def _record(path: str, index: int) -> dict[str, object]:
    return json.loads(
        (REPOSITORY_ROOT / path).read_text(encoding="utf-8").splitlines()[index]
    )


def _candidate_create(suffix: str, *, nested_id_suffix: str | None = None):
    from app.schemas.mutations import CandidateCreate

    payload = _record("data/samples/candidates.jsonl", 0)
    for key in ("candidate_id", "archetype", "data_origin", "schema_version"):
        payload.pop(key)
    project_map = {}
    nested_suffix = nested_id_suffix or suffix
    for project in payload["projects"]:
        old = project["project_id"]
        new = f"prj_usr_{nested_suffix}_{len(project_map) + 1}"
        project["project_id"] = new
        project_map[old] = new
    for index, evidence in enumerate(payload["project_evidence"], start=1):
        evidence["evidence_id"] = f"ev_usr_{nested_suffix}_{index}"
        evidence["project_id"] = project_map[evidence["project_id"]]
        evidence["artifact_ref"] = f"sandbox://candidate/user/project/{suffix}/{index}"
    return CandidateCreate.model_validate(payload)


def _job_create(suffix: str, *, nested_id_suffix: str | None = None):
    from app.schemas.mutations import JobCreate

    payload = _record("data/samples/jobs.jsonl", 0)
    for key in ("job_id", "archetype", "data_origin", "schema_version"):
        payload.pop(key)
    nested_suffix = nested_id_suffix or suffix
    for group in ("must_have", "nice_to_have"):
        for index, requirement in enumerate(payload[group], start=1):
            requirement["requirement_id"] = f"req_usr_{nested_suffix}_{group}_{index}"
    return JobCreate.model_validate(payload)


async def _run_isolated(callback):
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE candidate_project_evidence, candidate_projects, "
                    "candidate_skills, candidate_profiles, job_requirements, "
                    "job_profiles CASCADE"
                )
            )
        async with session_factory() as session:
            async with session.begin():
                await callback(session)
    finally:
        await engine.dispose()


def test_postgres_seed_is_idempotent_and_roundtrips_frozen_profiles() -> None:
    from app.repositories.candidate_repository import CandidateRepository
    from app.repositories.job_repository import JobRepository
    from app.services.seed_service import seed_frozen_profiles

    async def scenario(session):
        first = await seed_frozen_profiles(session, REPOSITORY_ROOT)
        second = await seed_frozen_profiles(session, REPOSITORY_ROOT)
        assert (first.candidates_inserted, first.jobs_inserted) == (48, 24)
        assert (second.candidates_unchanged, second.jobs_unchanged) == (48, 24)
        candidate = await CandidateRepository(session).get_by_id("cand_005")
        job = await JobRepository(session).get_by_id("job_001")
        assert len(candidate.skills) == 6
        assert len(candidate.projects) == 2
        assert len(candidate.evidence) == 6
        assert len(job.requirements) == 9

    asyncio.run(_run_isolated(scenario))


def test_postgres_candidate_crud_filters_and_cascade_delete() -> None:
    from app.models.candidate import (
        CandidateProfileModel,
        CandidateProjectEvidenceModel,
        CandidateProjectModel,
        CandidateSkillModel,
    )
    from app.repositories.candidate_repository import CandidateRepository
    from app.schemas.mutations import CandidatePatch
    from app.services.candidate_service import CandidateService

    async def scenario(session):
        service = CandidateService(session, CandidateRepository(session))
        created = await service.create(_candidate_create("crud"))
        items, total = await service.list(
            limit=20,
            offset=0,
            seniority=created.seniority.value,
            city=created.preferred_locations.cities[0],
            target_role=created.target_roles[0],
        )
        assert total == 1
        assert items[0].candidate_id == created.candidate_id
        patched = await service.patch(
            created.candidate_id, CandidatePatch(name="Synthetic User Candidate")
        )
        assert patched.name == "Synthetic User Candidate"
        projects = [project.model_copy(update={"summary": f"{project.summary} Updated."}) for project in patched.projects]
        patched = await service.patch(
            created.candidate_id,
            CandidatePatch(projects=projects, project_evidence=patched.project_evidence),
        )
        assert patched.projects[0].project_id == created.projects[0].project_id
        assert patched.projects[0].summary.endswith("Updated.")
        await service.delete(created.candidate_id)
        for model in (
            CandidateProfileModel,
            CandidateSkillModel,
            CandidateProjectModel,
            CandidateProjectEvidenceModel,
        ):
            assert await session.scalar(select(func.count()).select_from(model)) == 0

    asyncio.run(_run_isolated(scenario))


def test_postgres_job_crud_filters_and_cascade_delete() -> None:
    from app.models.job import JobProfileModel, JobRequirementModel
    from app.repositories.job_repository import JobRepository
    from app.schemas.mutations import JobPatch
    from app.services.job_service import JobService

    async def scenario(session):
        service = JobService(session, JobRepository(session))
        created = await service.create(_job_create("crud"))
        items, total = await service.list(
            limit=20,
            offset=0,
            role_title="Matching",
            role_direction=created.role_direction[0],
            city=created.location.cities[0],
            seniority=created.seniority_requirement[0].value,
        )
        assert total == 1
        assert items[0].job_id == created.job_id
        patched = await service.patch(
            created.job_id, JobPatch(company_name="Synthetic User Labs")
        )
        assert patched.company_name == "Synthetic User Labs"
        must_have = [
            requirement.model_copy(
                update={"evidence_expectation": f"{requirement.evidence_expectation} Reviewed."}
            )
            for requirement in patched.must_have
        ]
        patched = await service.patch(created.job_id, JobPatch(must_have=must_have))
        assert patched.must_have[0].requirement_id == created.must_have[0].requirement_id
        assert patched.must_have[0].evidence_expectation.endswith("Reviewed.")
        await service.delete(created.job_id)
        assert await session.scalar(select(func.count()).select_from(JobProfileModel)) == 0
        assert await session.scalar(select(func.count()).select_from(JobRequirementModel)) == 0

    asyncio.run(_run_isolated(scenario))


def test_postgres_nested_id_conflict_rolls_back_whole_profile() -> None:
    from app.exceptions import DomainValidationError
    from app.models.candidate import CandidateProfileModel
    from app.repositories.candidate_repository import CandidateRepository
    from app.services.candidate_service import CandidateService

    async def scenario(session):
        service = CandidateService(session, CandidateRepository(session))
        payload = _candidate_create("duplicate")
        projects = payload.projects.copy()
        projects[1] = projects[1].model_copy(
            update={"project_id": projects[0].project_id}
        )
        payload = payload.model_copy(update={"projects": projects})
        with pytest.raises(DomainValidationError):
            await service.create(payload)
        assert await session.scalar(select(func.count()).select_from(CandidateProfileModel)) == 0

    asyncio.run(_run_isolated(scenario))


def test_postgres_nested_identifiers_are_scoped_to_candidate_and_job() -> None:
    from app.repositories.candidate_repository import CandidateRepository
    from app.repositories.job_repository import JobRepository
    from app.services.candidate_service import CandidateService
    from app.services.job_service import JobService

    async def scenario(session):
        candidate_service = CandidateService(session, CandidateRepository(session))
        first_candidate = await candidate_service.create(
            _candidate_create("scope_a", nested_id_suffix="shared")
        )
        second_candidate = await candidate_service.create(
            _candidate_create("scope_b", nested_id_suffix="shared")
        )
        assert first_candidate.candidate_id != second_candidate.candidate_id
        assert first_candidate.projects[0].project_id == second_candidate.projects[0].project_id
        assert (
            first_candidate.project_evidence[0].evidence_id
            == second_candidate.project_evidence[0].evidence_id
        )

        job_service = JobService(session, JobRepository(session))
        first_job = await job_service.create(
            _job_create("scope_a", nested_id_suffix="shared")
        )
        second_job = await job_service.create(
            _job_create("scope_b", nested_id_suffix="shared")
        )
        assert first_job.job_id != second_job.job_id
        assert (
            first_job.must_have[0].requirement_id
            == second_job.must_have[0].requirement_id
        )

    asyncio.run(_run_isolated(scenario))


def test_nested_identifiers_remain_unique_within_their_owner() -> None:
    from app.exceptions import DomainValidationError
    from app.models.candidate import CandidateProfileModel
    from app.models.job import JobProfileModel
    from app.repositories.candidate_repository import CandidateRepository
    from app.repositories.job_repository import JobRepository
    from app.services.candidate_service import CandidateService
    from app.services.job_service import JobService

    async def scenario(session):
        candidate_payload = _candidate_create("owner_duplicate")
        evidence = candidate_payload.project_evidence.copy()
        evidence[1] = evidence[1].model_copy(
            update={"evidence_id": evidence[0].evidence_id}
        )
        with pytest.raises(DomainValidationError):
            await CandidateService(session, CandidateRepository(session)).create(
                candidate_payload.model_copy(update={"project_evidence": evidence})
            )

        job_payload = _job_create("owner_duplicate")
        must_have = job_payload.must_have.copy()
        must_have[1] = must_have[1].model_copy(
            update={"requirement_id": must_have[0].requirement_id}
        )
        with pytest.raises(DomainValidationError):
            await JobService(session, JobRepository(session)).create(
                job_payload.model_copy(update={"must_have": must_have})
            )

        assert await session.scalar(select(func.count()).select_from(CandidateProfileModel)) == 0
        assert await session.scalar(select(func.count()).select_from(JobProfileModel)) == 0

    asyncio.run(_run_isolated(scenario))


def test_postgres_candidate_nested_replacement_is_atomic_and_reference_safe() -> None:
    from app.exceptions import DomainValidationError
    from app.repositories.candidate_repository import CandidateRepository
    from app.schemas.mutations import CandidatePatch
    from app.services.candidate_service import CandidateService

    async def scenario(session):
        repository = CandidateRepository(session)
        service = CandidateService(session, repository)
        created = await service.create(_candidate_create("replacement"))
        model = await repository.get_by_id(created.candidate_id)
        initial_updated_at = model.updated_at
        original_evidence = {
            evidence.evidence_id: evidence.project_id
            for evidence in created.project_evidence
        }

        revised_projects = [
            project.model_copy(update={"summary": f"{project.summary} Revised."})
            for project in created.projects
        ]
        case_a = await service.patch(
            created.candidate_id,
            CandidatePatch(projects=revised_projects),
        )
        model = await repository.get_by_id(created.candidate_id)
        assert model.updated_at > initial_updated_at
        assert len(case_a.project_evidence) == len(created.project_evidence)
        assert {
            evidence.evidence_id: evidence.project_id
            for evidence in case_a.project_evidence
        } == original_evidence

        with pytest.raises(DomainValidationError):
            await service.patch(
                created.candidate_id,
                CandidatePatch(projects=[case_a.projects[0]]),
            )
        after_failed_patch = await service.get(created.candidate_id)
        model_after_failed_patch = await repository.get_by_id(created.candidate_id)
        case_a_updated_at = model.updated_at
        assert model_after_failed_patch.updated_at == case_a_updated_at
        assert [project.project_id for project in after_failed_patch.projects] == [
            project.project_id for project in case_a.projects
        ]
        assert {
            evidence.evidence_id: evidence.project_id
            for evidence in after_failed_patch.project_evidence
        } == original_evidence

        retained_project_id = case_a.projects[0].project_id
        case_c = await service.patch(
            created.candidate_id,
            CandidatePatch(
                projects=[case_a.projects[0]],
                project_evidence=[
                    evidence
                    for evidence in case_a.project_evidence
                    if evidence.project_id == retained_project_id
                ],
            ),
        )
        model_after_case_c = await repository.get_by_id(created.candidate_id)
        assert model_after_case_c.updated_at > case_a_updated_at
        assert [project.project_id for project in case_c.projects] == [retained_project_id]
        assert all(
            evidence.project_id == retained_project_id
            for evidence in case_c.project_evidence
        )

    asyncio.run(_run_isolated(scenario))


def test_postgres_job_partial_requirement_replacement_preserves_other_group_and_touches_parent() -> None:
    from app.repositories.job_repository import JobRepository
    from app.schemas.mutations import JobPatch
    from app.services.job_service import JobService

    async def scenario(session):
        repository = JobRepository(session)
        service = JobService(session, repository)
        created = await service.create(_job_create("replacement"))
        model = await repository.get_by_id(created.job_id)
        initial_updated_at = model.updated_at
        original_nice_to_have = created.nice_to_have
        replacement = [
            created.must_have[0].model_copy(
                update={"evidence_expectation": "A replacement synthetic expectation."}
            )
        ]

        patched = await service.patch(
            created.job_id,
            JobPatch(must_have=replacement),
        )
        model = await repository.get_by_id(created.job_id)
        assert model.updated_at > initial_updated_at
        assert patched.must_have == replacement
        assert patched.nice_to_have == original_nice_to_have

    asyncio.run(_run_isolated(scenario))


def test_postgres_candidate_api_crud_and_frozen_protection() -> None:
    from fastapi.testclient import TestClient

    from app.api.dependencies import get_db_session
    from app.main import create_app
    from app.services.seed_service import seed_frozen_profiles

    async def prepare() -> None:
        async def seed(session):
            await seed_frozen_profiles(session, REPOSITORY_ROOT)

        await _run_isolated(seed)

    asyncio.run(prepare())
    app = create_app()

    async def database_override():
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                async with session.begin():
                    yield session
        finally:
            await engine.dispose()

    app.dependency_overrides[get_db_session] = database_override
    payload = _candidate_create("api").model_dump(mode="json")
    with TestClient(app) as client:
        created_response = client.post("/api/v1/candidates", json=payload)
        assert created_response.status_code == 201
        candidate_id = created_response.json()["data"]["candidate_id"]
        assert candidate_id.startswith("cand_usr_")
        duplicate_response = client.post("/api/v1/candidates", json=payload)
        assert duplicate_response.status_code == 201
        second_candidate_id = duplicate_response.json()["data"]["candidate_id"]
        assert second_candidate_id != candidate_id
        assert (
            duplicate_response.json()["data"]["projects"][0]["project_id"]
            == created_response.json()["data"]["projects"][0]["project_id"]
        )

        list_response = client.get(
            "/api/v1/candidates",
            params={"limit": 5, "target_role": payload["target_roles"][0]},
        )
        assert list_response.status_code == 200
        page = list_response.json()["data"]
        assert page["limit"] == 5
        assert page["total"] >= 1
        last_page_response = client.get(
            "/api/v1/candidates",
            params={
                "limit": 5,
                "offset": max(page["total"] - 2, 0),
                "target_role": payload["target_roles"][0],
            },
        )
        last_page_ids = {
            item["candidate_id"]
            for item in last_page_response.json()["data"]["items"]
        }
        assert {candidate_id, second_candidate_id} <= last_page_ids
        assert client.get(f"/api/v1/candidates/{candidate_id}").status_code == 200

        patch_response = client.patch(
            f"/api/v1/candidates/{candidate_id}",
            json={"name": "API Synthetic Candidate"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["data"]["name"] == "API Synthetic Candidate"

        frozen_response = client.patch(
            "/api/v1/candidates/cand_005", json={"name": "Forbidden Change"}
        )
        assert frozen_response.status_code == 409
        assert frozen_response.json()["error"]["code"] == "frozen_record"

        assert client.delete(f"/api/v1/candidates/{candidate_id}").status_code == 204
        missing_response = client.get(f"/api/v1/candidates/{candidate_id}")
        assert missing_response.status_code == 404
        assert missing_response.json()["error"]["code"] == "profile_not_found"


def test_postgres_job_api_crud_and_frozen_protection() -> None:
    from fastapi.testclient import TestClient

    from app.api.dependencies import get_db_session
    from app.main import create_app
    from app.services.seed_service import seed_frozen_profiles

    async def prepare() -> None:
        async def seed(session):
            await seed_frozen_profiles(session, REPOSITORY_ROOT)

        await _run_isolated(seed)

    asyncio.run(prepare())
    app = create_app()

    async def database_override():
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                async with session.begin():
                    yield session
        finally:
            await engine.dispose()

    app.dependency_overrides[get_db_session] = database_override
    payload = _job_create("api").model_dump(mode="json")
    with TestClient(app) as client:
        created_response = client.post("/api/v1/jobs", json=payload)
        assert created_response.status_code == 201
        job_id = created_response.json()["data"]["job_id"]
        assert job_id.startswith("job_usr_")

        list_response = client.get(
            "/api/v1/jobs",
            params={"limit": 5, "role_title": "Matching"},
        )
        assert list_response.status_code == 200
        assert list_response.json()["data"]["total"] >= 1
        assert client.get(f"/api/v1/jobs/{job_id}").status_code == 200

        patch_response = client.patch(
            f"/api/v1/jobs/{job_id}",
            json={"company_name": "API Synthetic Labs"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["data"]["company_name"] == "API Synthetic Labs"

        frozen_response = client.delete("/api/v1/jobs/job_001")
        assert frozen_response.status_code == 409
        assert frozen_response.json()["error"]["code"] == "frozen_record"

        assert client.delete(f"/api/v1/jobs/{job_id}").status_code == 204
        missing_response = client.get(f"/api/v1/jobs/{job_id}")
        assert missing_response.status_code == 404
        assert missing_response.json()["error"]["code"] == "profile_not_found"


def test_postgres_extraction_preview_persistence_and_failed_output_are_atomic() -> None:
    from app.models.candidate import CandidateProfileModel, CandidateSkillModel
    from app.models.job import JobProfileModel, JobRequirementModel
    from app.repositories.candidate_repository import CandidateRepository
    from app.repositories.job_repository import JobRepository
    from app.schemas.mutations import CandidatePatch, JobPatch
    from app.services.candidate_service import CandidateService
    from app.services.job_service import JobService
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService
    from app.services.profile_extraction.provider import MOCK_PROVIDER_DESCRIPTOR

    fixture_root = REPOSITORY_ROOT / "data" / "samples" / "extraction"
    candidate_source = (fixture_root / "candidate_matching_resume.txt").read_text(encoding="utf-8")
    job_source = (fixture_root / "job_matching_engineer.txt").read_text(encoding="utf-8")

    async def scenario(session):
        candidate_service = CandidateService(session, CandidateRepository(session))
        job_service = JobService(session, JobRepository(session))
        preview_service = ProfileExtractionService(
            MockStructuredOutputProvider.from_fixture_directory(fixture_root),
            MOCK_PROVIDER_DESCRIPTOR,
            candidate_service=candidate_service,
            job_service=job_service,
        )

        before_candidates = await session.scalar(select(func.count()).select_from(CandidateProfileModel))
        before_jobs = await session.scalar(select(func.count()).select_from(JobProfileModel))
        candidate_preview = await preview_service.parse_candidate(candidate_source, persist=False)
        job_preview = await preview_service.parse_job(job_source, persist=False)
        assert candidate_preview.record is None
        assert job_preview.record is None
        assert await session.scalar(select(func.count()).select_from(CandidateProfileModel)) == before_candidates
        assert await session.scalar(select(func.count()).select_from(JobProfileModel)) == before_jobs

        candidate_result = await preview_service.parse_candidate(candidate_source, persist=True)
        job_result = await preview_service.parse_job(job_source, persist=True)
        candidate = candidate_result.record
        job = job_result.record
        assert candidate.candidate_id.startswith("cand_parse_")
        assert candidate.data_origin.value == "mock_parsed"
        assert candidate.dataset_version is None and candidate.archetype is None
        assert candidate.raw_text == candidate_source
        assert candidate_result.extraction.persisted is True
        assert job.job_id.startswith("job_parse_")
        assert job.data_origin.value == "mock_parsed"
        assert job.dataset_version is None and job.archetype is None
        assert job.raw_jd == job_source
        assert job_result.extraction.persisted is True

        await candidate_service.patch(
            candidate.candidate_id,
            CandidatePatch(name="Parsed Candidate Updated"),
        )
        await job_service.patch(
            job.job_id,
            JobPatch(company_name="Parsed Job Updated"),
        )

        candidate_count = await session.scalar(select(func.count()).select_from(CandidateProfileModel))
        job_count = await session.scalar(select(func.count()).select_from(JobProfileModel))
        child_counts = (
            await session.scalar(select(func.count()).select_from(CandidateSkillModel)),
            await session.scalar(select(func.count()).select_from(JobRequirementModel)),
        )
        failing = ProfileExtractionService(
            MockStructuredOutputProvider.with_responses(["invalid", "invalid again"]),
            MOCK_PROVIDER_DESCRIPTOR,
            candidate_service=candidate_service,
            job_service=job_service,
        )
        from app.exceptions import ProviderOutputInvalidError
        with pytest.raises(ProviderOutputInvalidError):
            await failing.parse_candidate(candidate_source, persist=True)
        with pytest.raises(ProviderOutputInvalidError):
            await ProfileExtractionService(
                MockStructuredOutputProvider.with_responses(["invalid", "invalid again"]),
                MOCK_PROVIDER_DESCRIPTOR,
                candidate_service=candidate_service,
                job_service=job_service,
            ).parse_job(job_source, persist=True)
        assert await session.scalar(select(func.count()).select_from(CandidateProfileModel)) == candidate_count
        assert await session.scalar(select(func.count()).select_from(JobProfileModel)) == job_count
        assert (
            await session.scalar(select(func.count()).select_from(CandidateSkillModel)),
            await session.scalar(select(func.count()).select_from(JobRequirementModel)),
        ) == child_counts

    asyncio.run(_run_isolated(scenario))


def test_postgres_extraction_routes_preview_persist_get_and_delete() -> None:
    from fastapi.testclient import TestClient

    from app.api.dependencies import get_db_session
    from app.main import create_app

    async def prepare() -> None:
        async def no_op(_session):
            return None

        await _run_isolated(no_op)

    asyncio.run(prepare())
    app = create_app()

    async def database_override():
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                async with session.begin():
                    yield session
        finally:
            await engine.dispose()

    app.dependency_overrides[get_db_session] = database_override
    fixture_root = REPOSITORY_ROOT / "data" / "samples" / "extraction"
    candidate_source = (fixture_root / "candidate_matching_resume.txt").read_text(
        encoding="utf-8"
    )
    job_source = (fixture_root / "job_matching_engineer.txt").read_text(
        encoding="utf-8"
    )
    with TestClient(app) as client:
        candidate_preview = client.post(
            "/api/v1/candidates/parse",
            json={"text": candidate_source},
            headers={"X-Request-ID": "candidate-route-preview"},
        )
        assert candidate_preview.status_code == 200
        assert candidate_preview.headers["X-Request-ID"] == "candidate-route-preview"
        assert candidate_preview.json()["request_id"] == "candidate-route-preview"
        assert candidate_preview.json()["data"]["record"] is None

        candidate_persisted = client.post(
            "/api/v1/candidates/parse",
            json={"text": candidate_source, "persist": True},
        )
        assert candidate_persisted.status_code == 200
        candidate_record = candidate_persisted.json()["data"]["record"]
        candidate_id = candidate_record["candidate_id"]
        assert candidate_id.startswith("cand_parse_")
        assert candidate_record["data_origin"] == "mock_parsed"
        assert candidate_record["raw_text"] == candidate_source
        assert client.get(f"/api/v1/candidates/{candidate_id}").status_code == 200
        assert client.delete(f"/api/v1/candidates/{candidate_id}").status_code == 204

        job_preview = client.post(
            "/api/v1/jobs/parse",
            json={"text": job_source},
            headers={"X-Request-ID": "job-route-preview"},
        )
        assert job_preview.status_code == 200
        assert job_preview.headers["X-Request-ID"] == "job-route-preview"
        assert job_preview.json()["request_id"] == "job-route-preview"
        assert job_preview.json()["data"]["record"] is None

        job_persisted = client.post(
            "/api/v1/jobs/parse",
            json={"text": job_source, "persist": True},
        )
        assert job_persisted.status_code == 200
        job_record = job_persisted.json()["data"]["record"]
        job_id = job_record["job_id"]
        assert job_id.startswith("job_parse_")
        assert job_record["data_origin"] == "mock_parsed"
        assert job_record["raw_jd"] == job_source
        assert client.get(f"/api/v1/jobs/{job_id}").status_code == 200
        assert client.delete(f"/api/v1/jobs/{job_id}").status_code == 204
