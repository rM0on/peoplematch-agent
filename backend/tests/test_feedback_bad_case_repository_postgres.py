from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import func, select, text
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _alembic_head() -> None:
    from app.core.config import get_settings

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = str(TEST_DATABASE_URL)
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("prepend_sys_path", str(BACKEND_ROOT))
    try:
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def setup_module() -> None:
    if TEST_DATABASE_URL:
        _alembic_head()


async def _engine_and_factory():
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _truncate(engine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE bad_case_transitions, resolution_actions, "
                "bad_case_analyses, feedback_evidence_links, "
                "bad_case_source_links, bad_cases, system_signals, "
                "feedback_records, explanation_generation_attempts, "
                "match_explanations, explanation_runs, run_steps, match_results, "
                "match_runs, candidate_project_evidence, candidate_projects, "
                "candidate_skills, candidate_profiles, job_requirements, "
                "job_profiles RESTART IDENTITY CASCADE"
            )
        )


async def _completed_history(factory, suffix: str, *, candidate_count: int = 2):
    from app.repositories.explanation_run_repository import ExplanationRunRepository
    from tests.test_explanation_postgres import (
        _completion_values,
        _evidence,
        _explanation,
        _output,
        _running,
        _source_run,
    )

    run_id, job_id, candidates, results = await _source_run(
        factory, suffix, candidate_count=candidate_count
    )
    explanation_run_id = f"10000000-0000-0000-0000-{int(suffix):012d}"
    repository = ExplanationRunRepository(factory)
    await repository.create_running(
        _running(explanation_run_id, run_id, top_k=candidate_count)
    )
    bundle, provider = _evidence(run_id, job_id, candidates)
    await repository.store_evidence(
        explanation_run_id,
        evidence_bundle=bundle,
        provider_evidence=provider,
    )
    explanations = [
        _explanation(
            explanation_run_id,
            result,
            _output(result.candidate_id, result.result_rank),
        )
        for result in results
    ]
    await repository.finalize_completed(
        explanation_run_id,
        explanations,
        **_completion_values(),
    )
    stored = await repository.get_by_explanation_run_id(
        explanation_run_id, include_explanations=True
    )
    return run_id, job_id, candidates, results, stored


def _top1_feedback(run_id, job_id, result, *, feedback_id: str, supersedes=None):
    from app.models.feedback import FeedbackRecordModel

    return FeedbackRecordModel(
        feedback_id=feedback_id,
        contract_version="feedback_record_v1",
        feedback_type="ranking",
        origin="human",
        target_type="top1",
        match_run_id=run_id,
        match_result_id=result.id,
        candidate_id=result.candidate_id,
        result_rank=result.result_rank,
        job_id=job_id,
        value="wrong",
        reason_code="wrong_top1",
        comment="Historical ranking review",
        supersedes_feedback_id=supersedes,
    )


def _case(run_id, job_id, result, *, bad_case_id: str):
    from app.models.bad_case import BadCaseModel

    return BadCaseModel(
        bad_case_id=bad_case_id,
        case_contract_version="bad_case_v1",
        taxonomy_version="bad_case_taxonomy_v1",
        primary_match_run_id=run_id,
        primary_match_result_id=result.id,
        historical_job_id=job_id,
        historical_candidate_id=result.candidate_id,
        result_rank=result.result_rank,
        symptom_code="wrong_top1",
        symptom_family="RANKING",
        severity="HIGH",
        status="CREATED",
        revision=0,
    )


