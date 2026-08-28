from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Session:
    def __init__(self) -> None:
        self.transaction = _Transaction()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def begin(self):
        return self.transaction

    async def refresh(self, value) -> None:
        if getattr(value, "created_at", None) is None:
            value.created_at = datetime.now(timezone.utc)


class _SessionFactory:
    def __call__(self):
        return _Session()


class _FeedbackRepository:
    def __init__(self) -> None:
        self.created = []
        self.records = {}
        self.match = SimpleNamespace(
            match_run_id="run-1", job_id="job-1", job_snapshot={"job_id": "job-1"}
        )
        self.results = {
            11: SimpleNamespace(
                match_result_id=11,
                match_run_id="run-1",
                candidate_id="candidate-1",
                result_rank=1,
                candidate_snapshot={"candidate_id": "candidate-1", "skills": ["Python"]},
            ),
            12: SimpleNamespace(
                match_result_id=12,
                match_run_id="run-1",
                candidate_id="candidate-2",
                result_rank=2,
                candidate_snapshot={"candidate_id": "candidate-2", "skills": ["SQL"]},
            ),
        }

    async def resolve_match_run(self, match_run_id, *, session=None):
        assert session is not None
        if match_run_id != "run-1":
            from app.repositories.phase10_errors import HistoricalOwnerNotFoundError

            raise HistoricalOwnerNotFoundError("missing historical owner")
        return self.match

    async def resolve_match_result(self, match_run_id, result_id, *, session=None):
        assert match_run_id == "run-1"
        return self.results[result_id]

    async def resolve_explanation(
        self, match_run_id, explanation_run_id, match_explanation_id, *, session=None
    ):
        if (explanation_run_id, match_explanation_id) != ("explanation-1", 91):
            from app.repositories.phase10_errors import HistoricalOwnershipError

            raise HistoricalOwnershipError("cross-run explanation")
        return SimpleNamespace(
            explanation_run_id="explanation-1",
            match_explanation_id=91,
            match_run_id="run-1",
            match_result_id=11,
            candidate_id="candidate-1",
            result_rank=1,
        )

    async def resolve_evidence(
        self,
        explanation_run_id,
        evidence_reference,
        *,
        candidate_id=None,
        result_rank=None,
        session=None,
    ):
        return SimpleNamespace(
            evidence_id=evidence_reference,
            kind="skill",
            candidate_id="candidate-1",
            result_rank=1,
        )

    async def resolve_profile_snapshot(
        self, match_run_id, *, match_result_id=None, session=None
    ):
        result = self.results.get(match_result_id)
        return SimpleNamespace(
            match_run_id="run-1",
            job_id="job-1",
            job_snapshot={
                "job_id": "job-1",
                "must_have": ["Python"],
                "nice_to_have": [],
                "seniority_requirement": "senior",
                "location": "remote",
            },
            match_result_id=getattr(result, "match_result_id", None),
            candidate_id=getattr(result, "candidate_id", None),
            result_rank=getattr(result, "result_rank", None),
            candidate_snapshot=getattr(result, "candidate_snapshot", None),
        )

    async def list_supersession_ancestry(self, feedback_id, *, session=None, **kwargs):
        return []

    async def create(self, record, *, session=None):
        assert session is not None
        self.created.append(record)
        self.records[record.feedback_id] = record

    async def get_by_id(self, feedback_id, *, session=None):
        return self.records.get(feedback_id)


