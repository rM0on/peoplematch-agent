from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.models.bad_case import (
    BadCaseAnalysisModel,
    BadCaseModel,
    BadCaseSourceLinkModel,
    FeedbackEvidenceLinkModel,
    ResolutionActionModel,
)
from app.repositories.bad_case_repository import BadCaseRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.phase10_errors import (
    BadCaseConcurrencyError,
    BadCaseConflictError,
    BadCaseNotFoundError,
    FeedbackNotFoundError,
    HistoricalIntegrityError,
    HistoricalOwnerNotFoundError,
    HistoricalOwnershipError,
)
from app.repositories.system_signal_repository import SystemSignalRepository
from app.schemas.bad_cases import BadCaseCreateRequest, BadCaseUpdateRequest
from app.schemas.phase10 import BadCaseLinkSourceRequest
from app.services.bad_cases.compatibility import (
    evidence_supports_root_cause,
    symptom_allowed_for_feedback,
    symptom_allowed_for_signal,
)
from app.services.bad_cases.projections import (
    project_detail,
    project_review_export,
    project_summary,
)
from app.services.bad_cases.taxonomy import (
    BAD_CASE_CONTRACT_VERSION,
    BAD_CASE_TAXONOMY_VERSION,
    action_allowed_for_root_cause,
    category_family,
)
from app.services.feedback.errors import (
    HistoricalTargetError,
    Phase10NotFoundError,
    ReviewConcurrencyError,
    ReviewConflictError,
    ReviewEligibilityError,
)
from app.services.feedback.transaction import service_session


def _value(item):
    return getattr(item, "value", item)


