from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import func, select


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


def setup_module() -> None:
    if TEST_DATABASE_URL:
        from tests.test_feedback_bad_case_repository_postgres import _alembic_head

        _alembic_head()


def _feedback_service(factory):
    from app.services.feedback.service import FeedbackService

    return FeedbackService(factory)


def _case_service(factory):
    from app.services.bad_cases.service import BadCaseReviewService

    return BadCaseReviewService(factory)


def _top1_request(run_id: str, result_id: int, *, supersedes=None):
    from app.schemas.feedback import RankingFeedbackCreate

    return RankingFeedbackCreate.model_validate(
        {
            "feedback_type": "ranking",
            "match_run_id": run_id,
            "target_type": "top1",
            "subject_match_result_id": result_id,
            "value": "wrong",
            "reason_code": "wrong_top1",
            "supersedes_feedback_id": supersedes,
        }
    )


def test_feedback_service_postgres_derives_owners_and_rolls_back_attacks() -> None:
    async def scenario():
        from app.models.feedback import FeedbackRecordModel
        from app.schemas.feedback import RankingFeedbackCreate
        from app.services.feedback.errors import HistoricalTargetError
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            first = await _completed_history(factory, "701", candidate_count=2)
            second = await _completed_history(factory, "702", candidate_count=1)
            run_id, job_id, _candidates, results, _explanation = first
            service = _feedback_service(factory)

            original = await service.create(_top1_request(run_id, results[0].id))
            assert original.job_id == job_id
            assert original.candidate_id == results[0].candidate_id
            assert original.result_rank == 1

            successor = await service.create(
                _top1_request(
                    run_id,
                    results[0].id,
                    supersedes=original.feedback_id,
                )
            )
            assert successor.supersedes_feedback_id == original.feedback_id

            with pytest.raises(HistoricalTargetError):
                await service.create(_top1_request(run_id, results[1].id))

            cross_run = RankingFeedbackCreate.model_validate(
                {
                    "feedback_type": "ranking",
                    "match_run_id": run_id,
                    "target_type": "pairwise",
                    "subject_match_result_id": results[0].id,
                    "comparison_match_result_id": second[3][0].id,
                    "value": "wrong",
                    "reason_code": "ranking_inversion",
                }
            )
            with pytest.raises(HistoricalTargetError):
                await service.create(cross_run)

            opaque = RankingFeedbackCreate.model_validate(
                {
                    "feedback_type": "ranking",
                    "match_run_id": run_id,
                    "target_type": "expected_candidate",
                    "expected_candidate_reference": "expected_candidate:review-only-701",
                    "value": "wrong",
                    "reason_code": "false_negative",
                }
            )
            absent = await service.create(opaque)
            assert absent.candidate_id is None
            assert absent.result_rank is None

            async with factory() as session:
                rows = list(
                    (
                        await session.scalars(
                            select(FeedbackRecordModel).order_by(
                                FeedbackRecordModel.created_at
                            )
                        )
                    ).all()
                )
            assert len(rows) == 3
            assert rows[0].value == "wrong"
            assert rows[0].supersedes_feedback_id is None
            assert rows[1].supersedes_feedback_id == rows[0].feedback_id
            assert rows[2].expected_candidate_reference == (
                "expected_candidate:review-only-701"
            )
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_bad_case_service_postgres_full_grounded_lifecycle() -> None:
    async def scenario():
        from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
        from app.schemas.feedback import ExplanationFeedbackCreate
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, _job_id, _candidates, results, explanation = (
                await _completed_history(factory, "711", candidate_count=2)
            )
            feedback_service = _feedback_service(factory)
            case_service = _case_service(factory)
            feedback = await feedback_service.create(
                ExplanationFeedbackCreate.model_validate(
                    {
                        "feedback_type": "explanation",
                        "match_run_id": run_id,
                        "explanation_run_id": explanation.explanation_run_id,
                        "match_explanation_id": explanation.explanations[1].id,
                        "target_type": "match_reason",
                        "value": "unsupported",
                        "evidence_reference": (
                            "candidate:2:skill:0123456789abcdef0123456789abcde2"
                        ),
                    }
                )
            )
            assert feedback.candidate_id == results[1].candidate_id
            aggregate = await case_service.create(
                BadCaseCreateRequest.model_validate(
                    {
                        "feedback_id": feedback.feedback_id,
                        "symptom_code": "unsupported_explanation",
                        "severity": "HIGH",
                    }
                )
            )
            case_id = aggregate.root.bad_case_id
            assert len(aggregate.sources) == 1
            assert len(aggregate.evidence_links) == 1
            link_id = aggregate.evidence_links[0].id

            payloads = (
                {
                    "expected_status": "CREATED",
                    "expected_revision": 0,
                    "status": "REVIEWED",
                    "transition_reason": "review_completed",
                },
                {
                    "expected_status": "REVIEWED",
                    "expected_revision": 1,
                    "status": "ROOT_CAUSE_IDENTIFIED",
                    "transition_reason": "root_cause_supported",
                    "analysis": {
                        "assessment": "confirmed",
                        "root_cause_type": "explanation",
                        "root_cause_code": "explanation_unsupported_claim",
                        "description": "Case-specific unsupported selection",
                        "supporting_evidence_link_id": link_id,
                    },
                },
                {
                    "expected_status": "ROOT_CAUSE_IDENTIFIED",
                    "expected_revision": 2,
                    "status": "ACTION_PLANNED",
                    "transition_reason": "action_created",
                    "resolution": {
                        "action_type": "grounding_integrity_action",
                        "description": "Plan a bounded template change",
                    },
                },
            )
            for payload in payloads:
                aggregate = await case_service.review(
                    case_id, BadCaseUpdateRequest.model_validate(payload)
                )

            planned_id = aggregate.resolution_actions[-1].id
            aggregate = await case_service.review(
                case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "ACTION_PLANNED",
                        "expected_revision": 3,
                        "status": "RESOLVED",
                        "transition_reason": "actions_completed",
                        "resolution": {
                            "action_type": "grounding_integrity_action",
                            "description": "Case action completed",
                            "status": "completed",
                            "supersedes_action_id": planned_id,
                            "safe_change_reference": "commit:task4-case-711",
                        },
                    }
                ),
            )
            assert aggregate.root.status == "RESOLVED"
            assert len(aggregate.transitions) == 4

            aggregate = await case_service.review(
                case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "RESOLVED",
                        "expected_revision": 4,
                        "status": "VERIFIED",
                        "transition_reason": "verification_linked",
                        "verification_reference": "commit:task4-verify-711",
                    }
                ),
            )
            assert aggregate.root.status == "VERIFIED"
            assert aggregate.root.revision == 5
            assert [item.new_revision for item in aggregate.transitions] == [1, 2, 3, 4, 5]
            assert aggregate.transitions[-1].verification_reference == (
                "commit:task4-verify-711"
            )
            exported = await case_service.export_review(case_id)
            assert exported.verification_reference == "commit:task4-verify-711"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_bad_case_service_postgres_rejected_latest_analysis_blocks_root_cause() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseAnalysisModel, BadCaseModel
        from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
        from app.schemas.feedback import ExplanationFeedbackCreate
        from app.services.feedback.errors import ReviewEligibilityError
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, _job_id, _candidates, _results, explanation = (
                await _completed_history(factory, "712", candidate_count=2)
            )
            feedback = await _feedback_service(factory).create(
                ExplanationFeedbackCreate.model_validate(
                    {
                        "feedback_type": "explanation",
                        "match_run_id": run_id,
                        "explanation_run_id": explanation.explanation_run_id,
                        "match_explanation_id": explanation.explanations[1].id,
                        "target_type": "match_reason",
                        "value": "unsupported",
                        "evidence_reference": (
                            "candidate:2:skill:0123456789abcdef0123456789abcde2"
                        ),
                    }
                )
            )
            service = _case_service(factory)
            aggregate = await service.create(
                BadCaseCreateRequest.model_validate(
                    {
                        "feedback_id": feedback.feedback_id,
                        "symptom_code": "unsupported_explanation",
                        "severity": "HIGH",
                    }
                )
            )
            case_id = aggregate.root.bad_case_id
            evidence_id = aggregate.evidence_links[0].id
            await service.review(
                case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "CREATED",
                        "expected_revision": 0,
                        "status": "REVIEWED",
                        "transition_reason": "review_completed",
                    }
                ),
            )
            for assessment, description, support_id in (
                ("supported", "Initial historical support", evidence_id),
                ("rejected", "Later review rejects the hypothesis", None),
            ):
                await service.review(
                    case_id,
                    BadCaseUpdateRequest.model_validate(
                        {
                            "expected_status": "REVIEWED",
                            "expected_revision": 1,
                            "analysis": {
                                "assessment": assessment,
                                "root_cause_type": "explanation",
                                "root_cause_code": "explanation_unsupported_claim",
                                "description": description,
                                "supporting_evidence_link_id": support_id,
                            },
                        }
                    ),
                )
            with pytest.raises(ReviewEligibilityError, match="analysis"):
                await service.review(
                    case_id,
                    BadCaseUpdateRequest.model_validate(
                        {
                            "expected_status": "REVIEWED",
                            "expected_revision": 1,
                            "status": "ROOT_CAUSE_IDENTIFIED",
                            "transition_reason": "root_cause_supported",
                        }
                    ),
                )
            async with factory() as session:
                root = await session.get(BadCaseModel, case_id)
                count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(BadCaseAnalysisModel)
                        .where(BadCaseAnalysisModel.bad_case_id == case_id)
                    )
                    or 0
                )
            assert root is not None
            assert root.status == "REVIEWED"
            assert root.revision == 1
            assert count == 2
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_bad_case_service_postgres_stale_append_only_review_rolls_back() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseAnalysisModel, BadCaseModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
        from app.services.bad_cases.service import BadCaseReviewService
        from app.services.feedback.errors import ReviewConcurrencyError
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        class DelayedAnalysisRepository(BadCaseRepository):
            def __init__(self, session_factory):
                super().__init__(session_factory)
                self.started = asyncio.Event()
                self.release = asyncio.Event()

            async def append_analysis(self, analysis, *, session=None):
                self.started.set()
                await asyncio.wait_for(self.release.wait(), timeout=5)
                return await super().append_analysis(analysis, session=session)

        engine, factory = await _engine_and_factory()
        delayed_repository = DelayedAnalysisRepository(factory)
        try:
            await _truncate(engine)
            history = await _completed_history(factory, "713", candidate_count=1)
            feedback = await _feedback_service(factory).create(
                _top1_request(history[0], history[3][0].id)
            )
            delayed_service = BadCaseReviewService(
                factory, repository=delayed_repository
            )
            regular_service = _case_service(factory)
            aggregate = await delayed_service.create(
                BadCaseCreateRequest.model_validate(
                    {
                        "feedback_id": feedback.feedback_id,
                        "symptom_code": "wrong_top1",
                        "severity": "HIGH",
                    }
                )
            )
            case_id = aggregate.root.bad_case_id
            append_task = asyncio.create_task(
                delayed_service.review(
                    case_id,
                    BadCaseUpdateRequest.model_validate(
                        {
                            "expected_status": "CREATED",
                            "expected_revision": 0,
                            "analysis": {
                                "assessment": "suspected",
                                "root_cause_type": "ranking",
                                "root_cause_code": "ranking_wrong_top1",
                                "description": "Concurrent stale hypothesis",
                            },
                        }
                    ),
                )
            )
            await asyncio.wait_for(delayed_repository.started.wait(), timeout=5)
            await regular_service.review(
                case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "CREATED",
                        "expected_revision": 0,
                        "status": "DISMISSED",
                        "transition_reason": "case_dismissed",
                    }
                ),
            )
            delayed_repository.release.set()
            with pytest.raises(ReviewConcurrencyError, match="stale"):
                await append_task

            async with factory() as session:
                root = await session.get(BadCaseModel, case_id)
                analysis_count = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(BadCaseAnalysisModel)
                        .where(BadCaseAnalysisModel.bad_case_id == case_id)
                    )
                    or 0
                )
            assert root is not None
            assert root.status == "DISMISSED"
            assert root.revision == 1
            assert analysis_count == 0
        finally:
            delayed_repository.release.set()
            await engine.dispose()

    asyncio.run(scenario())