class _BadCaseRepository:
    def __init__(self) -> None:
        self.cases = {}
        self.next_id = 1

    async def create_with_source(self, case, source, *, session=None):
        self.cases[case.bad_case_id] = SimpleNamespace(
            root=case,
            sources=[source],
            evidence_links=[],
            analyses=[],
            resolution_actions=[],
            transitions=[],
            child_limit=100,
            truncated_collections=frozenset(),
        )

    async def get_by_id(self, bad_case_id, *, child_limit=100, session=None):
        from app.repositories.phase10_errors import BadCaseNotFoundError

        if bad_case_id not in self.cases:
            raise BadCaseNotFoundError("missing case")
        return self.cases[bad_case_id]

    async def append_evidence_link(self, link, *, session=None):
        link.id = self.next_id
        self.next_id += 1
        self.cases[link.bad_case_id].evidence_links.append(link)

    async def append_source(self, source, *, session=None):
        source.id = self.next_id
        source.created_at = datetime.now(timezone.utc)
        self.next_id += 1
        self.cases[source.bad_case_id].sources.append(source)

    async def append_analysis(self, analysis, *, session=None):
        analysis.id = self.next_id
        self.next_id += 1
        self.cases[analysis.bad_case_id].analyses.append(analysis)

    async def append_resolution_action(self, action, *, session=None):
        action.id = self.next_id
        self.next_id += 1
        self.cases[action.bad_case_id].resolution_actions.append(action)

    async def transition_atomically(
        self,
        bad_case_id,
        *,
        expected_status,
        expected_revision,
        to_status,
        reason,
        origin,
        analysis_id=None,
        action_id=None,
        verification_reference=None,
        duplicate_of_bad_case_id=None,
        session=None,
    ):
        aggregate = self.cases[bad_case_id]
        root = aggregate.root
        if root.status != expected_status or root.revision != expected_revision:
            from app.repositories.phase10_errors import BadCaseConcurrencyError

            raise BadCaseConcurrencyError("stale")
        transition = SimpleNamespace(
            id=self.next_id,
            bad_case_id=bad_case_id,
            from_status=expected_status,
            to_status=to_status,
            reason=reason,
            origin=origin,
            previous_revision=expected_revision,
            new_revision=expected_revision + 1,
            analysis_id=analysis_id,
            action_id=action_id,
            verification_reference=verification_reference,
            created_at=datetime.now(timezone.utc),
        )
        self.next_id += 1
        aggregate.transitions.append(transition)
        root.status = to_status
        root.revision += 1
        root.duplicate_of_bad_case_id = duplicate_of_bad_case_id


class _SystemSignalRepository:
    def __init__(self):
        self.signal = SimpleNamespace(
            signal_id="signal-1",
            match_run_id="run-1",
            explanation_run_id=None,
            signal_code="snapshot_fingerprint_mismatch",
            source_stage="match_run",
        )

    async def get_by_id(self, signal_id, *, session=None):
        return self.signal if signal_id == "signal-1" else None


def _feedback_record(**overrides):
    from app.models.feedback import FeedbackRecordModel

    payload = {
        "feedback_id": "feedback-1",
        "contract_version": "feedback_record_v1",
        "feedback_type": "ranking",
        "origin": "human",
        "target_type": "top1",
        "match_run_id": "run-1",
        "match_result_id": 11,
        "candidate_id": "candidate-1",
        "result_rank": 1,
        "job_id": "job-1",
        "value": "wrong",
        "reason_code": "wrong_top1",
        "created_at": datetime.now(timezone.utc),
    }
    payload.update(overrides)
    return FeedbackRecordModel(**payload)


def _ranking_request(**overrides):
    from app.schemas.feedback import RankingFeedbackCreate

    payload = {
        "feedback_type": "ranking",
        "match_run_id": "run-1",
        "target_type": "top1",
        "subject_match_result_id": 11,
        "value": "wrong",
        "reason_code": "wrong_top1",
    }
    payload.update(overrides)
    return RankingFeedbackCreate.model_validate(payload)


def test_feedback_service_derives_ranking_identity_and_keeps_false_negative_opaque():
    from app.services.feedback.service import FeedbackService
    from app.schemas.feedback import RankingFeedbackCreate

    async def scenario():
        repository = _FeedbackRepository()
        service = FeedbackService(_SessionFactory(), repository=repository)

        stored = await service.create(_ranking_request())
        assert stored.job_id == "job-1"
        assert stored.candidate_id == "candidate-1"
        assert stored.result_rank == 1

        expected = RankingFeedbackCreate.model_validate(
            {
                "feedback_type": "ranking",
                "match_run_id": "run-1",
                "target_type": "expected_candidate",
                "expected_candidate_reference": "expected_candidate:opaque-review-ref",
                "value": "wrong",
                "reason_code": "false_negative",
            }
        )
        absent = await service.create(expected)
        assert absent.expected_candidate_reference == "expected_candidate:opaque-review-ref"
        assert absent.candidate_id is None
        assert absent.result_rank is None

    asyncio.run(scenario())


