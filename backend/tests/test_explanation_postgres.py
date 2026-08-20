from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm.exc import DetachedInstanceError


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _alembic(revision: str, *, downgrade: bool = False) -> None:
    from app.core.config import get_settings

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = str(TEST_DATABASE_URL)
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("prepend_sys_path", str(BACKEND_ROOT))
    try:
        (command.downgrade if downgrade else command.upgrade)(config, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


async def _engine_and_factory():
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _truncate(engine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE match_explanations, explanation_runs, run_steps, "
                "match_results, match_runs, candidate_project_evidence, "
                "candidate_projects, candidate_skills, candidate_profiles, "
                "job_requirements, job_profiles CASCADE"
            )
        )


async def _source_run(factory, suffix: str, *, candidate_count: int = 1):
    from app.models.candidate import CandidateProfileModel
    from app.models.job import JobProfileModel
    from app.models.match_run import MatchResultModel, MatchRunModel

    run_id = f"00000000-0000-0000-0000-{int(suffix):012d}"
    job_id = f"job_usr_phase9_{suffix}"
    candidates = [f"cand_usr_phase9_{suffix}_{index}" for index in range(1, candidate_count + 1)]
    now = datetime.now(timezone.utc)
    async with factory() as session:
        async with session.begin():
            session.add(
                JobProfileModel(
                    job_id=job_id,
                    company_name="Synthetic Phase Nine Labs",
                    role_title="AI Engineer",
                    raw_jd="Synthetic job profile used only for Phase 9 persistence tests.",
                    product_stage="zero_to_one",
                    data_origin="user_created",
                    schema_version="1.0",
                    dataset_version=None,
                    dataset_archetype=None,
                    role_direction=["applied_ai"],
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
            for candidate_id in candidates:
                session.add(
                    CandidateProfileModel(
                        candidate_id=candidate_id,
                        name="Phase Nine Candidate",
                        raw_text="Synthetic Candidate used only for Phase 9 persistence tests.",
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
            run = MatchRunModel(
                run_id=run_id,
                requested_job_id=job_id,
                job_id=job_id,
                request_id=f"request-{suffix}",
                ranking_variant="ltr",
                status="COMPLETED",
                started_at=now,
                completed_at=now,
                request_parameters={"candidate_pool_k": 20, "top_k": 10},
                workflow_version="match_run_workflow_v1",
                workflow_fingerprint="1" * 64,
                ranking_input_contract_version="ranking_input_snapshot_v1",
                ranking_input_fingerprint="2" * 64,
                ranking_input_snapshot={
                    "contract_version": "ranking_input_snapshot_v1",
                    "job_id": job_id,
                },
                retrieval_document_version="retrieval_doc_v4",
                retrieval_configuration_fingerprint="3" * 64,
                retrieval_provenance={"index_freshness": "current"},
                feature_version="feature_schema_v1",
                feature_fingerprint="4" * 64,
                ranker_version="ltr_ranker_v1",
                ranker_model_sha256="5" * 64,
                result_count=candidate_count,
                result_fingerprint="6" * 64,
            )
            session.add(run)
            results = []
            for rank, candidate_id in enumerate(candidates, 1):
                result = MatchResultModel(
                    run_id=run_id,
                    candidate_id=candidate_id,
                    result_rank=rank,
                    candidate_input_contract_version="candidate_input_snapshot_v1",
                    candidate_input_fingerprint=f"{rank}" * 64,
                    candidate_input_snapshot={
                        "contract_version": "candidate_input_snapshot_v1",
                        "candidate_id": candidate_id,
                    },
                    retrieval_rank=rank,
                    matched_channels=["dense", "sparse"],
                    dense_rank=rank,
                    dense_score=0.30000000000000004,
                    sparse_rank=rank,
                    sparse_score=4.5,
                    fusion_score=0.0325,
                    semantic_score=0.30000000000000004,
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
                        "matched_must_have_requirement_ids": ["req_python"],
                    },
                    ltr_rank=rank,
                    ltr_score_raw=0.3125 - rank / 100,
                )
                session.add(result)
                results.append(result)
        for result in results:
            assert result.id is not None
    return run_id, job_id, candidates, results


def _candidate_evidence(candidate_id: str, rank: int) -> dict:
    return {
        "candidate_id": candidate_id,
        "result_rank": rank,
        "target_roles": ["AI Engineer"],
        "skills": [
            {
                "evidence_id": f"candidate:{rank}:skill:0123456789abcdef0123456789abcde{rank}",
                "name": "Python",
                "category": "backend",
            }
        ],
        "projects": [
            {
                "evidence_id": f"candidate:{rank}:project:project_{rank:03d}",
                "project_id": f"project_{rank:03d}",
                "technologies": ["Python"],
                "skills_demonstrated": ["Python"],
            }
        ],
        "project_evidence": [
            {
                "evidence_id": (
                    f"candidate:{rank}:project_evidence:evidence_{rank:03d}"
                ),
                "source_evidence_id": f"evidence_{rank:03d}",
                "project_id": f"project_{rank:03d}",
                "supports_skills": ["Python"],
                "verification_status": "described",
                "evidence_type": "readme",
            }
        ],
        "ai_tools": ["structured outputs"],
        "preferred_locations": {
            "cities": ["Shanghai"],
            "remote_policy": "hybrid",
            "relocation_open": True,
        },
        "seniority": "senior",
        "team_stage_preference": ["zero_to_one"],
        "overclaim_risk": {"level": "low", "reason_count": 0},
        "facts": [
            {
                "evidence_id": f"retrieval:{rank}:retrieval_rank",
                "kind": "retrieval", "candidate_id": candidate_id,
                "name": "retrieval_rank", "value": rank,
            },
            {
                "evidence_id": f"retrieval:{rank}:matched_channels",
                "kind": "retrieval", "candidate_id": candidate_id,
                "name": "matched_channels", "value": ["dense", "sparse"],
            },
            {
                "evidence_id": f"retrieval:{rank}:dense_score",
                "kind": "retrieval", "candidate_id": candidate_id,
                "name": "dense_score", "value": 0.4,
            },
            {
                "evidence_id": f"retrieval:{rank}:sparse_score",
                "kind": "retrieval", "candidate_id": candidate_id,
                "name": "sparse_score", "value": 0.3,
            },
            {
                "evidence_id": f"retrieval:{rank}:fusion_score",
                "kind": "retrieval", "candidate_id": candidate_id,
                "name": "fusion_score", "value": 0.2,
            },
            {
                "evidence_id": f"ranking:{rank}:result_rank",
                "kind": "ranking",
                "candidate_id": candidate_id,
                "name": "result_rank",
                "value": rank,
            },
            {
                "evidence_id": f"ranking:{rank}:ltr_rank",
                "kind": "ranking", "candidate_id": candidate_id,
                "name": "ltr_rank", "value": rank,
            },
            {
                "evidence_id": f"ranking:{rank}:ltr_score_raw",
                "kind": "ranking", "candidate_id": candidate_id,
                "name": "ltr_score_raw", "value": 0.5,
            },
            {
                "evidence_id": f"feature:{rank}:skill_fit_score",
                "kind": "feature",
                "candidate_id": candidate_id,
                "name": "skill_fit_score",
                "value": 0.30000000000000004,
            },
            *[
                {
                    "evidence_id": f"feature:{rank}:{name}", "kind": "feature",
                    "candidate_id": candidate_id, "name": name, "value": 0.1,
                }
                for name in (
                    "semantic_score", "sparse_score", "project_evidence_score",
                    "role_direction_score", "ai_tool_score", "location_score",
                    "seniority_score", "missing_penalty", "overclaim_penalty",
                )
            ],
            {
                "evidence_id": f"diagnostic:{rank}:location_relation",
                "kind": "diagnostic", "candidate_id": candidate_id,
                "name": "location_relation", "value": "exact_match",
            },
            *(
                [
                    {
                        "evidence_id": f"comparison:{rank}:top1:result_rank",
                        "kind": "comparison", "candidate_id": candidate_id,
                        "comparison_candidate_id": candidate_id.rsplit("_", 1)[0] + "_1",
                        "name": "result_rank", "value": 1,
                    },
                    {
                        "evidence_id": f"comparison:{rank}:top1:skill_fit_score",
                        "kind": "comparison", "candidate_id": candidate_id,
                        "comparison_candidate_id": candidate_id.rsplit("_", 1)[0] + "_1",
                        "name": "skill_fit_score", "value": 0.1,
                    },
                ]
                if rank > 1 else []
            ),
        ],
    }


def _evidence(run_id: str, job_id: str, candidates: list[str]):
    from app.schemas.explanations import InternalEvidenceBundleV1
    from app.services.explanation.contracts import project_provider_evidence

    requirement = {
        "evidence_id": "job_requirement:req_python",
        "requirement_id": "req_python",
        "priority": "must_have",
        "category": "skill",
        "text": "Strong Python engineering skills",
        "evidence_expectation": "A structured project evidence record",
    }
    provider_job = {
        "role_title": "AI Engineer",
        "role_direction": ["applied_ai"],
        "requirements": [requirement],
        "location": {
            "cities": ["Shanghai"],
            "remote_policy": "hybrid",
            "relocation_supported": True,
        },
        "seniority_requirement": ["senior"],
        "product_stage": "zero_to_one",
    }
    candidate_values = [
        _candidate_evidence(candidate_id, rank)
        for rank, candidate_id in enumerate(candidates, 1)
    ]
    internal = InternalEvidenceBundleV1.model_validate(
        {
            "contract_version": "evidence_bundle_v1",
            "source": {
                "match_run_id": run_id,
                "ranking_variant": "ltr",
                "workflow_version": "match_run_workflow_v1",
                "workflow_fingerprint": "1" * 64,
                "ranking_input_fingerprint": "2" * 64,
                "result_fingerprint": "6" * 64,
            },
            "job": {"job_id": job_id, **provider_job},
            "runtime_provenance": {
                "retrieval_document_version": "retrieval_doc_v4",
                "retrieval_configuration_fingerprint": "3" * 64,
                "feature_version": "feature_schema_v1",
                "feature_fingerprint": "4" * 64,
                "ranker_version": "ltr_ranker_v1",
                "ranker_model_sha256": "5" * 64,
                "cross_encoder": None,
            },
            "workflow_trace": [
                {"sequence": 1, "step_name": "resolve_inputs", "status": "COMPLETED"}
            ],
            "candidates": candidate_values,
        }
    )
    provider = project_provider_evidence(internal)
    return internal, provider


def _output(candidate_id: str, rank: int):
    from app.schemas.explanations import CandidateExplanationOutput

    payload = {
        "output_schema_version": "explanation_output_v1",
        "candidate_id": candidate_id,
        "result_rank": rank,
        "summary": {
            "text": "The persisted evidence supports the recorded match.",
            "evidence_refs": ["job_requirement:req_python"],
        },
        "match_reasons": [
            {
                "category": "skill_alignment",
                "text": "The required structured skill is present.",
                "evidence_refs": ["job_requirement:req_python"],
            },
            {
                "category": "ranking_context",
                "text": "This is the persisted result position.",
                "evidence_refs": [f"ranking:{rank}:result_rank"],
            },
        ],
        "risk_points": [],
        "missing_skills": [],
        "interview_questions": [],
        "why_not_top1": None
        if rank == 1
        else {
            "category": "ranking_comparison",
            "text": "This result is below the persisted top-ranked Candidate.",
            "evidence_refs": [f"comparison:{rank}:top1:skill_fit_score"],
        },
        "profile_rewrite_suggestion": None,
    }
    return CandidateExplanationOutput.model_validate(payload)


def _running(explanation_run_id: str, match_run_id: str, top_k: int = 5):
    from app.models.explanation_run import ExplanationRunModel

    return ExplanationRunModel(
        explanation_run_id=explanation_run_id,
        match_run_id=match_run_id,
        request_id=f"request-{explanation_run_id}",
        status="RUNNING",
        requested_top_k=top_k,
        explanation_count=0,
        attempt_count=0,
        repaired=False,
    )


def _explanation(explanation_run_id: str, source_result, output, *, id_=None):
    from app.models.explanation_run import MatchExplanationModel
    from app.services.explanation.contracts import candidate_output_fingerprint

    return MatchExplanationModel(
        id=id_,
        explanation_run_id=explanation_run_id,
        match_result_id=source_result.id,
        candidate_id=source_result.candidate_id,
        result_rank=source_result.result_rank,
        output_schema_version="explanation_output_v1",
        validated_output_json=output.model_dump(mode="json", exclude_none=False),
        candidate_output_fingerprint=candidate_output_fingerprint(output),
    )


def _completion_values() -> dict:
    return {
        "completed_at": datetime.now(timezone.utc),
        "provider_kind": "structured_output",
        "provider_name": "offline_contract_provider",
        "configured_model": "contract-model-v1",
        "observed_model": "contract-model-v1",
        "provider_configuration_fingerprint": "7" * 64,
        "prompt_version": "explanation_prompt_v1",
        "prompt_fingerprint": "8" * 64,
        "attempt_count": 1,
        "repaired": False,
    }


def test_postgres_fresh_and_phase8_to_phase9_upgrade_paths() -> None:
    _alembic("base", downgrade=True)
    _alembic("head")

    async def fresh_schema():
        engine, _factory = await _engine_and_factory()
        try:
            async with engine.connect() as connection:
                tables = await connection.run_sync(
                    lambda sync: set(inspect(sync).get_table_names())
                )
                columns = await connection.run_sync(
                    lambda sync: {
                        item["name"]
                        for item in inspect(sync).get_columns("explanation_runs")
                    }
                )
            assert {"explanation_runs", "match_explanations"} <= tables
            assert columns == set(
                __import__(
                    "app.models.explanation_run", fromlist=["ExplanationRunModel"]
                ).ExplanationRunModel.__table__.columns.keys()
            )
        finally:
            await engine.dispose()

    asyncio.run(fresh_schema())

    _alembic("20260818_0002", downgrade=True)

    async def seed_phase8():
        engine, factory = await _engine_and_factory()
        try:
            async with engine.connect() as connection:
                tables = await connection.run_sync(
                    lambda sync: set(inspect(sync).get_table_names())
                )
            assert "explanation_runs" not in tables
            await _source_run(factory, "920", candidate_count=1)
        finally:
            await engine.dispose()

    asyncio.run(seed_phase8())
    _alembic("head")

    async def verify_phase8_survived():
        engine, _factory = await _engine_and_factory()
        try:
            async with engine.connect() as connection:
                run_count = await connection.scalar(text("SELECT count(*) FROM match_runs"))
                result_count = await connection.scalar(text("SELECT count(*) FROM match_results"))
                fingerprint = await connection.scalar(
                    text("SELECT result_fingerprint FROM match_runs LIMIT 1")
                )
            assert run_count == result_count == 1
            assert fingerprint == "6" * 64
        finally:
            await engine.dispose()

    asyncio.run(verify_phase8_survived())


def test_postgres_atomic_completion_roundtrip_and_terminal_immutability() -> None:
    async def scenario():
        from app.exceptions import ExplanationRunConflictError
        from app.repositories.explanation_run_repository import ExplanationRunRepository
        from app.models.match_run import MatchRunModel

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, job_id, candidates, results = await _source_run(
                factory, "921", candidate_count=1
            )
            async with factory() as session:
                source_before = await session.get(MatchRunModel, run_id)
                frozen_state = (
                    source_before.status,
                    source_before.result_count,
                    source_before.result_fingerprint,
                )

            repository = ExplanationRunRepository(factory)
            explanation_run_id = "10000000-0000-0000-0000-000000000921"
            await repository.create_running(_running(explanation_run_id, run_id))
            internal, provider = _evidence(run_id, job_id, candidates)
            await repository.store_evidence(
                explanation_run_id,
                evidence_bundle=internal,
                provider_evidence=provider,
            )
            output = _output(candidates[0], 1)
            await repository.finalize_completed(
                explanation_run_id,
                [_explanation(explanation_run_id, results[0], output)],
                **_completion_values(),
            )

            stored = await repository.get_by_explanation_run_id(
                explanation_run_id,
                include_payloads=True,
                include_explanations=True,
            )
            assert stored.status == "COMPLETED"
            assert stored.explanation_count == stored.effective_top_k == 1
            assert len(stored.explanations) == 1
            assert (
                stored.provider_evidence_json["candidates"][0]["features"]
                ["skill_fit_score"]["value"]
                == 0.30000000000000004
            )
            assert stored.result_fingerprint is not None

            summary = await repository.get_by_explanation_run_id(explanation_run_id)
            with pytest.raises(DetachedInstanceError):
                _ = summary.evidence_bundle_json

            with pytest.raises(ExplanationRunConflictError):
                await repository.finalize_failed(
                    explanation_run_id,
                    completed_at=datetime.now(timezone.utc),
                    error_code="late_failure",
                    error_detail_safe="A late failure cannot mutate a terminal run",
                )

            async with factory() as session:
                source_after = await session.get(MatchRunModel, run_id)
                assert (
                    source_after.status,
                    source_after.result_count,
                    source_after.result_fingerprint,
                ) == frozen_state

            async with factory() as session:
                with pytest.raises(IntegrityError):
                    async with session.begin():
                        await session.execute(
                            delete(type(results[0])).where(
                                type(results[0]).id == results[0].id
                            )
                        )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_atomic_insert_failure_rolls_back_then_failure_is_durable() -> None:
    async def scenario():
        from app.models.explanation_run import MatchExplanationModel
        from app.repositories.explanation_run_repository import ExplanationRunRepository

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, job_id, candidates, results = await _source_run(
                factory, "922", candidate_count=2
            )
            repository = ExplanationRunRepository(factory)
            explanation_run_id = "10000000-0000-0000-0000-000000000922"
            await repository.create_running(
                _running(explanation_run_id, run_id, top_k=2)
            )
            internal, provider = _evidence(run_id, job_id, candidates)
            await repository.store_evidence(
                explanation_run_id,
                evidence_bundle=internal,
                provider_evidence=provider,
            )
            explanations = [
                _explanation(
                    explanation_run_id,
                    result,
                    _output(candidate_id, rank),
                    id_=777,
                )
                for rank, (candidate_id, result) in enumerate(
                    zip(candidates, results), 1
                )
            ]
            with pytest.raises(IntegrityError):
                await repository.finalize_completed(
                    explanation_run_id, explanations, **_completion_values()
                )

            stored = await repository.get_by_explanation_run_id(explanation_run_id)
            assert stored.status == "RUNNING"
            async with factory() as session:
                assert (
                    await session.scalar(
                        select(func.count()).select_from(MatchExplanationModel)
                    )
                    == 0
                )

            await repository.finalize_failed(
                explanation_run_id,
                completed_at=datetime.now(timezone.utc),
                error_code="explanation_persistence_failed",
                error_detail_safe="Atomic Candidate explanation persistence failed",
            )
            failed = await repository.get_by_explanation_run_id(explanation_run_id)
            assert failed.status == "FAILED"
            assert failed.error_code == "explanation_persistence_failed"
            assert failed.error_detail_safe == (
                "Atomic Candidate explanation persistence failed"
            )
            assert failed.explanation_count == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_named_constraints_enforce_uniqueness_and_lifecycle() -> None:
    async def scenario():
        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, _job_id, candidates, results = await _source_run(
                factory, "923", candidate_count=2
            )
            async with engine.connect() as connection:
                foreign_keys = await connection.run_sync(
                    lambda sync: {
                        item["name"]
                        for item in inspect(sync).get_foreign_keys("match_explanations")
                    }
                )
                unique_constraints = await connection.run_sync(
                    lambda sync: {
                        item["name"]
                        for item in inspect(sync).get_unique_constraints(
                            "match_explanations"
                        )
                    }
                )
            assert {
                "fk_match_explanations_explanation_run_id_explanation_runs",
                "fk_match_explanations_match_result_id_match_results",
            } <= foreign_keys
            assert {
                "uq_match_explanations_candidate",
                "uq_match_explanations_rank",
                "uq_match_explanations_match_result",
            } <= unique_constraints

            invalid = _running(
                "10000000-0000-0000-0000-000000000923", run_id, top_k=5
            )
            invalid.status = "COMPLETED"
            async with factory() as session:
                with pytest.raises(IntegrityError) as error:
                    async with session.begin():
                        session.add(invalid)
                        await session.flush()
            assert error.value.orig.__cause__.constraint_name == (
                "ck_explanation_runs_completed_state"
            )

            from app.models.explanation_run import MatchExplanationModel
            from app.repositories.explanation_run_repository import (
                ExplanationRunRepository,
            )

            repository = ExplanationRunRepository(factory)
            explanation_run_id = "10000000-0000-0000-0000-000000000924"
            await repository.create_running(
                _running(explanation_run_id, run_id, top_k=2)
            )

            def child(match_result, candidate_id: str, rank: int):
                return MatchExplanationModel(
                    explanation_run_id=explanation_run_id,
                    match_result_id=match_result.id,
                    candidate_id=candidate_id,
                    result_rank=rank,
                    output_schema_version="explanation_output_v1",
                    validated_output_json={},
                    candidate_output_fingerprint="9" * 64,
                )

            async with factory() as session:
                with pytest.raises(IntegrityError) as duplicate_candidate:
                    async with session.begin():
                        session.add_all(
                            [
                                child(results[0], candidates[0], 1),
                                child(results[1], candidates[0], 2),
                            ]
                        )
                        await session.flush()
            assert duplicate_candidate.value.orig.__cause__.constraint_name == (
                "uq_match_explanations_candidate"
            )

            async with factory() as session:
                with pytest.raises(IntegrityError) as duplicate_rank:
                    async with session.begin():
                        session.add_all(
                            [
                                child(results[0], candidates[0], 1),
                                child(results[1], candidates[1], 1),
                            ]
                        )
                        await session.flush()
            assert duplicate_rank.value.orig.__cause__.constraint_name == (
                "uq_match_explanations_rank"
            )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_rejects_every_provider_visible_projection_mismatch() -> None:
    async def scenario():
        from app.exceptions import ExplanationRunConflictError
        from app.repositories.explanation_run_repository import ExplanationRunRepository
        from app.schemas.explanations import ProviderEvidenceV1

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, job_id, candidates, _results = await _source_run(
                factory, "925", candidate_count=2
            )
            repository = ExplanationRunRepository(factory)
            explanation_run_id = "10000000-0000-0000-0000-000000000925"
            await repository.create_running(_running(explanation_run_id, run_id, top_k=2))
            internal, provider = _evidence(run_id, job_id, candidates)
            base = provider.model_dump(mode="json", exclude_none=False)

            mutations = []
            skill = deepcopy(base)
            skill["candidates"][0]["skills"][0]["category"] = "data"
            mutations.append(skill)
            project_status = deepcopy(base)
            project_status["candidates"][0]["project_evidence"][0][
                "verification_status"
            ] = "available"
            mutations.append(project_status)
            project = deepcopy(base)
            project["candidates"][0]["projects"][0]["project_id"] = "project_900"
            project["candidates"][0]["project_evidence"][0]["project_id"] = "project_900"
            mutations.append(project)
            retrieval = deepcopy(base)
            retrieval["candidates"][0]["retrieval"]["fusion_score"]["value"] = 0.01
            mutations.append(retrieval)
            feature = deepcopy(base)
            feature["candidates"][0]["features"]["skill_fit_score"]["value"] = 0.01
            mutations.append(feature)
            diagnostic = deepcopy(base)
            diagnostic["candidates"][0]["diagnostics"]["location_relation"]["value"] = "mismatch"
            mutations.append(diagnostic)
            ranking = deepcopy(base)
            ranking["candidates"][0]["ranking"]["ltr_score_raw"]["value"] = 0.01
            mutations.append(ranking)
            ce = deepcopy(base)
            ce["candidates"][0]["ranking"]["cross_encoder_rank"] = {
                "evidence_id": "ranking:1:cross_encoder_rank", "value": 1
            }
            ce["candidates"][0]["ranking"]["cross_encoder_score_raw"] = {
                "evidence_id": "ranking:1:cross_encoder_score_raw", "value": 0.1
            }
            mutations.append(ce)
            comparison = deepcopy(base)
            comparison["candidates"][1]["top1_comparison"]["result_rank"]["value"] = 2
            mutations.append(comparison)
            requirement = deepcopy(base)
            requirement["job"]["requirements"][0]["priority"] = "nice_to_have"
            mutations.append(requirement)

            for payload in mutations:
                with pytest.raises(
                    ExplanationRunConflictError,
                    match="grounded projection",
                ):
                    await repository.store_evidence(
                        explanation_run_id,
                        evidence_bundle=internal,
                        provider_evidence=ProviderEvidenceV1.model_validate(payload),
                    )

            stored = await repository.get_by_explanation_run_id(
                explanation_run_id, include_payloads=True
            )
            assert stored.status == "RUNNING"
            assert stored.evidence_bundle_json is None
            assert stored.provider_evidence_json is None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_complete_vs_fail_race_preserves_one_terminal_state() -> None:
    async def scenario():
        from app.exceptions import ExplanationRunConflictError
        from app.repositories.explanation_run_repository import ExplanationRunRepository

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, job_id, candidates, results = await _source_run(
                factory, "926", candidate_count=1
            )
            completing = ExplanationRunRepository(factory)
            failing = ExplanationRunRepository(factory)
            explanation_run_id = "10000000-0000-0000-0000-000000000926"
            await completing.create_running(_running(explanation_run_id, run_id))
            internal, provider = _evidence(run_id, job_id, candidates)
            await completing.store_evidence(
                explanation_run_id,
                evidence_bundle=internal,
                provider_evidence=provider,
            )

            lock_acquired = asyncio.Event()
            release_completion = asyncio.Event()
            failure_backend_pid = asyncio.get_running_loop().create_future()
            complete_running = completing._running
            fail_running = failing._running

            async def hold_completion_lock(session, run_id_value):
                run = await complete_running(session, run_id_value)
                lock_acquired.set()
                await release_completion.wait()
                return run

            async def signal_failure_attempt(session, run_id_value):
                pid = await session.scalar(text("SELECT pg_backend_pid()"))
                failure_backend_pid.set_result(pid)
                return await fail_running(session, run_id_value)

            completing._running = hold_completion_lock
            failing._running = signal_failure_attempt
            output = _output(candidates[0], 1)
            complete_task = asyncio.create_task(
                completing.finalize_completed(
                    explanation_run_id,
                    [_explanation(explanation_run_id, results[0], output)],
                    **_completion_values(),
                )
            )
            await lock_acquired.wait()
            fail_task = asyncio.create_task(
                failing.finalize_failed(
                    explanation_run_id,
                    completed_at=datetime.now(timezone.utc),
                    error_code="concurrent_failure",
                    error_detail_safe="Concurrent terminal failure",
                )
            )
            pid = await failure_backend_pid

            async def wait_until_postgres_reports_lock_contention():
                while True:
                    async with engine.connect() as observer:
                        blocked = await observer.scalar(
                            text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                            {"pid": pid},
                        )
                    if blocked:
                        return
                    await asyncio.sleep(0)

            await asyncio.wait_for(
                wait_until_postgres_reports_lock_contention(), timeout=5
            )
            release_completion.set()

            complete_result, fail_result = await asyncio.gather(
                complete_task, fail_task, return_exceptions=True
            )
            assert complete_result is None
            assert isinstance(fail_result, ExplanationRunConflictError)

            stored = await completing.get_by_explanation_run_id(
                explanation_run_id, include_explanations=True
            )
            assert stored.status == "COMPLETED"
            assert stored.explanation_count == 1
            assert len(stored.explanations) == 1
            assert stored.error_code is None
        finally:
            await engine.dispose()

    asyncio.run(scenario())
