from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bad_case import (
    BadCaseAnalysisModel,
    BadCaseModel,
    BadCaseSourceLinkModel,
    BadCaseTransitionModel,
    FeedbackEvidenceLinkModel,
    ResolutionActionModel,
)
from app.models.explanation_run import ExplanationRunModel
from app.models.feedback import FeedbackRecordModel, SystemSignalModel
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.phase10_errors import (
    BadCaseConcurrencyError,
    BadCaseConflictError,
    BadCaseNotFoundError,
    HistoricalOwnerNotFoundError,
    HistoricalOwnershipError,
)
from app.repositories.phase10_transaction import repository_session


@dataclass(frozen=True)
class BadCaseAggregate:
    root: BadCaseModel
    sources: tuple[BadCaseSourceLinkModel, ...]
    evidence_links: tuple[FeedbackEvidenceLinkModel, ...]
    analyses: tuple[BadCaseAnalysisModel, ...]
    resolution_actions: tuple[ResolutionActionModel, ...]
    transitions: tuple[BadCaseTransitionModel, ...]
    child_limit: int
    truncated_collections: frozenset[str]


class BadCaseRepository:
    """BadCase aggregate repository with append-only children."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    @staticmethod
    def validate_list_window(*, limit: int, offset: int) -> tuple[int, int]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer from 1 through 100")
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        return limit, offset

    @staticmethod
    async def _case(session, bad_case_id: str) -> BadCaseModel:
        case = await session.get(BadCaseModel, bad_case_id)
        if case is None:
            raise BadCaseNotFoundError(f"BadCase {bad_case_id} was not found")
        return case

    @staticmethod
    async def _locked_case(session, bad_case_id: str) -> BadCaseModel:
        case = await session.scalar(
            select(BadCaseModel)
            .where(BadCaseModel.bad_case_id == bad_case_id)
            .with_for_update()
        )
        if case is None:
            raise BadCaseNotFoundError(f"BadCase {bad_case_id} was not found")
        return case

    @staticmethod
    async def _source_owner(session, source: BadCaseSourceLinkModel):
        if source.feedback_id is not None:
            record = await session.get(FeedbackRecordModel, source.feedback_id)
            if record is None:
                raise HistoricalOwnerNotFoundError(
                    f"Feedback source {source.feedback_id} was not found"
                )
            return record.match_run_id, record
        signal = await session.get(SystemSignalModel, source.system_signal_id)
        if signal is None:
            raise HistoricalOwnerNotFoundError(
                f"SystemSignal source {source.system_signal_id} was not found"
            )
        if signal.explanation_run_id is not None:
            explanation = await session.get(
                ExplanationRunModel, signal.explanation_run_id
            )
            if (
                explanation is None
                or explanation.match_run_id != signal.match_run_id
            ):
                raise HistoricalOwnershipError(
                    "SystemSignal ExplanationRun belongs to another MatchRun"
                )
        return signal.match_run_id, signal

    @staticmethod
    async def _validate_case_history(session, case: BadCaseModel) -> None:
        run = await FeedbackRepository._match_run(session, case.primary_match_run_id)
        if case.historical_job_id != run.job_id:
            raise HistoricalOwnershipError(
                "BadCase Job identity conflicts with historical MatchRun"
            )
        result = None
        if case.primary_match_result_id is not None:
            result = await FeedbackRepository._match_result(
                session, case.primary_match_run_id, case.primary_match_result_id
            )
            if (
                case.historical_candidate_id != result.candidate_id
                or case.result_rank != result.result_rank
            ):
                raise HistoricalOwnershipError(
                    "BadCase Candidate identity or rank conflicts with MatchResult"
                )
        elif case.historical_candidate_id is not None or case.result_rank is not None:
            raise HistoricalOwnershipError(
                "BadCase Candidate ownership requires a historical MatchResult"
            )
        explanation_values = (
            case.primary_explanation_run_id,
            case.primary_match_explanation_id,
        )
        if any(item is not None for item in explanation_values):
            if any(item is None for item in explanation_values) or result is None:
                raise HistoricalOwnershipError(
                    "BadCase Explanation ownership requires complete historical identity"
                )
            explanation = await FeedbackRepository._explanation(
                session,
                case.primary_match_run_id,
                case.primary_explanation_run_id,
                case.primary_match_explanation_id,
            )
            if explanation.match_result_id != result.match_result_id:
                raise HistoricalOwnershipError(
                    "BadCase Explanation belongs to another MatchResult"
                )

    @staticmethod
    async def _validate_source_for_case(
        session, case: BadCaseModel, source: BadCaseSourceLinkModel
    ) -> None:
        if source.bad_case_id != case.bad_case_id:
            raise HistoricalOwnershipError("BadCase source belongs to another case")
        match_run_id, record = await BadCaseRepository._source_owner(session, source)
        if match_run_id != case.primary_match_run_id:
            raise HistoricalOwnershipError(
                "BadCase source belongs to another MatchRun"
            )
        if isinstance(record, FeedbackRecordModel):
            if (
                record.match_result_id is not None
                and case.primary_match_result_id != record.match_result_id
            ):
                raise HistoricalOwnershipError(
                    "BadCase source belongs to another MatchResult"
                )
            if (
                record.explanation_run_id is not None
                and case.primary_explanation_run_id != record.explanation_run_id
            ):
                raise HistoricalOwnershipError(
                    "BadCase source belongs to another ExplanationRun"
                )

    async def create_with_source(
        self,
        case: BadCaseModel,
        source: BadCaseSourceLinkModel,
        *,
        session: Optional[AsyncSession] = None,
    ) -> None:
        try:
            async with repository_session(
                self.session_factory, session, write=True
            ) as active_session:
                if await active_session.get(BadCaseModel, case.bad_case_id):
                    raise BadCaseConflictError("BadCase IDs are immutable and unique")
                await self._validate_case_history(active_session, case)
                await self._validate_source_for_case(active_session, case, source)
                active_session.add_all((case, source))
                await active_session.flush()
        except IntegrityError as error:
            raise BadCaseConflictError(
                "BadCase persistence violated an immutable database constraint"
            ) from error

    async def get_by_id(
        self,
        bad_case_id: str,
        *,
        child_limit: int = 100,
        session: Optional[AsyncSession] = None,
    ) -> BadCaseAggregate:
        self.validate_list_window(limit=child_limit, offset=0)
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            root = await self._case(active_session, bad_case_id)
            source_limit = min(child_limit, 20)
            source_rows = list(
                (
                    await active_session.scalars(
                        select(BadCaseSourceLinkModel)
                        .where(BadCaseSourceLinkModel.bad_case_id == bad_case_id)
                        .order_by(BadCaseSourceLinkModel.id)
                        .limit(source_limit + 1)
                    )
                ).all()
            )
            evidence_rows = list(
                (
                    await active_session.scalars(
                        select(FeedbackEvidenceLinkModel)
                        .where(FeedbackEvidenceLinkModel.bad_case_id == bad_case_id)
                        .order_by(FeedbackEvidenceLinkModel.id)
                        .limit(child_limit + 1)
                    )
                ).all()
            )
            analysis_rows = list(
                (
                    await active_session.scalars(
                        select(BadCaseAnalysisModel)
                        .where(BadCaseAnalysisModel.bad_case_id == bad_case_id)
                        .order_by(BadCaseAnalysisModel.revision_number)
                        .limit(child_limit + 1)
                    )
                ).all()
            )
            action_rows = list(
                (
                    await active_session.scalars(
                        select(ResolutionActionModel)
                        .where(ResolutionActionModel.bad_case_id == bad_case_id)
                        .order_by(ResolutionActionModel.id)
                        .limit(child_limit + 1)
                    )
                ).all()
            )
            transition_rows = list(
                (
                    await active_session.scalars(
                        select(BadCaseTransitionModel)
                        .where(BadCaseTransitionModel.bad_case_id == bad_case_id)
                        .order_by(BadCaseTransitionModel.new_revision)
                        .limit(child_limit + 1)
                    )
                ).all()
            )
            truncated = frozenset(
                name
                for name, rows, limit in (
                    ("sources", source_rows, source_limit),
                    ("evidence_links", evidence_rows, child_limit),
                    ("analyses", analysis_rows, child_limit),
                    ("resolution_actions", action_rows, child_limit),
                    ("transitions", transition_rows, child_limit),
                )
                if len(rows) > limit
            )
            return BadCaseAggregate(
                root=root,
                sources=tuple(source_rows[:source_limit]),
                evidence_links=tuple(evidence_rows[:child_limit]),
                analyses=tuple(analysis_rows[:child_limit]),
                resolution_actions=tuple(action_rows[:child_limit]),
                transitions=tuple(transition_rows[:child_limit]),
                child_limit=child_limit,
                truncated_collections=truncated,
            )

    async def list_cases(
        self,
        *,
        limit: int,
        offset: int,
        session: Optional[AsyncSession] = None,
    ) -> tuple[list[BadCaseModel], int]:
        limit, offset = self.validate_list_window(limit=limit, offset=offset)
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            total = int(
                await active_session.scalar(
                    select(func.count()).select_from(BadCaseModel)
                )
                or 0
            )
            rows = (
                await active_session.scalars(
                    select(BadCaseModel)
                    .order_by(BadCaseModel.created_at.desc(), BadCaseModel.bad_case_id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return list(rows), total

    async def append_source(
        self,
        source: BadCaseSourceLinkModel,
        *,
        session: Optional[AsyncSession] = None,
    ) -> None:
        try:
            async with repository_session(
                self.session_factory, session, write=True
            ) as active_session:
                case = await self._case(active_session, source.bad_case_id)
                await self._validate_source_for_case(active_session, case, source)
                active_session.add(source)
                await active_session.flush()
        except IntegrityError as error:
            raise BadCaseConflictError(
                "BadCase source is duplicated or violates ownership"
            ) from error

    async def append_evidence_link(
        self,
        link: FeedbackEvidenceLinkModel,
        *,
        session: Optional[AsyncSession] = None,
    ) -> None:
        if (link.evidence_reference is None) == (link.field_locator is None):
            raise BadCaseConflictError(
                "Evidence links require exactly one historical reference or field locator"
            )
        try:
            async with repository_session(
                self.session_factory, session, write=True
            ) as active_session:
                case = await self._case(active_session, link.bad_case_id)
                if link.evidence_reference is not None:
                    explanation = await active_session.get(
                        ExplanationRunModel, link.explanation_run_id
                    )
                    if (
                        explanation is None
                        or explanation.match_run_id != case.primary_match_run_id
                    ):
                        raise HistoricalOwnershipError(
                            "Evidence link ExplanationRun belongs to another MatchRun"
                        )
                    owner = await FeedbackRepository._evidence(
                        active_session,
                        link.explanation_run_id,
                        link.evidence_reference,
                    )
                    if (
                        owner.kind != link.evidence_kind
                        or owner.candidate_id != link.candidate_id
                        or owner.result_rank != link.result_rank
                    ):
                        raise HistoricalOwnershipError(
                            "Evidence link kind or owner conflicts with historical bundle"
                        )
                    if owner.candidate_id is not None and (
                        case.historical_candidate_id != owner.candidate_id
                        or case.result_rank != owner.result_rank
                    ):
                        raise HistoricalOwnershipError(
                            "Evidence link belongs to another BadCase Candidate"
                        )
                elif link.field_locator.startswith("candidate."):
                    if (
                        link.candidate_id != case.historical_candidate_id
                        or link.result_rank != case.result_rank
                    ):
                        raise HistoricalOwnershipError(
                            "Historical field locator belongs to another Candidate"
                        )
                elif link.candidate_id is not None or link.result_rank is not None:
                    raise HistoricalOwnershipError(
                        "Job field locator cannot carry Candidate ownership"
                    )
                active_session.add(link)
                await active_session.flush()
        except IntegrityError as error:
            raise BadCaseConflictError(
                "Evidence link is duplicated or violates ownership"
            ) from error

    async def append_analysis(
        self,
        analysis: BadCaseAnalysisModel,
        *,
        session: Optional[AsyncSession] = None,
    ) -> None:
        try:
            async with repository_session(
                self.session_factory, session, write=True
            ) as active_session:
                await self._locked_case(active_session, analysis.bad_case_id)
                latest = int(
                    await active_session.scalar(
                        select(func.max(BadCaseAnalysisModel.revision_number)).where(
                            BadCaseAnalysisModel.bad_case_id == analysis.bad_case_id
                        )
                    )
                    or 0
                )
                if analysis.revision_number != latest + 1:
                    raise BadCaseConcurrencyError(
                        "BadCase analysis revision is stale or non-contiguous"
                    )
                if analysis.supporting_evidence_link_id is not None:
                    support = await active_session.get(
                        FeedbackEvidenceLinkModel,
                        analysis.supporting_evidence_link_id,
                    )
                    if support is None or support.bad_case_id != analysis.bad_case_id:
                        raise HistoricalOwnershipError(
                            "Analysis support belongs to another BadCase"
                        )
                active_session.add(analysis)
                await active_session.flush()
        except IntegrityError as error:
            raise BadCaseConflictError(
                "BadCase analysis violates append-only ownership"
            ) from error

    async def append_resolution_action(
        self,
        action: ResolutionActionModel,
        *,
        session: Optional[AsyncSession] = None,
    ) -> None:
        try:
            async with repository_session(
                self.session_factory, session, write=True
            ) as active_session:
                await self._locked_case(active_session, action.bad_case_id)
                if action.supersedes_action_id is not None:
                    predecessor = await active_session.get(
                        ResolutionActionModel, action.supersedes_action_id
                    )
                    if predecessor is None or predecessor.bad_case_id != action.bad_case_id:
                        raise HistoricalOwnershipError(
                            "Resolution supersession belongs to another BadCase"
                        )
                active_session.add(action)
                await active_session.flush()
        except IntegrityError as error:
            raise BadCaseConflictError(
                "Resolution action violates append-only ownership"
            ) from error

    async def transition_atomically(
        self,
        bad_case_id: str,
        *,
        expected_status: str,
        expected_revision: int,
        to_status: str,
        reason: str,
        origin: str,
        analysis_id: Optional[int] = None,
        action_id: Optional[int] = None,
        verification_reference: Optional[str] = None,
        duplicate_of_bad_case_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> None:
        try:
            async with repository_session(
                self.session_factory, session, write=True
            ) as active_session:
                case = await self._locked_case(active_session, bad_case_id)
                if (
                    case.status != expected_status
                    or case.revision != expected_revision
                ):
                    raise BadCaseConcurrencyError(
                        "BadCase transition uses a stale status or revision"
                    )
                if analysis_id is not None:
                    analysis = await active_session.get(
                        BadCaseAnalysisModel, analysis_id
                    )
                    if analysis is None or analysis.bad_case_id != bad_case_id:
                        raise HistoricalOwnershipError(
                            "Transition analysis belongs to another BadCase"
                        )
                if action_id is not None:
                    action = await active_session.get(
                        ResolutionActionModel, action_id
                    )
                    if action is None or action.bad_case_id != bad_case_id:
                        raise HistoricalOwnershipError(
                            "Transition action belongs to another BadCase"
                        )
                if duplicate_of_bad_case_id is not None:
                    duplicate = await active_session.get(
                        BadCaseModel, duplicate_of_bad_case_id
                    )
                    if duplicate is None or duplicate.bad_case_id == bad_case_id:
                        raise HistoricalOwnershipError(
                            "Duplicate disposition requires another existing BadCase"
                        )

                new_revision = expected_revision + 1
                transition = BadCaseTransitionModel(
                    bad_case_id=bad_case_id,
                    from_status=expected_status,
                    to_status=to_status,
                    reason=reason,
                    origin=origin,
                    analysis_id=analysis_id,
                    action_id=action_id,
                    previous_revision=expected_revision,
                    new_revision=new_revision,
                    verification_reference=verification_reference,
                )
                case.status = to_status
                case.revision = new_revision
                case.duplicate_of_bad_case_id = (
                    duplicate_of_bad_case_id if to_status == "DUPLICATE" else None
                )
                case.updated_at = datetime.now(timezone.utc)
                active_session.add(transition)
                await active_session.flush()
        except IntegrityError as error:
            raise BadCaseConflictError(
                "BadCase transition violates lifecycle or revision constraints"
            ) from error


__all__ = ["BadCaseAggregate", "BadCaseRepository"]