def test_feedback_service_rejects_top1_spoof_and_cross_run_explanation():
    from app.services.feedback.errors import HistoricalTargetError
    from app.services.feedback.service import FeedbackService
    from app.schemas.feedback import ExplanationFeedbackCreate

    async def scenario():
        service = FeedbackService(_SessionFactory(), repository=_FeedbackRepository())
        with pytest.raises(HistoricalTargetError):
            await service.create(_ranking_request(subject_match_result_id=12))

        request = ExplanationFeedbackCreate.model_validate(
            {
                "feedback_type": "explanation",
                "match_run_id": "run-1",
                "explanation_run_id": "explanation-other",
                "match_explanation_id": 91,
                "target_type": "match_reason",
                "value": "unsupported",
            }
        )
        with pytest.raises(HistoricalTargetError):
            await service.create(request)

    asyncio.run(scenario())


def test_profile_feedback_resolves_only_closed_historical_snapshot_locator():
    from app.services.feedback.errors import HistoricalTargetError
    from app.services.feedback.service import FeedbackService
    from app.schemas.feedback import ProfileDataFeedbackCreate

    async def scenario():
        service = FeedbackService(_SessionFactory(), repository=_FeedbackRepository())
        candidate = ProfileDataFeedbackCreate.model_validate(
            {
                "feedback_type": "profile_data",
                "match_run_id": "run-1",
                "target_type": "candidate_profile",
                "subject_match_result_id": 11,
                "value": "incorrect_skill",
                "field_locator": "candidate.skills",
            }
        )
        stored = await service.create(candidate)
        assert stored.candidate_id == "candidate-1"

        unavailable = ProfileDataFeedbackCreate.model_validate(
            {
                "feedback_type": "profile_data",
                "match_run_id": "run-1",
                "target_type": "job_profile",
                "value": "missing_expectation",
                "field_locator": "job.expectations",
            }
        )
        with pytest.raises(HistoricalTargetError, match="historical snapshot"):
            await service.create(unavailable)

    asyncio.run(scenario())


def test_bad_case_compatibility_keeps_symptom_root_cause_and_actions_separate():
    from app.services.bad_cases.compatibility import (
        evidence_supports_root_cause,
        symptom_allowed_for_feedback,
        symptom_allowed_for_signal,
    )

    assert symptom_allowed_for_feedback("ranking", "wrong", "wrong_top1") == "wrong_top1"
    assert symptom_allowed_for_feedback("ranking", "correct", None) is None
    assert evidence_supports_root_cause("ranking_wrong_top1", "ranking")
    assert not evidence_supports_root_cause("ranking_wrong_top1", "skill")
    assert not evidence_supports_root_cause("retrieval_recall_miss", "retrieval")
    assert symptom_allowed_for_signal("snapshot_fingerprint_mismatch") == (
        "history_integrity_failure"
    )
    assert symptom_allowed_for_signal("attempt_audit_mismatch") == (
        "provider_attempt_failure"
    )


def test_bad_case_service_creates_only_compatible_human_observation():
    from app.schemas.bad_cases import BadCaseCreateRequest
    from app.services.bad_cases.service import BadCaseReviewService
    from app.services.feedback.errors import ReviewEligibilityError

    async def scenario():
        feedback = _FeedbackRepository()
        feedback.records["feedback-1"] = _feedback_record()
        cases = _BadCaseRepository()
        service = BadCaseReviewService(
            _SessionFactory(), feedback_repository=feedback, repository=cases
        )
        request = BadCaseCreateRequest.model_validate(
            {
                "feedback_id": "feedback-1",
                "symptom_code": "wrong_top1",
                "severity": "HIGH",
            }
        )
        created = await service.create(request)
        assert created.root.primary_match_run_id == "run-1"
        assert created.root.primary_match_result_id == 11
        assert created.root.symptom_code == "wrong_top1"
        assert created.root.status == "CREATED"

        feedback.records["feedback-correct"] = _feedback_record(
            feedback_id="feedback-correct", value="correct", reason_code=None
        )
        invalid = BadCaseCreateRequest.model_validate(
            {
                "feedback_id": "feedback-correct",
                "symptom_code": "wrong_top1",
                "severity": "HIGH",
            }
        )
        with pytest.raises(ReviewEligibilityError):
            await service.create(invalid)

    asyncio.run(scenario())


