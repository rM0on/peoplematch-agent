from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import event


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


async def _context():
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE run_steps, match_results, match_runs, "
                "candidate_project_evidence, candidate_projects, candidate_skills, "
                "candidate_profiles, job_requirements, job_profiles CASCADE"
            )
        )
    return engine, factory


async def _profiles(factory, suffix: str, *, referenced: bool = True):
    from app.models.candidate import CandidateProfileModel
    from app.models.job import JobProfileModel

    candidate_id = f"cand_usr_phase8_{suffix}"
    job_id = f"job_usr_phase8_{suffix}"
    async with factory() as session:
        async with session.begin():
            session.add(
                CandidateProfileModel(
                    candidate_id=candidate_id,
                    name="Phase Eight Candidate",
                    raw_text="Synthetic user profile for persistence integration testing.",
                    github_url=None,
                    seniority="senior",
                    data_origin="user_created",
                    schema_version="1.0",
                    dataset_version=None,
                    dataset_archetype=None,
                    ai_tools=["structured outputs"],
                    target_roles=["AI Engineer"],
                    missing_fields=[],
                    preferred_locations={
                        "cities": ["Shanghai"],
                        "remote_policy": "hybrid",
                        "relocation_open": True,
                    },
                    work_style={
                        "team_stage_preference": ["zero_to_one"],
                        "collaboration_style": "cross functional",
                    },
                    overclaim_risk={"level": "low", "reasons": []},
                )
            )
            session.add(
                JobProfileModel(
                    job_id=job_id,
                    company_name="Synthetic Phase Eight Labs",
                    role_title="AI Engineer",
                    raw_jd="Synthetic job profile used only for persistence integration testing.",
                    product_stage="zero_to_one",
                    data_origin="user_created",
                    schema_version="1.0",
                    dataset_version=None,
                    dataset_archetype=None,
                    role_direction=["ai_product"],
                    team_tags=["synthetic"],
                    seniority_requirement=["senior"],
                    evaluation_focus=["project evidence"],
                    location={
                        "cities": ["Shanghai"],
                        "remote_policy": "hybrid",
                        "relocation_supported": True,
                    },
                )
            )
    return candidate_id, job_id


def _run(run_id: str, job_id: str):
    from app.models.match_run import MatchRunModel
    from app.services.match_runs.contracts import (
        RANKER_MODEL_SHA256,
        RANKING_INPUT_CONTRACT_VERSION,
        RETRIEVAL_CONFIGURATION_FINGERPRINT,
        WORKFLOW_FINGERPRINT,
        WORKFLOW_VERSION,
    )
    from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION
    from app.services.ranking.contract import RANKER_VERSION
    from app.services.retrieval.documents import RETRIEVAL_DOCUMENT_VERSION

    now = datetime.now(timezone.utc)
    return MatchRunModel(
        run_id=run_id,
        requested_job_id=job_id,
        job_id=None,
        request_id=f"request-{run_id}",
        ranking_variant="ltr",
        status="RUNNING",
        started_at=now,
        request_parameters={"candidate_pool_k": 20, "top_k": 10},
        workflow_version=WORKFLOW_VERSION,
        workflow_fingerprint=WORKFLOW_FINGERPRINT,
        ranking_input_contract_version=RANKING_INPUT_CONTRACT_VERSION,
        retrieval_document_version=RETRIEVAL_DOCUMENT_VERSION,
        retrieval_configuration_fingerprint=RETRIEVAL_CONFIGURATION_FINGERPRINT,
        retrieval_provenance=None,
        feature_version=FEATURE_VERSION,
        feature_fingerprint=FEATURE_FINGERPRINT,
        ranker_version=RANKER_VERSION,
        ranker_model_sha256=RANKER_MODEL_SHA256,
        result_count=0,
    )


def _step(run_id: str, sequence: int, name: str):
    from app.models.match_run import RunStepModel

    return RunStepModel(
        run_id=run_id,
        sequence=sequence,
        step_name=name,
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
        input_refs={"run_id": run_id},
        contract_version="match_run_step_refs_v1",
    )