def test_bad_case_service_postgres_links_existing_feedback_fail_closed() -> None:
    async def scenario():
        from pydantic import TypeAdapter

        from app.models.bad_case import (
            BadCaseModel,
            BadCaseSourceLinkModel,
            BadCaseTransitionModel,
        )
        from app.models.feedback import FeedbackRecordModel
        from app.schemas.bad_cases import BadCaseCreateRequest
        from app.schemas.feedback import RankingFeedbackCreate
        from app.schemas.phase10 import BadCaseLinkSourceRequest
        from app.services.feedback.errors import (
            HistoricalTargetError,
            Phase10NotFoundError,
            ReviewConflictError,
            ReviewEligibilityError,
        )
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            first = await _completed_history(factory, "716", candidate_count=1)
            second = await _completed_history(factory, "717", candidate_count=1)
            feedback_service = _feedback_service(factory)
            case_service = _case_service(factory)

            original = await feedback_service.create(
                _top1_request(first[0], first[3][0].id)
            )
            compatible = await feedback_service.create(
                _top1_request(first[0], first[3][0].id)
            )
            cross_run = await feedback_service.create(
                _top1_request(second[0], second[3][0].id)
            )
            incompatible = await feedback_service.create(
                RankingFeedbackCreate.model_validate(
                    {
                        "feedback_type": "ranking",
                        "match_run_id": first[0],
                        "target_type": "top1",
                        "subject_match_result_id": first[3][0].id,
                        "value": "correct",
                    }
                )
            )
            aggregate = await case_service.create(
                BadCaseCreateRequest.model_validate(
                    {
                        "feedback_id": original.feedback_id,
                        "symptom_code": "wrong_top1",
                        "severity": "HIGH",
                    }
                )
            )
            case_id = aggregate.root.bad_case_id
            original_source = aggregate.sources[0]

            linked = await case_service.link_source(
                case_id,
                TypeAdapter(BadCaseLinkSourceRequest).validate_python(
                    {
                        "source_type": "feedback",
                        "feedback_id": compatible.feedback_id,
                    }
                ),
            )
            assert [item.feedback_id for item in linked.sources] == [
                original.feedback_id,
                compatible.feedback_id,
            ]
            assert linked.root.status == "CREATED"
            assert linked.root.revision == 0
            assert not linked.transitions

            with pytest.raises(ReviewConflictError):
                await case_service.link_source(
                    case_id,
                    TypeAdapter(BadCaseLinkSourceRequest).validate_python(
                        {
                            "source_type": "feedback",
                            "feedback_id": compatible.feedback_id,
                        }
                    ),
                )
            with pytest.raises(Phase10NotFoundError):
                await case_service.link_source(
                    case_id,
                    TypeAdapter(BadCaseLinkSourceRequest).validate_python(
                        {
                            "source_type": "feedback",
                            "feedback_id": "00000000-0000-0000-0000-000000000716",
                        }
                    ),
                )
            with pytest.raises(HistoricalTargetError):
                await case_service.link_source(
                    case_id,
                    TypeAdapter(BadCaseLinkSourceRequest).validate_python(
                        {
                            "source_type": "feedback",
                            "feedback_id": cross_run.feedback_id,
                        }
                    ),
                )
            with pytest.raises(ReviewEligibilityError, match="symptom"):
                await case_service.link_source(
                    case_id,
                    TypeAdapter(BadCaseLinkSourceRequest).validate_python(
                        {
                            "source_type": "feedback",
                            "feedback_id": incompatible.feedback_id,
                        }
                    ),
                )

            async with factory() as session:
                root = await session.get(BadCaseModel, case_id)
                sources = list(
                    (
                        await session.scalars(
                            select(BadCaseSourceLinkModel)
                            .where(BadCaseSourceLinkModel.bad_case_id == case_id)
                            .order_by(BadCaseSourceLinkModel.id)
                        )
                    ).all()
                )
                transitions = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(BadCaseTransitionModel)
                        .where(BadCaseTransitionModel.bad_case_id == case_id)
                    )
                    or 0
                )
                feedback_rows = list(
                    (
                        await session.scalars(
                            select(FeedbackRecordModel)
                            .where(
                                FeedbackRecordModel.feedback_id.in_(
                                    [original.feedback_id, compatible.feedback_id]
                                )
                            )
                            .order_by(FeedbackRecordModel.feedback_id)
                        )
                    ).all()
                )

            assert root is not None
            assert root.status == "CREATED"
            assert root.revision == 0
            assert transitions == 0
            assert len(sources) == 2
            assert sources[0].id == original_source.id
            assert sources[0].feedback_id == original.feedback_id
            assert sources[0].created_at == original_source.created_at
            feedback_by_id = {row.feedback_id: row for row in feedback_rows}
            assert feedback_by_id[original.feedback_id].value == "wrong"
            assert feedback_by_id[original.feedback_id].reason_code == "wrong_top1"
            assert feedback_by_id[original.feedback_id].match_run_id == first[0]
            assert feedback_by_id[compatible.feedback_id].value == "wrong"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_bad_case_service_postgres_concurrent_duplicate_source_is_typed_and_atomic() -> None:
    async def scenario():
        from pydantic import TypeAdapter

        from app.models.bad_case import BadCaseModel, BadCaseSourceLinkModel
        from app.repositories.bad_case_repository import BadCaseRepository
        from app.schemas.bad_cases import BadCaseCreateRequest
        from app.schemas.phase10 import BadCaseLinkSourceRequest
        from app.services.bad_cases.service import BadCaseReviewService
        from app.services.feedback.errors import ReviewConflictError
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        class CoordinatedSourceRepository(BadCaseRepository):
            def __init__(self, session_factory):
                super().__init__(session_factory)
                self.arrived = 0
                self.guard = asyncio.Lock()
                self.release = asyncio.Event()

            async def append_source(self, source, *, session=None):
                async with self.guard:
                    self.arrived += 1
                    if self.arrived == 2:
                        self.release.set()
                await asyncio.wait_for(self.release.wait(), timeout=5)
                return await super().append_source(source, session=session)

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            history = await _completed_history(factory, "718", candidate_count=1)
            feedback_service = _feedback_service(factory)
            original = await feedback_service.create(
                _top1_request(history[0], history[3][0].id)
            )
            compatible = await feedback_service.create(
                _top1_request(history[0], history[3][0].id)
            )
            repository = CoordinatedSourceRepository(factory)
            case_service = BadCaseReviewService(factory, repository=repository)
            aggregate = await case_service.create(
                BadCaseCreateRequest.model_validate(
                    {
                        "feedback_id": original.feedback_id,
                        "symptom_code": "wrong_top1",
                        "severity": "HIGH",
                    }
                )
            )
            case_id = aggregate.root.bad_case_id
            command = TypeAdapter(BadCaseLinkSourceRequest).validate_python(
                {
                    "source_type": "feedback",
                    "feedback_id": compatible.feedback_id,
                }
            )

            outcomes = await asyncio.gather(
                case_service.link_source(case_id, command),
                case_service.link_source(case_id, command),
                return_exceptions=True,
            )
            assert sum(not isinstance(item, Exception) for item in outcomes) == 1
            failures = [item for item in outcomes if isinstance(item, Exception)]
            assert len(failures) == 1
            assert isinstance(failures[0], ReviewConflictError)

            async with factory() as session:
                root = await session.get(BadCaseModel, case_id)
                sources = list(
                    (
                        await session.scalars(
                            select(BadCaseSourceLinkModel)
                            .where(BadCaseSourceLinkModel.bad_case_id == case_id)
                            .order_by(BadCaseSourceLinkModel.id)
                        )
                    ).all()
                )
            assert root is not None
            assert root.status == "CREATED"
            assert root.revision == 0
            assert [item.feedback_id for item in sources] == [
                original.feedback_id,
                compatible.feedback_id,
            ]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_task4_services_compose_in_caller_owned_transaction_and_outer_rollback() -> None:
    async def scenario():
        from app.models.bad_case import BadCaseModel
        from app.models.feedback import FeedbackRecordModel
        from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, _job_id, _candidates, results, _explanation = (
                await _completed_history(factory, "721", candidate_count=1)
            )
            feedback_service = _feedback_service(factory)
            case_service = _case_service(factory)

            async with factory() as session:
                transaction = await session.begin()
                feedback = await feedback_service.create(
                    _top1_request(run_id, results[0].id), session=session
                )
                aggregate = await case_service.create(
                    BadCaseCreateRequest.model_validate(
                        {
                            "feedback_id": feedback.feedback_id,
                            "symptom_code": "wrong_top1",
                            "severity": "HIGH",
                        }
                    ),
                    session=session,
                )
                await case_service.review(
                    aggregate.root.bad_case_id,
                    BadCaseUpdateRequest.model_validate(
                        {
                            "expected_status": "CREATED",
                            "expected_revision": 0,
                            "status": "REVIEWED",
                            "transition_reason": "review_completed",
                        }
                    ),
                    session=session,
                )
                await transaction.rollback()

            async with factory() as session:
                assert await session.scalar(
                    select(func.count()).select_from(FeedbackRecordModel)
                ) == 0
                assert await session.scalar(
                    select(func.count()).select_from(BadCaseModel)
                ) == 0
                from app.models.match_run import MatchRunModel

                assert await session.get(MatchRunModel, run_id) is not None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_task4_service_propagates_postgres_revision_conflict_and_duplicate_policy() -> None:
    async def scenario():
        from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
        from app.services.feedback.errors import ReviewConcurrencyError, ReviewEligibilityError
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            first = await _completed_history(factory, "731", candidate_count=1)
            second = await _completed_history(factory, "732", candidate_count=1)
            feedback_service = _feedback_service(factory)
            case_service = _case_service(factory)
            feedback_a = await feedback_service.create(
                _top1_request(first[0], first[3][0].id)
            )
            feedback_b = await feedback_service.create(
                _top1_request(first[0], first[3][0].id)
            )
            feedback_other = await feedback_service.create(
                _top1_request(second[0], second[3][0].id)
            )
            case_a = await case_service.create(
                BadCaseCreateRequest.model_validate(
                    {"feedback_id": feedback_a.feedback_id, "symptom_code": "wrong_top1", "severity": "HIGH"}
                )
            )
            case_b = await case_service.create(
                BadCaseCreateRequest.model_validate(
                    {"feedback_id": feedback_b.feedback_id, "symptom_code": "wrong_top1", "severity": "MEDIUM"}
                )
            )
            other = await case_service.create(
                BadCaseCreateRequest.model_validate(
                    {"feedback_id": feedback_other.feedback_id, "symptom_code": "wrong_top1", "severity": "LOW"}
                )
            )

            review = BadCaseUpdateRequest.model_validate(
                {
                    "expected_status": "CREATED",
                    "expected_revision": 0,
                    "status": "REVIEWED",
                    "transition_reason": "review_completed",
                }
            )
            results = await asyncio.gather(
                case_service.review(case_a.root.bad_case_id, review),
                case_service.review(case_a.root.bad_case_id, review),
                return_exceptions=True,
            )
            assert sum(not isinstance(item, Exception) for item in results) == 1
            assert sum(isinstance(item, ReviewConcurrencyError) for item in results) == 1, results

            with pytest.raises(ReviewEligibilityError, match="canonical"):
                await case_service.review(
                    case_b.root.bad_case_id,
                    BadCaseUpdateRequest.model_validate(
                        {
                            "expected_status": "CREATED",
                            "expected_revision": 0,
                            "status": "DUPLICATE",
                            "transition_reason": "duplicate_linked",
                            "duplicate_of_bad_case_id": other.root.bad_case_id,
                        }
                    ),
                )
            duplicate = await case_service.review(
                case_b.root.bad_case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "CREATED",
                        "expected_revision": 0,
                        "status": "DUPLICATE",
                        "transition_reason": "duplicate_linked",
                        "duplicate_of_bad_case_id": case_a.root.bad_case_id,
                    }
                ),
            )
            reopened = await case_service.review(
                case_b.root.bad_case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "DUPLICATE",
                        "expected_revision": 1,
                        "status": "REVIEWED",
                        "transition_reason": "case_reopened",
                    }
                ),
            )
            dismissed = await case_service.review(
                case_b.root.bad_case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "REVIEWED",
                        "expected_revision": 2,
                        "status": "DISMISSED",
                        "transition_reason": "case_dismissed",
                    }
                ),
            )
            assert duplicate.root.status == "DUPLICATE"
            assert reopened.root.status == "REVIEWED"
            assert dismissed.root.revision == 3
            assert [item.to_status for item in dismissed.transitions] == [
                "DUPLICATE",
                "REVIEWED",
                "DISMISSED",
            ]
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_explanation_scoped_system_signal_keeps_signal_owner_without_fake_match_explanation() -> None:
    async def scenario():
        from app.models.feedback import SystemSignalModel
        from app.schemas.bad_cases import BadCaseCreateRequest
        from app.services.feedback.errors import ReviewEligibilityError
        from tests.test_feedback_bad_case_repository_postgres import (
            _completed_history,
            _engine_and_factory,
            _truncate,
        )

        engine, factory = await _engine_and_factory()
        try:
            await _truncate(engine)
            run_id, _job_id, _candidates, _results, explanation = (
                await _completed_history(factory, "741", candidate_count=1)
            )
            async with factory() as session:
                async with session.begin():
                    session.add(
                        SystemSignalModel(
                            signal_id="50000000-0000-0000-0000-000000000741",
                            contract_version="system_signal_v1",
                            match_run_id=run_id,
                            explanation_run_id=explanation.explanation_run_id,
                            signal_code="attempt_audit_mismatch",
                            source_stage="persistence",
                            occurrence_identity="attempt-audit-741",
                        )
                    )
            service = _case_service(factory)
            with pytest.raises(ReviewEligibilityError, match="SystemSignal"):
                await service.create(
                    BadCaseCreateRequest.model_validate(
                        {
                            "system_signal_id": "50000000-0000-0000-0000-000000000741",
                            "symptom_code": "history_integrity_failure",
                            "severity": "CRITICAL",
                        }
                    )
                )
            created = await service.create(
                BadCaseCreateRequest.model_validate(
                    {
                        "system_signal_id": "50000000-0000-0000-0000-000000000741",
                        "symptom_code": "provider_attempt_failure",
                        "severity": "CRITICAL",
                    }
                )
            )
            assert created.root.primary_explanation_run_id is None
            assert created.root.primary_match_explanation_id is None
            assert created.sources[0].system_signal_id == (
                "50000000-0000-0000-0000-000000000741"
            )
        finally:
            await engine.dispose()

    asyncio.run(scenario())