def test_bad_case_service_links_compatible_feedback_to_existing_case_append_only():
    from pydantic import TypeAdapter

    from app.schemas.bad_cases import BadCaseCreateRequest
    from app.schemas.phase10 import BadCaseLinkSourceRequest
    from app.services.bad_cases.service import BadCaseReviewService
    from app.services.feedback.errors import ReviewEligibilityError

    async def scenario():
        feedback = _FeedbackRepository()
        feedback.records["feedback-1"] = _feedback_record()
        feedback.records["feedback-2"] = _feedback_record(feedback_id="feedback-2")
        feedback.records["feedback-incompatible"] = _feedback_record(
            feedback_id="feedback-incompatible", value="correct", reason_code=None
        )
        cases = _BadCaseRepository()
        service = BadCaseReviewService(
            _SessionFactory(), feedback_repository=feedback, repository=cases
        )
        created = await service.create(
            BadCaseCreateRequest.model_validate(
                {
                    "feedback_id": "feedback-1",
                    "symptom_code": "wrong_top1",
                    "severity": "HIGH",
                }
            )
        )
        linked = await service.link_source(
            created.root.bad_case_id,
            TypeAdapter(BadCaseLinkSourceRequest).validate_python(
                {"source_type": "feedback", "feedback_id": "feedback-2"}
            ),
        )
        assert [item.feedback_id for item in linked.sources] == [
            "feedback-1",
            "feedback-2",
        ]

        with pytest.raises(ReviewEligibilityError, match="symptom"):
            await service.link_source(
                created.root.bad_case_id,
                TypeAdapter(BadCaseLinkSourceRequest).validate_python(
                    {
                        "source_type": "feedback",
                        "feedback_id": "feedback-incompatible",
                    }
                ),
            )
        assert len(linked.sources) == 2

    asyncio.run(scenario())


def test_bad_case_service_rejects_incompatible_analysis_and_action_semantics():
    from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
    from app.services.bad_cases.service import BadCaseReviewService
    from app.services.feedback.errors import ReviewEligibilityError

    async def scenario():
        feedback = _FeedbackRepository()
        feedback.records["feedback-1"] = _feedback_record()
        cases = _BadCaseRepository()
        service = BadCaseReviewService(
            _SessionFactory(), feedback_repository=feedback, repository=cases
        )
        created = await service.create(
            BadCaseCreateRequest.model_validate(
                {
                    "feedback_id": "feedback-1",
                    "symptom_code": "wrong_top1",
                    "severity": "HIGH",
                }
            )
        )
        case_id = created.root.bad_case_id
        link = SimpleNamespace(
            id=7,
            bad_case_id=case_id,
            evidence_kind="skill",
            evidence_reference="candidate:1:skill:0123456789abcdef0123456789abcdef",
            field_locator=None,
        )
        cases.cases[case_id].evidence_links.append(link)

        incompatible = BadCaseUpdateRequest.model_validate(
            {
                "expected_status": "CREATED",
                "expected_revision": 0,
                "analysis": {
                    "assessment": "confirmed",
                    "root_cause_type": "ranking",
                    "root_cause_code": "ranking_wrong_top1",
                    "description": "Case-specific hypothesis",
                    "supporting_evidence_link_id": 7,
                },
            }
        )
        with pytest.raises(ReviewEligibilityError, match="evidence"):
            await service.review(case_id, incompatible)

        cases.cases[case_id].evidence_links[0].evidence_kind = "ranking"
        accepted = await service.review(case_id, incompatible)
        assert accepted.analyses[-1].assessment == "confirmed"

        invalid_action = BadCaseUpdateRequest.model_validate(
            {
                "expected_status": "CREATED",
                "expected_revision": 0,
                "resolution": {
                    "action_type": "template_change_hypothesis",
                    "description": "Unrelated change",
                },
            }
        )
        with pytest.raises(ReviewEligibilityError, match="root cause"):
            await service.review(case_id, invalid_action)

    asyncio.run(scenario())