def test_feedback_repository_enforces_historical_ownership_and_append_only() -> None:
    async def scenario():
        from app.models.feedback import FeedbackRecordModel
        from app.models.match_run import MatchRunModel
        from app.repositories.feedback_repository import FeedbackRepository
        from app.repositories.phase10_errors import (
            HistoricalOwnerNotFoundError,
            HistoricalOwnershipError,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            first = await _completed_history(factory, "301", candidate_count=2)
            second = await _completed_history(factory, "302", candidate_count=1)
            run_id, job_id, _candidates, results, _explanation = first
            repository = FeedbackRepository(factory)

            feedback = _top1_feedback(
                run_id,
                job_id,
                results[0],
                feedback_id="30000000-0000-0000-0000-000000000301",
            )
            await repository.create(feedback)
            stored = await repository.get_by_id(feedback.feedback_id)
            assert stored.feedback_id == feedback.feedback_id
            assert stored.match_result_id == results[0].id

            wrong_top1 = _top1_feedback(
                run_id,
                job_id,
                results[1],
                feedback_id="30000000-0000-0000-0000-000000000302",
            )
            with pytest.raises(HistoricalOwnershipError, match="rank one"):
                await repository.create(wrong_top1)

            cross_run = FeedbackRecordModel(
                feedback_id="30000000-0000-0000-0000-000000000303",
                contract_version="feedback_record_v1",
                feedback_type="ranking",
                origin="human",
                target_type="pairwise",
                match_run_id=run_id,
                match_result_id=results[0].id,
                comparison_match_result_id=second[3][0].id,
                candidate_id=results[0].candidate_id,
                comparison_candidate_id=second[3][0].candidate_id,
                result_rank=1,
                comparison_result_rank=1,
                job_id=job_id,
                value="wrong",
                reason_code="ranking_inversion",
            )
            with pytest.raises(HistoricalOwnershipError, match="MatchRun"):
                await repository.create(cross_run)

            async with factory() as session:
                async with session.begin():
                    second_run = await session.get(
                        MatchRunModel, second[0]
                    )
                    second_run.status = "RUNNING"
                    second_run.completed_at = None
            with pytest.raises(HistoricalOwnershipError, match="completed"):
                await repository.resolve_match_run(second[0])
            with pytest.raises(HistoricalOwnerNotFoundError, match="not found"):
                await repository.resolve_match_run(
                    "00000000-0000-0000-0000-000000999999"
                )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_feedback_repository_validates_explanation_evidence_and_supersession() -> None:
    async def scenario():
        from app.models.feedback import FeedbackRecordModel
        from app.repositories.feedback_repository import FeedbackRepository
        from app.repositories.phase10_errors import HistoricalOwnershipError

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            first = await _completed_history(factory, "311", candidate_count=2)
            second = await _completed_history(factory, "312", candidate_count=1)
            run_id, job_id, candidates, results, explanation = first
            repository = FeedbackRepository(factory)

            explanation_feedback = FeedbackRecordModel(
                feedback_id="30000000-0000-0000-0000-000000000311",
                contract_version="feedback_record_v1",
                feedback_type="explanation",
                origin="human",
                target_type="match_reason",
                match_run_id=run_id,
                match_result_id=results[1].id,
                candidate_id=candidates[1],
                result_rank=2,
                job_id=job_id,
                explanation_run_id=explanation.explanation_run_id,
                match_explanation_id=explanation.explanations[1].id,
                value="unsupported",
                evidence_reference="candidate:2:skill:0123456789abcdef0123456789abcde2",
            )
            await repository.create(explanation_feedback)
            owner = await repository.resolve_evidence(
                explanation.explanation_run_id,
                explanation_feedback.evidence_reference,
                candidate_id=candidates[1],
                result_rank=2,
            )
            assert owner.kind == "skill"

            with pytest.raises(HistoricalOwnershipError, match="Candidate"):
                await repository.resolve_evidence(
                    explanation.explanation_run_id,
                    "candidate:1:skill:0123456789abcdef0123456789abcde1",
                    candidate_id=candidates[1],
                    result_rank=2,
                )

            cross_explanation = FeedbackRecordModel(
                **{
                    key: value
                    for key, value in explanation_feedback.__dict__.items()
                    if not key.startswith("_")
                }
            )
            cross_explanation.feedback_id = "30000000-0000-0000-0000-000000000312"
            cross_explanation.explanation_run_id = second[4].explanation_run_id
            cross_explanation.match_explanation_id = second[4].explanations[0].id
            with pytest.raises(HistoricalOwnershipError, match="Explanation"):
                await repository.create(cross_explanation)

            replacement = _top1_feedback(
                run_id,
                job_id,
                results[0],
                feedback_id="30000000-0000-0000-0000-000000000313",
            )
            await repository.create(replacement)
            replacement2 = _top1_feedback(
                run_id,
                job_id,
                results[0],
                feedback_id="30000000-0000-0000-0000-000000000314",
                supersedes=replacement.feedback_id,
            )
            await repository.create(replacement2)
            ancestry = await repository.list_supersession_ancestry(
                replacement2.feedback_id
            )
            assert [item.feedback_id for item in ancestry] == [replacement.feedback_id]

            incompatible = FeedbackRecordModel(
                **{
                    key: value
                    for key, value in explanation_feedback.__dict__.items()
                    if not key.startswith("_")
                }
            )
            incompatible.feedback_id = "30000000-0000-0000-0000-000000000315"
            incompatible.supersedes_feedback_id = replacement2.feedback_id
            with pytest.raises(HistoricalOwnershipError, match="supersession"):
                await repository.create(incompatible)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_historical_profile_resolution_never_reads_current_profile_rows() -> None:
    async def scenario():
        from app.repositories.feedback_repository import FeedbackRepository

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, job_id, candidates, results, _explanation = await _completed_history(
                factory, "321", candidate_count=1
            )
            repository = FeedbackRepository(factory)
            snapshot = await repository.resolve_profile_snapshot(
                run_id, match_result_id=results[0].id
            )
            assert snapshot.job_id == job_id
            assert snapshot.candidate_id == candidates[0]
            assert snapshot.job_snapshot["job_id"] == job_id
            assert snapshot.candidate_snapshot["candidate_id"] == candidates[0]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_false_negative_feedback_preserves_absent_result_reference() -> None:
    async def scenario():
        from app.models.feedback import FeedbackRecordModel
        from app.repositories.feedback_repository import FeedbackRepository

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            history = await _completed_history(factory, "326", candidate_count=1)
            record = FeedbackRecordModel(
                feedback_id="30000000-0000-0000-0000-000000000326",
                contract_version="feedback_record_v1",
                feedback_type="ranking",
                origin="human",
                target_type="expected_candidate",
                match_run_id=history[0],
                expected_candidate_reference="expected_candidate:reviewer_ref_326",
                job_id=history[1],
                value="wrong",
                reason_code="false_negative",
                comment="Reviewer expected an absent historical candidate.",
            )
            repository = FeedbackRepository(factory)
            await repository.create(record)
            stored = await repository.get_by_id(record.feedback_id)
            assert stored.match_result_id is None
            assert stored.candidate_id is None
            assert stored.expected_candidate_reference == (
                "expected_candidate:reviewer_ref_326"
            )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_bad_case_repository_persists_bounded_append_only_aggregate() -> None:
    async def scenario():
        from app.models.bad_case import (
            BadCaseAnalysisModel,
            BadCaseSourceLinkModel,
            FeedbackEvidenceLinkModel,
            ResolutionActionModel,
        )
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.repositories.feedback_repository import FeedbackRepository

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, job_id, candidates, results, explanation = await _completed_history(
                factory, "331", candidate_count=1
            )
            feedback_repository = FeedbackRepository(factory)
            feedback = _top1_feedback(
                run_id,
                job_id,
                results[0],
                feedback_id="30000000-0000-0000-0000-000000000331",
            )
            await feedback_repository.create(feedback)

            repository = BadCaseRepository(factory)
            case = _case(
                run_id,
                job_id,
                results[0],
                bad_case_id="40000000-0000-0000-0000-000000000331",
            )
            source = BadCaseSourceLinkModel(
                bad_case_id=case.bad_case_id, feedback_id=feedback.feedback_id
            )
            await repository.create_with_source(case, source)

            evidence = FeedbackEvidenceLinkModel(
                bad_case_id=case.bad_case_id,
                explanation_run_id=explanation.explanation_run_id,
                evidence_reference=(
                    "candidate:1:skill:0123456789abcdef0123456789abcde1"
                ),
                purpose="supports_observation",
                evidence_kind="skill",
                candidate_id=candidates[0],
                result_rank=1,
            )
            await repository.append_evidence_link(evidence)
            analysis = BadCaseAnalysisModel(
                bad_case_id=case.bad_case_id,
                revision_number=1,
                assessment="supported",
                root_cause_type="ranking",
                root_cause_code="ranking_wrong_top1",
                description="Historical evidence supports review of the recorded top result.",
                supporting_evidence_link_id=evidence.id,
            )
            await repository.append_analysis(analysis)
            action = ResolutionActionModel(
                bad_case_id=case.bad_case_id,
                action_type="ranking_change_hypothesis",
                description="Review the ranking policy in a later governed phase.",
                status="planned",
            )
            await repository.append_resolution_action(action)

            aggregate = await repository.get_by_id(case.bad_case_id)
            assert aggregate.root.bad_case_id == case.bad_case_id
            assert len(aggregate.sources) == 1
            assert [item.revision_number for item in aggregate.analyses] == [1]
            assert len(aggregate.resolution_actions) == 1
            assert aggregate.transitions == ()
            listed, total = await repository.list_cases(limit=10, offset=0)
            assert total == 1
            assert [item.bad_case_id for item in listed] == [case.bad_case_id]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_bad_case_transition_is_atomic_and_rejects_stale_revision() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseSourceLinkModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.repositories.feedback_repository import FeedbackRepository
        from app.repositories.phase10_errors import BadCaseConcurrencyError

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, job_id, _candidates, results, _explanation = await _completed_history(
                factory, "341", candidate_count=1
            )
            feedback_repository = FeedbackRepository(factory)
            feedback = _top1_feedback(
                run_id,
                job_id,
                results[0],
                feedback_id="30000000-0000-0000-0000-000000000341",
            )
            await feedback_repository.create(feedback)
            repository = BadCaseRepository(factory)
            case = _case(
                run_id,
                job_id,
                results[0],
                bad_case_id="40000000-0000-0000-0000-000000000341",
            )
            await repository.create_with_source(
                case,
                BadCaseSourceLinkModel(
                    bad_case_id=case.bad_case_id, feedback_id=feedback.feedback_id
                ),
            )

            await repository.transition_atomically(
                case.bad_case_id,
                expected_status="CREATED",
                expected_revision=0,
                to_status="REVIEWED",
                reason="review_completed",
                origin="manual_review",
            )
            with pytest.raises(BadCaseConcurrencyError, match="stale"):
                await repository.transition_atomically(
                    case.bad_case_id,
                    expected_status="CREATED",
                    expected_revision=0,
                    to_status="REVIEWED",
                    reason="review_completed",
                    origin="manual_review",
                )
            aggregate = await repository.get_by_id(case.bad_case_id)
            assert aggregate.root.status == "REVIEWED"
            assert aggregate.root.revision == 1
            assert [(item.previous_revision, item.new_revision) for item in aggregate.transitions] == [(0, 1)]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgres_two_session_transition_contention_has_one_winner() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseSourceLinkModel, BadCaseTransitionModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.repositories.feedback_repository import FeedbackRepository
        from app.repositories.phase10_errors import BadCaseConcurrencyError

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, job_id, _candidates, results, _explanation = await _completed_history(
                factory, "351", candidate_count=1
            )
            feedback_repository = FeedbackRepository(factory)
            feedback = _top1_feedback(
                run_id,
                job_id,
                results[0],
                feedback_id="30000000-0000-0000-0000-000000000351",
            )
            await feedback_repository.create(feedback)
            first = BadCaseRepository(factory)
            second = BadCaseRepository(factory)
            case = _case(
                run_id,
                job_id,
                results[0],
                bad_case_id="40000000-0000-0000-0000-000000000351",
            )
            await first.create_with_source(
                case,
                BadCaseSourceLinkModel(
                    bad_case_id=case.bad_case_id, feedback_id=feedback.feedback_id
                ),
            )

            lock_acquired = asyncio.Event()
            release_winner = asyncio.Event()
            winner_backend_pid = asyncio.get_running_loop().create_future()
            loser_backend_pid = asyncio.get_running_loop().create_future()
            first_locked = first._locked_case
            second_locked = second._locked_case

            async def hold_first(session, bad_case_id):
                row = await first_locked(session, bad_case_id)
                winner_backend_pid.set_result(
                    await session.scalar(text("SELECT pg_backend_pid()"))
                )
                lock_acquired.set()
                await release_winner.wait()
                return row

            async def identify_loser(session, bad_case_id):
                pid = await session.scalar(text("SELECT pg_backend_pid()"))
                loser_backend_pid.set_result(pid)
                return await second_locked(session, bad_case_id)

            first._locked_case = hold_first
            second._locked_case = identify_loser
            arguments = dict(
                expected_status="CREATED",
                expected_revision=0,
                to_status="REVIEWED",
                reason="review_completed",
                origin="manual_review",
            )
            winner_task = asyncio.create_task(
                first.transition_atomically(case.bad_case_id, **arguments)
            )
            await lock_acquired.wait()
            winner_pid = await winner_backend_pid
            loser_task = asyncio.create_task(
                second.transition_atomically(case.bad_case_id, **arguments)
            )
            pid = await loser_backend_pid

            async def postgres_reports_contention():
                while True:
                    async with engine.connect() as observer:
                        blocker_pids = await observer.scalar(
                            text("SELECT pg_blocking_pids(:pid)"),
                            {"pid": pid},
                        )
                    if winner_pid in blocker_pids:
                        return
                    await asyncio.sleep(0)

            try:
                await asyncio.wait_for(postgres_reports_contention(), timeout=5)
            finally:
                release_winner.set()
            winner, loser = await asyncio.gather(
                winner_task, loser_task, return_exceptions=True
            )
            assert winner is None
            assert isinstance(loser, BadCaseConcurrencyError)

            async with factory() as session:
                stored = await session.get(type(case), case.bad_case_id)
                count = await session.scalar(
                    select(func.count())
                    .select_from(BadCaseTransitionModel)
                    .where(BadCaseTransitionModel.bad_case_id == case.bad_case_id)
                )
            assert stored.status == "REVIEWED"
            assert stored.revision == 1
            assert count == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_bad_case_rejects_cross_run_source_and_cross_candidate_evidence() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseSourceLinkModel, FeedbackEvidenceLinkModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.repositories.feedback_repository import FeedbackRepository
        from app.repositories.phase10_errors import (
            BadCaseConflictError,
            HistoricalOwnerNotFoundError,
            HistoricalOwnershipError,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            first = await _completed_history(factory, "361", candidate_count=2)
            second = await _completed_history(factory, "362", candidate_count=1)
            feedback_repository = FeedbackRepository(factory)
            feedback = _top1_feedback(
                first[0],
                first[1],
                first[3][0],
                feedback_id="30000000-0000-0000-0000-000000000361",
            )
            await feedback_repository.create(feedback)
            repository = BadCaseRepository(factory)

            wrong_case = _case(
                second[0],
                second[1],
                second[3][0],
                bad_case_id="40000000-0000-0000-0000-000000000361",
            )
            with pytest.raises(HistoricalOwnershipError, match="another MatchRun"):
                await repository.create_with_source(
                    wrong_case,
                    BadCaseSourceLinkModel(
                        bad_case_id=wrong_case.bad_case_id,
                        feedback_id=feedback.feedback_id,
                    ),
                )

            case = _case(
                first[0],
                first[1],
                first[3][0],
                bad_case_id="40000000-0000-0000-0000-000000000362",
            )
            await repository.create_with_source(
                case,
                BadCaseSourceLinkModel(
                    bad_case_id=case.bad_case_id, feedback_id=feedback.feedback_id
                ),
            )
            cross_candidate = FeedbackEvidenceLinkModel(
                bad_case_id=case.bad_case_id,
                explanation_run_id=first[4].explanation_run_id,
                evidence_reference=(
                    "candidate:2:skill:0123456789abcdef0123456789abcde2"
                ),
                purpose="supports_observation",
                evidence_kind="skill",
                candidate_id=first[2][1],
                result_rank=2,
            )
            with pytest.raises(HistoricalOwnershipError, match="another BadCase"):
                await repository.append_evidence_link(cross_candidate)

            unknown = FeedbackEvidenceLinkModel(
                bad_case_id=case.bad_case_id,
                explanation_run_id=first[4].explanation_run_id,
                evidence_reference=(
                    "candidate:1:skill:ffffffffffffffffffffffffffffffff"
                ),
                purpose="supports_observation",
                evidence_kind="skill",
                candidate_id=first[2][0],
                result_rank=1,
            )
            with pytest.raises(HistoricalOwnerNotFoundError, match="not found"):
                await repository.append_evidence_link(unknown)

            malformed = FeedbackEvidenceLinkModel(
                bad_case_id=case.bad_case_id,
                purpose="supports_observation",
            )
            with pytest.raises(BadCaseConflictError, match="exactly one"):
                await repository.append_evidence_link(malformed)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_invalid_transition_rolls_back_root_and_transition_together() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseSourceLinkModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.repositories.feedback_repository import FeedbackRepository
        from app.repositories.phase10_errors import BadCaseConflictError

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            history = await _completed_history(factory, "371", candidate_count=1)
            feedback = _top1_feedback(
                history[0],
                history[1],
                history[3][0],
                feedback_id="30000000-0000-0000-0000-000000000371",
            )
            await FeedbackRepository(factory).create(feedback)
            repository = BadCaseRepository(factory)
            case = _case(
                history[0],
                history[1],
                history[3][0],
                bad_case_id="40000000-0000-0000-0000-000000000371",
            )
            await repository.create_with_source(
                case,
                BadCaseSourceLinkModel(
                    bad_case_id=case.bad_case_id, feedback_id=feedback.feedback_id
                ),
            )
            with pytest.raises(BadCaseConflictError, match="lifecycle"):
                await repository.transition_atomically(
                    case.bad_case_id,
                    expected_status="CREATED",
                    expected_revision=0,
                    to_status="RESOLVED",
                    reason="actions_completed",
                    origin="manual_review",
                )
            aggregate = await repository.get_by_id(case.bad_case_id)
            assert aggregate.root.status == "CREATED"
            assert aggregate.root.revision == 0
            assert aggregate.transitions == ()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_bad_case_detail_uses_fixed_bounded_query_count() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseSourceLinkModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.repositories.feedback_repository import FeedbackRepository

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            history = await _completed_history(factory, "381", candidate_count=1)
            feedback = _top1_feedback(
                history[0],
                history[1],
                history[3][0],
                feedback_id="30000000-0000-0000-0000-000000000381",
            )
            await FeedbackRepository(factory).create(feedback)
            repository = BadCaseRepository(factory)
            case = _case(
                history[0],
                history[1],
                history[3][0],
                bad_case_id="40000000-0000-0000-0000-000000000381",
            )
            await repository.create_with_source(
                case,
                BadCaseSourceLinkModel(
                    bad_case_id=case.bad_case_id, feedback_id=feedback.feedback_id
                ),
            )

            statements: list[str] = []

            def observe(_connection, _cursor, statement, _parameters, _context, _many):
                statements.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", observe)
            try:
                aggregate = await repository.get_by_id(case.bad_case_id)
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", observe)
            assert aggregate.root.bad_case_id == case.bad_case_id
            assert len(statements) == 6
            assert all("JOIN" not in statement.upper() for statement in statements)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_evidence_resolution_rejects_bundle_from_another_match_run() -> None:
    async def scenario():
        from app.models.explanation_run import ExplanationRunModel
        from app.repositories.feedback_repository import FeedbackRepository
        from app.repositories.phase10_errors import HistoricalOwnershipError
        from sqlalchemy.orm import undefer

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            first = await _completed_history(factory, "391", candidate_count=1)
            second = await _completed_history(factory, "392", candidate_count=1)
            async with factory() as session:
                async with session.begin():
                    explanation = await session.scalar(
                        select(ExplanationRunModel)
                        .where(
                            ExplanationRunModel.explanation_run_id
                            == first[4].explanation_run_id
                        )
                        .options(undefer(ExplanationRunModel.evidence_bundle_json))
                    )
                    tampered = deepcopy(explanation.evidence_bundle_json)
                    tampered["source"]["match_run_id"] = second[0]
                    explanation.evidence_bundle_json = tampered

            with pytest.raises(HistoricalOwnershipError, match="Evidence Bundle"):
                await FeedbackRepository(factory).resolve_evidence(
                    first[4].explanation_run_id,
                    "candidate:1:skill:0123456789abcdef0123456789abcde1",
                    candidate_id=first[2][0],
                    result_rank=1,
                )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_system_signal_source_rejects_cross_run_explanation_owner() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseSourceLinkModel
        from app.models.feedback import SystemSignalModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.repositories.phase10_errors import HistoricalOwnershipError

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            first = await _completed_history(factory, "401", candidate_count=1)
            second = await _completed_history(factory, "402", candidate_count=1)
            signal = SystemSignalModel(
                signal_id="50000000-0000-0000-0000-000000000401",
                contract_version="system_signal_v1",
                match_run_id=first[0],
                explanation_run_id=second[4].explanation_run_id,
                signal_code="explanation_grounding_failure",
                source_stage="explanation",
                source_error_code="grounding_failed",
                occurrence_identity="occurrence_phase10_task3_401",
            )
            async with factory() as session:
                async with session.begin():
                    session.add(signal)

            case = _case(
                first[0],
                first[1],
                first[3][0],
                bad_case_id="40000000-0000-0000-0000-000000000401",
            )
            case.symptom_code = "ownership_failure"
            case.symptom_family = "INTEGRITY_OPERATIONS"
            with pytest.raises(HistoricalOwnershipError, match="SystemSignal"):
                await BadCaseRepository(factory).create_with_source(
                    case,
                    BadCaseSourceLinkModel(
                        bad_case_id=case.bad_case_id,
                        system_signal_id=signal.signal_id,
                    ),
                )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_supersession_ancestry_uses_one_bounded_query() -> None:
    async def scenario():
        from app.repositories.feedback_repository import FeedbackRepository

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            history = await _completed_history(factory, "411", candidate_count=1)
            repository = FeedbackRepository(factory)
            predecessor = None
            records = []
            for index in range(1, 4):
                record = _top1_feedback(
                    history[0],
                    history[1],
                    history[3][0],
                    feedback_id=f"30000000-0000-0000-0000-{4110 + index:012d}",
                    supersedes=predecessor,
                )
                await repository.create(record)
                records.append(record)
                predecessor = record.feedback_id

            statements: list[str] = []

            def observe(_connection, _cursor, statement, _parameters, _context, _many):
                statements.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", observe)
            try:
                ancestry = await repository.list_supersession_ancestry(
                    records[-1].feedback_id
                )
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", observe)
            assert [item.feedback_id for item in ancestry] == [
                records[1].feedback_id,
                records[0].feedback_id,
            ]
            assert len(statements) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_caller_owned_transaction_composes_repositories_and_rolls_back_every_write() -> None:
    class ForcedRollback(RuntimeError):
        pass

    async def scenario():
        from app.models.bad_case import (
            BadCaseSourceLinkModel,
            FeedbackEvidenceLinkModel,
        )
        from app.models.feedback import FeedbackRecordModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.repositories.feedback_repository import FeedbackRepository

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            history = await _completed_history(factory, "421", candidate_count=1)
            feedback_repository = FeedbackRepository(factory)
            case_repository = BadCaseRepository(factory)
            feedback = _top1_feedback(
                history[0],
                history[1],
                history[3][0],
                feedback_id="30000000-0000-0000-0000-000000000421",
            )
            case = _case(
                history[0],
                history[1],
                history[3][0],
                bad_case_id="40000000-0000-0000-0000-000000000421",
            )

            with pytest.raises(ForcedRollback):
                async with factory() as session:
                    async with session.begin():
                        match = await feedback_repository.resolve_match_run(
                            history[0], session=session
                        )
                        result = await feedback_repository.resolve_match_result(
                            history[0], history[3][0].id, session=session
                        )
                        evidence = await feedback_repository.resolve_evidence(
                            history[4].explanation_run_id,
                            "candidate:1:skill:0123456789abcdef0123456789abcde1",
                            candidate_id=history[2][0],
                            result_rank=1,
                            session=session,
                        )
                        assert match.job_id == history[1]
                        assert result.candidate_id == history[2][0]
                        assert evidence.kind == "skill"

                        await feedback_repository.create(feedback, session=session)
                        await case_repository.create_with_source(
                            case,
                            BadCaseSourceLinkModel(
                                bad_case_id=case.bad_case_id,
                                feedback_id=feedback.feedback_id,
                            ),
                            session=session,
                        )
                        await case_repository.append_evidence_link(
                            FeedbackEvidenceLinkModel(
                                bad_case_id=case.bad_case_id,
                                explanation_run_id=history[4].explanation_run_id,
                                evidence_reference=(
                                    "candidate:1:skill:"
                                    "0123456789abcdef0123456789abcde1"
                                ),
                                purpose="supports_observation",
                                evidence_kind="skill",
                                candidate_id=history[2][0],
                                result_rank=1,
                            ),
                            session=session,
                        )
                        await case_repository.transition_atomically(
                            case.bad_case_id,
                            expected_status="CREATED",
                            expected_revision=0,
                            to_status="REVIEWED",
                            reason="review_completed",
                            origin="manual_review",
                            session=session,
                        )
                        raise ForcedRollback

            async with factory() as session:
                assert await session.get(FeedbackRecordModel, feedback.feedback_id) is None
                assert await session.get(type(case), case.bad_case_id) is None
                phase10_counts = {
                    table: await session.scalar(
                        text(f"SELECT count(*) FROM {table}")
                    )
                    for table in (
                        "bad_case_source_links",
                        "feedback_evidence_links",
                        "bad_case_transitions",
                    )
                }
                assert phase10_counts == {
                    "bad_case_source_links": 0,
                    "feedback_evidence_links": 0,
                    "bad_case_transitions": 0,
                }
                assert await session.get(
                    __import__(
                        "app.models.match_run", fromlist=["MatchRunModel"]
                    ).MatchRunModel,
                    history[0],
                ) is not None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_bounded_bad_case_detail_explicitly_reports_truncated_children() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseSourceLinkModel, ResolutionActionModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.repositories.feedback_repository import FeedbackRepository

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            history = await _completed_history(factory, "431", candidate_count=1)
            feedback = _top1_feedback(
                history[0],
                history[1],
                history[3][0],
                feedback_id="30000000-0000-0000-0000-000000000431",
            )
            await FeedbackRepository(factory).create(feedback)
            repository = BadCaseRepository(factory)
            case = _case(
                history[0],
                history[1],
                history[3][0],
                bad_case_id="40000000-0000-0000-0000-000000000431",
            )
            await repository.create_with_source(
                case,
                BadCaseSourceLinkModel(
                    bad_case_id=case.bad_case_id, feedback_id=feedback.feedback_id
                ),
            )
            for index in range(2):
                await repository.append_resolution_action(
                    ResolutionActionModel(
                        bad_case_id=case.bad_case_id,
                        action_type="ranking_change_hypothesis",
                        description=f"Bounded action hypothesis {index}",
                        status="planned",
                    )
                )

            aggregate = await repository.get_by_id(case.bad_case_id, child_limit=1)
            assert len(aggregate.resolution_actions) == 1
            assert aggregate.truncated_collections == frozenset(
                {"resolution_actions"}
            )
        finally:
            await engine.dispose()

    asyncio.run(scenario())