def _result(run_id: str, candidate_id: str, rank: int = 1):
    from app.models.match_run import MatchResultModel

    return MatchResultModel(
        run_id=run_id,
        candidate_id=candidate_id,
        result_rank=rank,
        candidate_input_contract_version="candidate_input_snapshot_v1",
        candidate_input_fingerprint="a" * 64,
        candidate_input_snapshot={
            "contract_version": "candidate_input_snapshot_v1",
            "candidate_id": candidate_id,
        },
        retrieval_rank=2,
        matched_channels=["dense", "sparse"],
        dense_rank=2,
        dense_score=0.30000000000000004,
        sparse_rank=1,
        fusion_score=0.0325,
        semantic_score=0.30000000000000004,
        sparse_score=4.5,
        skill_fit_score=0.8,
        project_evidence_score=0.6,
        role_direction_score=0.7,
        ai_tool_score=0.5,
        location_score=1.0,
        seniority_score=1.0,
        missing_penalty=0.2,
        overclaim_penalty=0.0,
        feature_diagnostics_contract_version="selected_feature_diagnostics_v1",
        feature_diagnostics={
            "contract_version": "selected_feature_diagnostics_v1",
            "matched_must_have_requirement_ids": [],
        },
        ltr_rank=1,
        ltr_score_raw=0.3125,
    )