def test_bad_case_service_uses_only_the_latest_analysis_as_current_root_cause():
    from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
    from app.services.bad_cases.service import BadCaseReviewService
    from app.services.feedback.errors import ReviewEligibilityError

    async def scenario():
        feedback = _FeedbackRepository()
        feedback.records["feedback-1"] = _feedback_record()
        cases = _BadCaseRepository()
        service = BadCaseReviewService(
            _SessionFactory(), feedback_repository=feedback, repository=cases
        )
        created = await service.create(
            BadCaseCreateRequest.model_validate(
                {
                    "feedback_id": "feedback-1",
                    "symptom_code": "wrong_top1",
                    "severity": "HIGH",
                }
            )
        )
        case_id = created.root.bad_case_id
        cases.cases[case_id].evidence_links.append(
            SimpleNamespace(
                id=7,
                bad_case_id=case_id,
                evidence_kind="ranking",
                evidence_reference="ranking:run-1:result:11",
                field_locator=None,
            )
        )
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
        await service.review(
            case_id,
            BadCaseUpdateRequest.model_validate(
                {
                    "expected_status": "REVIEWED",
                    "expected_revision": 1,
                    "analysis": {
                        "assessment": "supported",
                        "root_cause_type": "ranking",
                        "root_cause_code": "ranking_wrong_top1",
                        "description": "Initially supported hypothesis",
                        "supporting_evidence_link_id": 7,
                    },
                }
            ),
        )
        await service.review(
            case_id,
            BadCaseUpdateRequest.model_validate(
                {
                    "expected_status": "REVIEWED",
                    "expected_revision": 1,
                    "analysis": {
                        "assessment": "rejected",
                        "root_cause_type": "ranking",
                        "root_cause_code": "ranking_wrong_top1",
                        "description": "Later review rejected the hypothesis",
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

        with pytest.raises(ReviewEligibilityError, match="supported root cause"):
            await service.review(
                case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "REVIEWED",
                        "expected_revision": 1,
                        "analysis": {
                            "assessment": "suspected",
                            "root_cause_type": "ranking",
                            "root_cause_code": "ranking_wrong_top1",
                            "description": "Unproven replacement hypothesis",
                        },
                        "resolution": {
                            "action_type": "ranking_change_hypothesis",
                            "description": "Must not be planned from suspicion alone",
                        },
                    }
                ),
            )

    asyncio.run(scenario())


def test_bad_case_service_rechecks_revision_after_append_only_review_write():
    from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
    from app.services.bad_cases.service import BadCaseReviewService
    from app.services.feedback.errors import ReviewConcurrencyError

    class ConcurrentTransitionRepository(_BadCaseRepository):
        async def append_analysis(self, analysis, *, session=None):
            await super().append_analysis(analysis, session=session)
            root = self.cases[analysis.bad_case_id].root
            root.status = "DISMISSED"
            root.revision = 1

    async def scenario():
        feedback = _FeedbackRepository()
        feedback.records["feedback-1"] = _feedback_record()
        cases = ConcurrentTransitionRepository()
        service = BadCaseReviewService(
            _SessionFactory(), feedback_repository=feedback, repository=cases
        )
        created = await service.create(
            BadCaseCreateRequest.model_validate(
                {
                    "feedback_id": "feedback-1",
                    "symptom_code": "wrong_top1",
                    "severity": "HIGH",
                }
            )
        )

        with pytest.raises(ReviewConcurrencyError, match="stale"):
            await service.review(
                created.root.bad_case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "CREATED",
                        "expected_revision": 0,
                        "analysis": {
                            "assessment": "suspected",
                            "root_cause_type": "ranking",
                            "root_cause_code": "ranking_wrong_top1",
                            "description": "Stale analysis must not commit",
                        },
                    }
                ),
            )

    asyncio.run(scenario())