class BadCaseReviewService:
    """Orchestrate append-only review policy over frozen historical owners."""

    def __init__(
        self,
        session_factory,
        *,
        feedback_repository: FeedbackRepository | None = None,
        repository: BadCaseRepository | None = None,
        system_signal_repository=None,
    ) -> None:
        self.session_factory = session_factory
        self.feedback_repository = feedback_repository or FeedbackRepository(
            session_factory
        )
        self.repository = repository or BadCaseRepository(session_factory)
        self.system_signal_repository = system_signal_repository or SystemSignalRepository(
            session_factory
        )

    async def get_detail(self, bad_case_id: str, *, child_limit: int = 100):
        try:
            aggregate = await self.repository.get_by_id(
                bad_case_id, child_limit=child_limit
            )
            return project_detail(aggregate)
        except BadCaseNotFoundError as error:
            raise Phase10NotFoundError("BadCase was not found") from error

    async def list_summaries(self, *, limit: int, offset: int):
        rows, total = await self.repository.list_cases(limit=limit, offset=offset)
        return [project_summary(item) for item in rows], total

    async def create_detail(self, request: BadCaseCreateRequest):
        return project_detail(await self.create(request))

    async def review_detail(self, bad_case_id: str, request: BadCaseUpdateRequest):
        return project_detail(await self.review(bad_case_id, request))

    async def link_source_detail(
        self, bad_case_id: str, request: BadCaseLinkSourceRequest
    ):
        return project_detail(await self.link_source(bad_case_id, request))

    async def export_review(self, bad_case_id: str):
        try:
            aggregate = await self.repository.get_by_id(bad_case_id, child_limit=100)
        except BadCaseNotFoundError as error:
            raise Phase10NotFoundError("BadCase was not found") from error
        if aggregate.truncated_collections:
            raise ReviewConflictError(
                "Review export requires a complete bounded BadCase history"
            )
        return project_review_export(aggregate)

    async def link_source(
        self,
        bad_case_id: str,
        request: BadCaseLinkSourceRequest,
        *,
        session=None,
    ):
        try:
            async with service_session(self.session_factory, session) as active_session:
                aggregate = await self.repository.get_by_id(
                    bad_case_id, session=active_session
                )
                if request.feedback_id is not None:
                    feedback = await self.feedback_repository.get_by_id(
                        request.feedback_id, session=active_session
                    )
                    if feedback is None:
                        raise FeedbackNotFoundError("Feedback was not found")
                    expected_symptom = symptom_allowed_for_feedback(
                        feedback.feedback_type,
                        feedback.value,
                        feedback.reason_code,
                        target_type=feedback.target_type,
                    )
                    if expected_symptom != aggregate.root.symptom_code:
                        raise ReviewEligibilityError(
                            "Feedback source is incompatible with the existing BadCase symptom"
                        )
                    source = BadCaseSourceLinkModel(
                        bad_case_id=bad_case_id,
                        feedback_id=feedback.feedback_id,
                    )
                    await self.repository.append_source(source, session=active_session)
                    await self._append_feedback_reference(
                        bad_case_id,
                        feedback,
                        active_session,
                        existing_links=aggregate.evidence_links,
                    )
                else:
                    signal = await self.system_signal_repository.get_by_id(
                        request.system_signal_id, session=active_session
                    )
                    if signal is None:
                        raise HistoricalOwnerNotFoundError("SystemSignal was not found")
                    if symptom_allowed_for_signal(signal.signal_code) != (
                        aggregate.root.symptom_code
                    ):
                        raise ReviewEligibilityError(
                            "SystemSignal source is incompatible with the existing BadCase symptom"
                        )
                    if (
                        aggregate.root.primary_explanation_run_id is not None
                        and signal.explanation_run_id
                        != aggregate.root.primary_explanation_run_id
                    ):
                        raise HistoricalOwnershipError(
                            "SystemSignal belongs to another ExplanationRun"
                        )
                    source = BadCaseSourceLinkModel(
                        bad_case_id=bad_case_id,
                        system_signal_id=signal.signal_id,
                    )
                    await self.repository.append_source(source, session=active_session)
                return await self.repository.get_by_id(
                    bad_case_id, session=active_session
                )
        except ReviewEligibilityError:
            raise
        except (
            FeedbackNotFoundError,
            BadCaseNotFoundError,
            HistoricalOwnerNotFoundError,
        ) as error:
            raise Phase10NotFoundError("Historical review source was not found") from error
        except (HistoricalOwnershipError, HistoricalIntegrityError) as error:
            raise HistoricalTargetError("Historical review source is invalid") from error
        except BadCaseConflictError as error:
            raise ReviewConflictError(
                "BadCase source conflicts with persisted history"
            ) from error

    async def create(self, request: BadCaseCreateRequest, *, session=None):
        try:
            async with service_session(self.session_factory, session) as active_session:
                    if request.feedback_id is None:
                        return await self._create_from_signal(request, active_session)
                    feedback = await self.feedback_repository.get_by_id(
                        request.feedback_id, session=active_session
                    )
                    if feedback is None:
                        raise FeedbackNotFoundError("Feedback was not found")
                    expected_symptom = symptom_allowed_for_feedback(
                        feedback.feedback_type,
                        feedback.value,
                        feedback.reason_code,
                        target_type=feedback.target_type,
                    )
                    if expected_symptom is None or expected_symptom != request.symptom_code.value:
                        raise ReviewEligibilityError(
                            "Feedback observation is incompatible with the requested symptom"
                        )
                    case = BadCaseModel(
                        bad_case_id=str(uuid4()),
                        case_contract_version=BAD_CASE_CONTRACT_VERSION,
                        taxonomy_version=BAD_CASE_TAXONOMY_VERSION,
                        primary_match_run_id=feedback.match_run_id,
                        primary_match_result_id=feedback.match_result_id,
                        historical_job_id=feedback.job_id,
                        historical_candidate_id=feedback.candidate_id,
                        result_rank=feedback.result_rank,
                        primary_explanation_run_id=feedback.explanation_run_id,
                        primary_match_explanation_id=feedback.match_explanation_id,
                        symptom_code=request.symptom_code.value,
                        symptom_family=category_family(request.symptom_code.value),
                        severity=request.severity.value,
                        status="CREATED",
                        revision=0,
                    )
                    source = BadCaseSourceLinkModel(
                        bad_case_id=case.bad_case_id,
                        feedback_id=feedback.feedback_id,
                    )
                    await self.repository.create_with_source(
                        case, source, session=active_session
                    )
                    await self._append_feedback_reference(
                        case.bad_case_id, feedback, active_session
                    )
                    return await self.repository.get_by_id(
                        case.bad_case_id, session=active_session
                    )
        except ReviewEligibilityError:
            raise
        except (FeedbackNotFoundError, BadCaseNotFoundError, HistoricalOwnerNotFoundError) as error:
            raise Phase10NotFoundError("Historical review source was not found") from error
        except (HistoricalOwnershipError, HistoricalIntegrityError) as error:
            raise HistoricalTargetError("Historical review source is invalid") from error
        except BadCaseConflictError as error:
            raise ReviewConflictError("BadCase conflicts with immutable history") from error

    async def _create_from_signal(self, request, session):
        if self.system_signal_repository is None:
            raise ReviewEligibilityError("No deterministic SystemSignal source is available")
        signal = await self.system_signal_repository.get_by_id(
            request.system_signal_id, session=session
        )
        if signal is None:
            raise Phase10NotFoundError("SystemSignal was not found")
        if symptom_allowed_for_signal(signal.signal_code) != request.symptom_code.value:
            raise ReviewEligibilityError(
                "SystemSignal is incompatible with the requested deterministic symptom"
            )
        run = await self.feedback_repository.resolve_match_run(
            signal.match_run_id, session=session
        )
        case = BadCaseModel(
            bad_case_id=str(uuid4()),
            case_contract_version=BAD_CASE_CONTRACT_VERSION,
            taxonomy_version=BAD_CASE_TAXONOMY_VERSION,
            primary_match_run_id=signal.match_run_id,
            primary_match_result_id=None,
            historical_job_id=run.job_id,
            historical_candidate_id=None,
            result_rank=None,
            # The signal retains its ExplanationRun owner. Without a specific
            # MatchExplanation/MatchResult, the BadCase root must remain run-scoped.
            primary_explanation_run_id=None,
            primary_match_explanation_id=None,
            symptom_code=request.symptom_code.value,
            symptom_family=category_family(request.symptom_code.value),
            severity=request.severity.value,
            status="CREATED",
            revision=0,
        )
        source = BadCaseSourceLinkModel(
            bad_case_id=case.bad_case_id,
            system_signal_id=signal.signal_id,
        )
        await self.repository.create_with_source(case, source, session=session)
        return await self.repository.get_by_id(case.bad_case_id, session=session)

    async def _append_feedback_reference(
        self,
        bad_case_id,
        feedback,
        session,
        *,
        existing_links=(),
    ) -> None:
        if feedback.evidence_reference is not None:
            if any(
                item.evidence_reference == feedback.evidence_reference
                and item.explanation_run_id == feedback.explanation_run_id
                for item in existing_links
            ):
                return
            owner = await self.feedback_repository.resolve_evidence(
                feedback.explanation_run_id,
                feedback.evidence_reference,
                session=session,
            )
            link = FeedbackEvidenceLinkModel(
                bad_case_id=bad_case_id,
                explanation_run_id=feedback.explanation_run_id,
                evidence_reference=feedback.evidence_reference,
                purpose="disputed_reference",
                evidence_kind=owner.kind,
                candidate_id=owner.candidate_id,
                result_rank=owner.result_rank,
            )
            await self.repository.append_evidence_link(link, session=session)
        elif feedback.field_locator is not None:
            if any(
                item.field_locator == feedback.field_locator
                and item.candidate_id == feedback.candidate_id
                and item.result_rank == feedback.result_rank
                for item in existing_links
            ):
                return
            link = FeedbackEvidenceLinkModel(
                bad_case_id=bad_case_id,
                field_locator=feedback.field_locator,
                purpose="missing_expected_evidence",
                candidate_id=feedback.candidate_id,
                result_rank=feedback.result_rank,
            )
            await self.repository.append_evidence_link(link, session=session)

    async def review(self, bad_case_id: str, request: BadCaseUpdateRequest, *, session=None):
        try:
            async with service_session(self.session_factory, session) as active_session:
                    aggregate = await self.repository.get_by_id(
                        bad_case_id, session=active_session
                    )
                    root = aggregate.root
                    if (
                        root.status != _value(request.expected_status)
                        or root.revision != request.expected_revision
                    ):
                        raise ReviewConcurrencyError(
                            "Review uses a stale BadCase status or revision"
                        )

                    analysis = None
                    if request.analysis is not None:
                        analysis = self._build_analysis(aggregate, request.analysis)
                        await self.repository.append_analysis(
                            analysis, session=active_session
                        )

                    action = None
                    if request.resolution is not None:
                        latest = (
                            analysis
                            if analysis is not None
                            and analysis.assessment in {"supported", "confirmed"}
                            else self._current_supported_analysis(aggregate)
                            if analysis is None
                            else None
                        )
                        if latest is None or not action_allowed_for_root_cause(
                            latest.root_cause_code,
                            request.resolution.action_type.value,
                        ):
                            raise ReviewEligibilityError(
                                "Resolution action is incompatible with the supported root cause"
                            )
                        terminal = request.resolution.status.value in {
                            "completed",
                            "cancelled",
                            "superseded",
                        }
                        action = ResolutionActionModel(
                            bad_case_id=bad_case_id,
                            action_type=request.resolution.action_type.value,
                            description=request.resolution.description,
                            status=request.resolution.status.value,
                            supersedes_action_id=request.resolution.supersedes_action_id,
                            safe_change_reference=request.resolution.safe_change_reference,
                            completed_at=datetime.now(timezone.utc) if terminal else None,
                        )
                        await self.repository.append_resolution_action(
                            action, session=active_session
                        )

                    if request.status is not None:
                        await self._validate_transition_prerequisite(
                            aggregate,
                            request,
                            analysis=analysis,
                            action=action,
                            session=active_session,
                        )
                        expire = getattr(active_session, "expire", None)
                        if expire is not None:
                            expire(root)
                        await self.repository.transition_atomically(
                            bad_case_id,
                            expected_status=_value(request.expected_status),
                            expected_revision=request.expected_revision,
                            to_status=_value(request.status),
                            reason=_value(request.transition_reason),
                            origin="manual_review",
                            analysis_id=getattr(analysis, "id", None),
                            action_id=getattr(action, "id", None),
                            verification_reference=request.verification_reference,
                            duplicate_of_bad_case_id=request.duplicate_of_bad_case_id,
                            session=active_session,
                        )
                    elif analysis is not None or action is not None:
                        refresh = getattr(active_session, "refresh", None)
                        if refresh is not None:
                            await refresh(root)
                        if (
                            root.status != _value(request.expected_status)
                            or root.revision != request.expected_revision
                        ):
                            raise ReviewConcurrencyError(
                                "Review uses a stale BadCase status or revision"
                            )
                    return await self.repository.get_by_id(
                        bad_case_id, session=active_session
                    )
        except (ReviewEligibilityError, ReviewConcurrencyError):
            raise
        except BadCaseConcurrencyError as error:
            raise ReviewConcurrencyError(
                "Review uses a stale BadCase status or revision"
            ) from error
        except BadCaseNotFoundError as error:
            raise Phase10NotFoundError("BadCase was not found") from error
        except (HistoricalOwnershipError, HistoricalIntegrityError) as error:
            raise HistoricalTargetError("BadCase historical ownership is invalid") from error
        except BadCaseConflictError as error:
            raise ReviewConflictError("BadCase review conflicts with persisted history") from error

    @staticmethod
    def _current_supported_analysis(aggregate):
        if not aggregate.analyses:
            return None
        latest = aggregate.analyses[-1]
        return latest if latest.assessment in {"supported", "confirmed"} else None

    @staticmethod
    def _build_analysis(aggregate, request):
        support = None
        if request.supporting_evidence_link_id is not None:
            support = next(
                (
                    item
                    for item in aggregate.evidence_links
                    if item.id == request.supporting_evidence_link_id
                ),
                None,
            )
            if support is None:
                raise ReviewEligibilityError(
                    "Analysis evidence does not belong to this BadCase"
                )
            kind = support.evidence_kind or "field_locator"
            if not evidence_supports_root_cause(request.root_cause_code.value, kind):
                raise ReviewEligibilityError(
                    "Historical evidence kind cannot support the selected root cause"
                )
        elif request.assessment.value in {"supported", "confirmed"}:
            raise ReviewEligibilityError(
                "Supported analysis requires compatible historical evidence"
            )
        return BadCaseAnalysisModel(
            bad_case_id=aggregate.root.bad_case_id,
            revision_number=(aggregate.analyses[-1].revision_number + 1)
            if aggregate.analyses
            else 1,
            assessment=request.assessment.value,
            root_cause_type=request.root_cause_type.value,
            root_cause_code=request.root_cause_code.value,
            description=request.description,
            supporting_evidence_link_id=request.supporting_evidence_link_id,
        )

    @staticmethod
    def _current_actions(actions):
        superseded_ids = {
            item.supersedes_action_id
            for item in actions
            if item.supersedes_action_id is not None
        }
        return [item for item in actions if getattr(item, "id", None) not in superseded_ids]

    async def _validate_transition_prerequisite(
        self,
        aggregate,
        request,
        *,
        analysis: Optional[BadCaseAnalysisModel],
        action: Optional[ResolutionActionModel],
        session,
    ) -> None:
        target = _value(request.status)
        analyses = [*aggregate.analyses, *([analysis] if analysis is not None else [])]
        actions = [
            *aggregate.resolution_actions,
            *([action] if action is not None else []),
        ]
        current_actions = self._current_actions(actions)
        latest = self._current_supported_analysis(
            type("Aggregate", (), {"analyses": analyses})()
        )
        if target == "ROOT_CAUSE_IDENTIFIED" and (
            latest is None or latest.assessment not in {"supported", "confirmed"}
        ):
            raise ReviewEligibilityError(
                "Root-cause identification requires supported historical analysis"
            )
        if target == "ACTION_PLANNED":
            if latest is None or not any(
                item.status in {"planned", "in_progress"}
                and action_allowed_for_root_cause(
                    latest.root_cause_code, item.action_type
                )
                for item in current_actions
            ):
                raise ReviewEligibilityError(
                    "Action planning requires a compatible active resolution action"
                )
        if target == "RESOLVED" and (
            not current_actions
            or any(
                item.status not in {"completed", "cancelled", "superseded"}
                for item in current_actions
            )
        ):
            raise ReviewEligibilityError(
                "Resolution requires all case actions to have terminal dispositions"
            )
        if target == "VERIFIED" and request.verification_reference is None:
            raise ReviewEligibilityError(
                "Verification requires a new immutable case-specific reference"
            )
        if target == "DUPLICATE":
            if request.duplicate_of_bad_case_id == aggregate.root.bad_case_id:
                raise ReviewEligibilityError("BadCase cannot duplicate itself")
            canonical = await self.repository.get_by_id(
                request.duplicate_of_bad_case_id, session=session
            )
            if (
                canonical.root.primary_match_run_id
                != aggregate.root.primary_match_run_id
                or canonical.root.symptom_code != aggregate.root.symptom_code
            ):
                raise ReviewEligibilityError(
                    "Duplicate disposition requires a compatible canonical case"
                )


__all__ = ["BadCaseReviewService"]