def test_postgres_phase8_migration_and_atomic_lifecycle_roundtrip() -> None:
    async def scenario():
        from app.models.match_run import MatchResultModel
        from app.repositories.match_run_repository import MatchRunRepository
        from app.services.match_runs.contracts import canonical_fingerprint

        engine, factory = await _context()
        try:
            async with engine.connect() as connection:
                tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
            assert {"match_runs", "match_results", "run_steps"} <= tables
            candidate_id, job_id = await _profiles(factory, "success")
            repository = MatchRunRepository(factory)
            run_id = "00000000-0000-0000-0000-000000000001"
            await repository.create_running(_run(run_id, job_id))
            assert (await repository.get_by_run_id(run_id)).status == "RUNNING"
            await repository.start_step(_step(run_id, 1, "resolve_inputs"))
            await repository.resolve_job(
                run_id=run_id,
                job_id=job_id,
                ranking_input_snapshot={"contract_version": "ranking_input_snapshot_v1", "job_id": job_id},
                ranking_input_fingerprint="b" * 64,
            )
            await repository.complete_step(
                run_id,
                1,
                finished_at=datetime.now(timezone.utc),
                duration_ms=1.0,
                output_refs={"job_id": job_id},
            )
            await repository.start_step(_step(run_id, 2, "phase6_ltr_rank"))
            await repository.complete_step(
                run_id,
                2,
                finished_at=datetime.now(timezone.utc),
                duration_ms=2.0,
                output_refs={"result_count": 1},
            )
            await repository.start_step(_step(run_id, 3, "persist_results"))
            result = _result(run_id, candidate_id)
            canonical = {
                "candidate_id": candidate_id,
                "result_rank": 1,
                "dense_score": result.dense_score,
                "semantic_score": result.semantic_score,
                "ltr_score_raw": result.ltr_score_raw,
            }
            result_fingerprint = canonical_fingerprint(canonical)
            await repository.finalize_results_atomically(
                run_id,
                [result],
                finished_at=datetime.now(timezone.utc),
                duration_ms=1.0,
                output_refs={"result_count": 1},
                result_fingerprint=result_fingerprint,
                ce_provenance=None,
            )
            stored = await repository.get_by_run_id(run_id)
            assert stored.status == "COMPLETED"
            assert stored.result_count == 1
            assert [step.status for step in stored.steps] == ["COMPLETED"] * 3
            assert canonical_fingerprint(
                {
                    "candidate_id": stored.results[0].candidate_id,
                    "result_rank": stored.results[0].result_rank,
                    "dense_score": stored.results[0].dense_score,
                    "semantic_score": stored.results[0].semantic_score,
                    "ltr_score_raw": stored.results[0].ltr_score_raw,
                }
            ) == result_fingerprint
            items, total = await repository.list_runs(
                limit=20, offset=0, job_id=job_id, status="COMPLETED", ranking_variant="ltr"
            )
            assert total == 1 and items[0].run_id == run_id
            from app.exceptions import MatchRunConflictError
            with pytest.raises(MatchRunConflictError):
                await repository.resolve_job(run_id=run_id, ranking_input_fingerprint="c" * 64)
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(MatchResultModel)) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_result_failure_rolls_back_and_failed_run_is_retained() -> None:
    async def scenario():
        from app.models.match_run import MatchResultModel
        from app.repositories.match_run_repository import MatchRunRepository

        engine, factory = await _context()
        try:
            candidate_id, job_id = await _profiles(factory, "failure")
            repository = MatchRunRepository(factory)
            run_id = "00000000-0000-0000-0000-000000000002"
            await repository.create_running(_run(run_id, job_id))
            await repository.resolve_job(run_id=run_id, job_id=job_id)
            await repository.start_step(_step(run_id, 1, "persist_results"))
            with pytest.raises(IntegrityError):
                await repository.finalize_results_atomically(
                    run_id,
                    [_result(run_id, candidate_id), _result(run_id, "cand_usr_missing", 2)],
                    finished_at=datetime.now(timezone.utc),
                    duration_ms=1.0,
                    output_refs={"result_count": 2},
                    result_fingerprint="d" * 64,
                    ce_provenance=None,
                )
            await repository.finalize_failed(
                run_id,
                sequence=1,
                step=_step(run_id, 1, "persist_results"),
                finished_at=datetime.now(timezone.utc),
                duration_ms=2.0,
                error_code="match_run_persistence_failed",
                error_detail_safe="Result persistence failed",
            )
            stored = await repository.get_by_run_id(run_id)
            assert stored.status == "FAILED"
            assert stored.steps[0].status == "FAILED"
            assert stored.results == []
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(MatchResultModel)) == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_cross_encoder_result_fingerprint_roundtrip() -> None:
    async def scenario():
        from app.services.match_runs.contracts import canonical_fingerprint
        from app.repositories.match_run_repository import MatchRunRepository

        engine, factory = await _context()
        try:
            candidate_id, job_id = await _profiles(factory, "ce-fingerprint")
            repository = MatchRunRepository(factory)
            run_id = "00000000-0000-0000-0000-000000000004"
            run = _run(run_id, job_id)
            run.ranking_variant = "cross_encoder_experiment"
            await repository.create_running(run)
            await repository.resolve_job(run_id=run_id, job_id=job_id)
            await repository.start_step(_step(run_id, 1, "persist_results"))
            result = _result(run_id, candidate_id)
            result.cross_encoder_rank = 1
            result.cross_encoder_score_raw = -0.0
            semantic = {
                "candidate_id": result.candidate_id,
                "result_rank": result.result_rank,
                "dense_score": result.dense_score,
                "sparse_score": result.sparse_score,
                "fusion_score": result.fusion_score,
                "semantic_score": result.semantic_score,
                "skill_fit_score": result.skill_fit_score,
                "project_evidence_score": result.project_evidence_score,
                "role_direction_score": result.role_direction_score,
                "ai_tool_score": result.ai_tool_score,
                "location_score": result.location_score,
                "seniority_score": result.seniority_score,
                "missing_penalty": result.missing_penalty,
                "overclaim_penalty": result.overclaim_penalty,
                "ltr_rank": result.ltr_rank,
                "ltr_score_raw": result.ltr_score_raw,
                "cross_encoder_rank": result.cross_encoder_rank,
                "cross_encoder_score_raw": result.cross_encoder_score_raw,
            }
            fingerprint = canonical_fingerprint(semantic)
            await repository.finalize_results_atomically(
                run_id,
                [result],
                finished_at=datetime.now(timezone.utc),
                duration_ms=1.0,
                output_refs={"result_count": 1},
                result_fingerprint=fingerprint,
                ce_provenance={"score_type": "raw_logit"},
            )
            stored = await repository.get_by_run_id(run_id)
            roundtrip = stored.results[0]
            assert canonical_fingerprint({
                "candidate_id": roundtrip.candidate_id,
                "result_rank": roundtrip.result_rank,
                "dense_score": roundtrip.dense_score,
                "sparse_score": roundtrip.sparse_score,
                "fusion_score": roundtrip.fusion_score,
                "semantic_score": roundtrip.semantic_score,
                "skill_fit_score": roundtrip.skill_fit_score,
                "project_evidence_score": roundtrip.project_evidence_score,
                "role_direction_score": roundtrip.role_direction_score,
                "ai_tool_score": roundtrip.ai_tool_score,
                "location_score": roundtrip.location_score,
                "seniority_score": roundtrip.seniority_score,
                "missing_penalty": roundtrip.missing_penalty,
                "overclaim_penalty": roundtrip.overclaim_penalty,
                "ltr_rank": roundtrip.ltr_rank,
                "ltr_score_raw": roundtrip.ltr_score_raw,
                "cross_encoder_rank": roundtrip.cross_encoder_rank,
                "cross_encoder_score_raw": roundtrip.cross_encoder_score_raw,
            }) == fingerprint
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_historical_foreign_keys_return_typed_profile_conflict() -> None:
    async def scenario():
        from app.exceptions import ProfileHistoryConflictError
        from app.repositories.candidate_repository import CandidateRepository
        from app.repositories.job_repository import JobRepository
        from app.repositories.match_run_repository import MatchRunRepository
        from app.services.candidate_service import CandidateService
        from app.services.job_service import JobService

        engine, factory = await _context()
        try:
            candidate_id, job_id = await _profiles(factory, "restrict")
            free_candidate_id, free_job_id = await _profiles(factory, "free")
            repository = MatchRunRepository(factory)
            run_id = "00000000-0000-0000-0000-000000000003"
            await repository.create_running(_run(run_id, job_id))
            await repository.resolve_job(run_id=run_id, job_id=job_id)
            await repository.start_step(_step(run_id, 1, "persist_results"))
            await repository.finalize_results_atomically(
                run_id,
                [_result(run_id, candidate_id)],
                finished_at=datetime.now(timezone.utc),
                duration_ms=1.0,
                output_refs={"result_count": 1},
                result_fingerprint="e" * 64,
                ce_provenance=None,
            )
            async with factory() as session:
                async with session.begin():
                    with pytest.raises(ProfileHistoryConflictError):
                        await CandidateService(session, CandidateRepository(session)).delete(candidate_id)
                    with pytest.raises(ProfileHistoryConflictError):
                        await JobService(session, JobRepository(session)).delete(job_id)
                    await CandidateService(session, CandidateRepository(session)).delete(free_candidate_id)
                    await JobService(session, JobRepository(session)).delete(free_job_id)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_repeatable_read_keeps_match_inputs_stable_during_concurrent_patch() -> None:
    async def scenario():
        from app.repositories.candidate_repository import CandidateRepository

        engine, factory = await _context()
        execution_engine = engine.execution_options(isolation_level="REPEATABLE READ")
        execution_factory = async_sessionmaker(execution_engine, expire_on_commit=False)
        try:
            candidate_id, _job_id = await _profiles(factory, "repeatable")
            async with execution_factory() as execution_session:
                async with execution_session.begin():
                    repository = CandidateRepository(execution_session)
                    original = await repository.get_by_id(candidate_id)
                    assert original is not None
                    original_name = original.name
                    execution_session.expire_all()

                    async with factory() as writer:
                        async with writer.begin():
                            mutable = await writer.get(
                                type(original), candidate_id
                            )
                            assert mutable is not None
                            mutable.name = "Updated after match snapshot"

                    execution_session.expire_all()
                    stable = await repository.get_by_id(candidate_id)
                    assert stable is not None
                    assert stable.name == original_name

            async with factory() as later:
                current = await later.get(type(original), candidate_id)
                assert current is not None
                assert current.name == "Updated after match snapshot"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_match_run_list_does_not_select_child_tables_but_detail_does() -> None:
    async def scenario():
        from app.repositories.match_run_repository import MatchRunRepository

        engine, factory = await _context()
        statements: list[str] = []

        def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement.lower())

        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            candidate_id, job_id = await _profiles(factory, "list-query")
            repository = MatchRunRepository(factory)
            run_id = "00000000-0000-0000-0000-000000000005"
            await repository.create_running(_run(run_id, job_id))
            await repository.resolve_job(run_id=run_id, job_id=job_id)
            await repository.start_step(_step(run_id, 1, "persist_results"))
            await repository.finalize_results_atomically(
                run_id,
                [_result(run_id, candidate_id)],
                finished_at=datetime.now(timezone.utc),
                duration_ms=1.0,
                output_refs={"result_count": 1},
                result_fingerprint="f" * 64,
                ce_provenance=None,
            )

            statements.clear()
            items, total = await repository.list_runs(limit=20, offset=0)
            assert total == 1 and items[0].run_id == run_id
            assert not any("match_results" in sql or "run_steps" in sql for sql in statements)

            statements.clear()
            detail = await repository.get_by_run_id(run_id)
            assert detail is not None
            assert len(detail.results) == 1
            assert len(detail.steps) == 1
            assert any("match_results" in sql for sql in statements)
            assert any("run_steps" in sql for sql in statements)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_profile_delete_http_conflicts_and_unreferenced_delete_succeeds() -> None:
    async def scenario():
        from fastapi.testclient import TestClient

        from app.api.dependencies import get_candidate_service, get_job_service
        from app.main import create_app
        from app.repositories.candidate_repository import CandidateRepository
        from app.repositories.job_repository import JobRepository
        from app.repositories.match_run_repository import MatchRunRepository
        from app.services.candidate_service import CandidateService
        from app.services.job_service import JobService

        engine, factory = await _context()
        try:
            candidate_id, job_id = await _profiles(factory, "http-referenced")
            free_candidate_id, free_job_id = await _profiles(factory, "http-free")
            repository = MatchRunRepository(factory)
            run_id = "00000000-0000-0000-0000-000000000006"
            await repository.create_running(_run(run_id, job_id))
            await repository.resolve_job(run_id=run_id, job_id=job_id)
            await repository.start_step(_step(run_id, 1, "persist_results"))
            await repository.finalize_results_atomically(
                run_id,
                [_result(run_id, candidate_id)],
                finished_at=datetime.now(timezone.utc),
                duration_ms=1.0,
                output_refs={"result_count": 1},
                result_fingerprint="1" * 64,
                ce_provenance=None,
            )

            class RealCandidateDeleteService:
                async def delete(self, value):
                    request_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
                    request_factory = async_sessionmaker(
                        request_engine, expire_on_commit=False
                    )
                    try:
                        async with request_factory() as session:
                            async with session.begin():
                                await CandidateService(
                                    session, CandidateRepository(session)
                                ).delete(value)
                    finally:
                        await request_engine.dispose()

            class RealJobDeleteService:
                async def delete(self, value):
                    request_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
                    request_factory = async_sessionmaker(
                        request_engine, expire_on_commit=False
                    )
                    try:
                        async with request_factory() as session:
                            async with session.begin():
                                await JobService(
                                    session, JobRepository(session)
                                ).delete(value)
                    finally:
                        await request_engine.dispose()

            app = create_app()
            app.dependency_overrides[get_candidate_service] = (
                lambda: RealCandidateDeleteService()
            )
            app.dependency_overrides[get_job_service] = lambda: RealJobDeleteService()
            with TestClient(app) as client:
                candidate_response = client.delete(f"/api/v1/candidates/{candidate_id}")
                job_response = client.delete(f"/api/v1/jobs/{job_id}")
                free_candidate_response = client.delete(
                    f"/api/v1/candidates/{free_candidate_id}"
                )
                free_job_response = client.delete(f"/api/v1/jobs/{free_job_id}")

            for response in (candidate_response, job_response):
                assert response.status_code == 409
                assert response.json()["error"]["code"] == "profile_history_conflict"
                body = response.text.lower()
                assert "integrityerror" not in body
                assert "constraint" not in body
                assert "postgresql" not in body
            assert free_candidate_response.status_code == 204
            assert free_job_response.status_code == 204

            async with factory() as session:
                from app.models.match_run import MatchResultModel, MatchRunModel

                historical = await session.scalar(
                    select(MatchResultModel).where(
                        MatchResultModel.run_id == run_id,
                        MatchResultModel.candidate_id == candidate_id,
                    )
                )
                assert historical is not None
                assert await session.get(MatchRunModel, run_id) is not None
        finally:
            await engine.dispose()

    asyncio.run(scenario())