def test_bad_case_service_enforces_lifecycle_prerequisites_and_verification_artifact():
    from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
    from app.services.bad_cases.service import BadCaseReviewService
    from app.services.feedback.errors import ReviewEligibilityError

    async def scenario():
        feedback = _FeedbackRepository()
        feedback.records["feedback-1"] = _feedback_record()
        cases = _BadCaseRepository()
        service = BadCaseReviewService(
            _SessionFactory(), feedback_repository=feedback, repository=cases
        )
        created = await service.create(
            BadCaseCreateRequest.model_validate(
                {
                    "feedback_id": "feedback-1",
                    "symptom_code": "wrong_top1",
                    "severity": "HIGH",
                }
            )
        )
        case_id = created.root.bad_case_id

        skip = BadCaseUpdateRequest.model_validate(
            {
                "expected_status": "CREATED",
                "expected_revision": 0,
                "status": "REVIEWED",
                "transition_reason": "review_completed",
            }
        )
        reviewed = await service.review(case_id, skip)
        assert reviewed.root.status == "REVIEWED"

        root_without_analysis = BadCaseUpdateRequest.model_validate(
            {
                "expected_status": "REVIEWED",
                "expected_revision": 1,
                "status": "ROOT_CAUSE_IDENTIFIED",
                "transition_reason": "root_cause_supported",
            }
        )
        with pytest.raises(ReviewEligibilityError, match="analysis"):
            await service.review(case_id, root_without_analysis)

        cases.cases[case_id].root.status = "RESOLVED"
        cases.cases[case_id].root.revision = 5
        verify_without_artifact = BadCaseUpdateRequest.model_construct(
            expected_status="RESOLVED",
            expected_revision=5,
            status="VERIFIED",
            transition_reason="verification_linked",
            analysis=None,
            resolution=None,
            verification_reference=None,
            duplicate_of_bad_case_id=None,
        )
        with pytest.raises(ReviewEligibilityError, match="Verification"):
            await service.review(case_id, verify_without_artifact)

    asyncio.run(scenario())


def test_bad_case_service_completes_valid_append_only_lifecycle_without_phase11_claims():
    from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
    from app.services.bad_cases.service import BadCaseReviewService

    async def scenario():
        feedback = _FeedbackRepository()
        feedback.records["feedback-1"] = _feedback_record()
        cases = _BadCaseRepository()
        service = BadCaseReviewService(
            _SessionFactory(), feedback_repository=feedback, repository=cases
        )
        aggregate = await service.create(
            BadCaseCreateRequest.model_validate(
                {
                    "feedback_id": "feedback-1",
                    "symptom_code": "wrong_top1",
                    "severity": "HIGH",
                }
            )
        )
        case_id = aggregate.root.bad_case_id
        cases.cases[case_id].evidence_links.append(
            SimpleNamespace(
                id=9,
                bad_case_id=case_id,
                evidence_kind="ranking",
                evidence_reference="ranking:1:final_score",
                field_locator=None,
            )
        )

        for payload in (
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
                    "assessment": "supported",
                    "root_cause_type": "ranking",
                    "root_cause_code": "ranking_wrong_top1",
                    "description": "Case-specific recorded ranking discrepancy",
                    "supporting_evidence_link_id": 9,
                },
            },
            {
                "expected_status": "ROOT_CAUSE_IDENTIFIED",
                "expected_revision": 2,
                "status": "ACTION_PLANNED",
                "transition_reason": "action_created",
                "resolution": {
                    "action_type": "ranking_change_hypothesis",
                    "description": "Review a bounded ranking policy change",
                    "status": "planned",
                },
            },
        ):
            aggregate = await service.review(
                case_id, BadCaseUpdateRequest.model_validate(payload)
            )

        planned_id = aggregate.resolution_actions[-1].id
        aggregate = await service.review(
            case_id,
            BadCaseUpdateRequest.model_validate(
                {
                    "expected_status": "ACTION_PLANNED",
                    "expected_revision": 3,
                    "status": "RESOLVED",
                    "transition_reason": "actions_completed",
                    "resolution": {
                        "action_type": "ranking_change_hypothesis",
                        "description": "Bounded case action completed",
                        "status": "completed",
                        "supersedes_action_id": planned_id,
                        "safe_change_reference": "commit:case-change-1",
                    },
                }
            ),
        )
        assert aggregate.root.status == "RESOLVED"
        assert aggregate.root.revision == 4

        aggregate = await service.review(
            case_id,
            BadCaseUpdateRequest.model_validate(
                {
                    "expected_status": "RESOLVED",
                    "expected_revision": 4,
                    "status": "VERIFIED",
                    "transition_reason": "verification_linked",
                    "verification_reference": "commit:case-verification-1",
                }
            ),
        )
        assert aggregate.root.status == "VERIFIED"
        assert aggregate.transitions[-1].verification_reference == (
            "commit:case-verification-1"
        )

    asyncio.run(scenario())


def test_bad_case_duplicate_requires_same_historical_symptom_and_reopen_is_audit_transition():
    from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
    from app.services.bad_cases.service import BadCaseReviewService
    from app.services.feedback.errors import ReviewEligibilityError

    async def scenario():
        feedback = _FeedbackRepository()
        feedback.records["feedback-1"] = _feedback_record()
        feedback.records["feedback-2"] = _feedback_record(feedback_id="feedback-2")
        cases = _BadCaseRepository()
        service = BadCaseReviewService(
            _SessionFactory(), feedback_repository=feedback, repository=cases
        )
        first = await service.create(
            BadCaseCreateRequest.model_validate(
                {"feedback_id": "feedback-1", "symptom_code": "wrong_top1", "severity": "HIGH"}
            )
        )
        second = await service.create(
            BadCaseCreateRequest.model_validate(
                {"feedback_id": "feedback-2", "symptom_code": "wrong_top1", "severity": "MEDIUM"}
            )
        )
        incompatible = SimpleNamespace(
            root=SimpleNamespace(
                bad_case_id="other-case",
                primary_match_run_id="run-other",
                symptom_code="unsupported_explanation",
            )
        )
        cases.cases["other-case"] = incompatible
        with pytest.raises(ReviewEligibilityError, match="canonical"):
            await service.review(
                second.root.bad_case_id,
                BadCaseUpdateRequest.model_validate(
                    {
                        "expected_status": "CREATED",
                        "expected_revision": 0,
                        "status": "DUPLICATE",
                        "transition_reason": "duplicate_linked",
                        "duplicate_of_bad_case_id": "other-case",
                    }
                ),
            )

        duplicate = await service.review(
            second.root.bad_case_id,
            BadCaseUpdateRequest.model_validate(
                {
                    "expected_status": "CREATED",
                    "expected_revision": 0,
                    "status": "DUPLICATE",
                    "transition_reason": "duplicate_linked",
                    "duplicate_of_bad_case_id": first.root.bad_case_id,
                }
            ),
        )
        reopened = await service.review(
            second.root.bad_case_id,
            BadCaseUpdateRequest.model_validate(
                {
                    "expected_status": "DUPLICATE",
                    "expected_revision": 1,
                    "status": "REVIEWED",
                    "transition_reason": "case_reopened",
                }
            ),
        )
        assert duplicate.root.status == "REVIEWED"  # same aggregate object was reopened
        assert reopened.transitions[-1].from_status == "DUPLICATE"
        assert len(reopened.transitions) == 2

    asyncio.run(scenario())


def test_system_signal_case_uses_only_existing_deterministic_signal_identity():
    from app.schemas.bad_cases import BadCaseCreateRequest
    from app.services.bad_cases.service import BadCaseReviewService

    async def scenario():
        feedback = _FeedbackRepository()
        cases = _BadCaseRepository()
        service = BadCaseReviewService(
            _SessionFactory(),
            feedback_repository=feedback,
            repository=cases,
            system_signal_repository=_SystemSignalRepository(),
        )
        created = await service.create(
            BadCaseCreateRequest.model_validate(
                {
                    "system_signal_id": "signal-1",
                    "symptom_code": "history_integrity_failure",
                    "severity": "CRITICAL",
                }
            )
        )
        assert created.root.primary_match_run_id == "run-1"
        assert created.sources[0].system_signal_id == "signal-1"
        assert created.root.historical_candidate_id is None

        service.system_signal_repository.signal.signal_code = "attempt_audit_mismatch"
        incompatible = BadCaseCreateRequest.model_validate(
            {
                "system_signal_id": "signal-1",
                "symptom_code": "history_integrity_failure",
                "severity": "CRITICAL",
            }
        )
        from app.services.feedback.errors import ReviewEligibilityError

        with pytest.raises(ReviewEligibilityError, match="SystemSignal"):
            await service.create(incompatible)

    asyncio.run(scenario())


def test_system_signal_repository_is_read_only_for_task4_orchestration():
    from app.repositories.system_signal_repository import SystemSignalRepository
    from app.services.bad_cases.service import BadCaseReviewService

    assert hasattr(SystemSignalRepository, "get_by_id")
    assert not hasattr(SystemSignalRepository, "create")
    assert not hasattr(SystemSignalRepository, "update")
    assert not hasattr(SystemSignalRepository, "delete")
    service = BadCaseReviewService(
        _SessionFactory(),
        feedback_repository=_FeedbackRepository(),
        repository=_BadCaseRepository(),
    )
    assert isinstance(service.system_signal_repository, SystemSignalRepository)
