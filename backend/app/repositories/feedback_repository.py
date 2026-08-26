from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from pydantic import ValidationError
from sqlalchemy import literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, undefer

from app.models.explanation_run import ExplanationRunModel, MatchExplanationModel
from app.models.feedback import FeedbackRecordModel
from app.models.match_run import MatchResultModel, MatchRunModel
from app.repositories.phase10_errors import (
    FeedbackConflictError,
    FeedbackNotFoundError,
    HistoricalIntegrityError,
    HistoricalOwnerNotFoundError,
    HistoricalOwnershipError,
)
from app.repositories.phase10_transaction import repository_session
from app.schemas.explanations import InternalEvidenceBundleV1


@dataclass(frozen=True)
class HistoricalEvidenceOwner:
    evidence_id: str
    kind: str
    candidate_id: Optional[str]
    result_rank: Optional[int]


@dataclass(frozen=True)
class HistoricalMatchOwner:
    match_run_id: str
    job_id: str
    job_snapshot: dict[str, Any]


@dataclass(frozen=True)
class HistoricalResultOwner:
    match_result_id: int
    match_run_id: str
    candidate_id: str
    result_rank: int
    candidate_snapshot: dict[str, Any]


@dataclass(frozen=True)
class HistoricalExplanationOwner:
    explanation_run_id: str
    match_explanation_id: int
    match_run_id: str
    match_result_id: int
    candidate_id: str
    result_rank: int


@dataclass(frozen=True)
class HistoricalProfileSnapshot:
    match_run_id: str
    job_id: str
    job_snapshot: dict[str, Any]
    match_result_id: Optional[int]
    candidate_id: Optional[str]
    result_rank: Optional[int]
    candidate_snapshot: Optional[dict[str, Any]]


def _validated_evidence_bundle(payload: dict[str, Any]) -> InternalEvidenceBundleV1:
    try:
        return InternalEvidenceBundleV1.model_validate(payload)
    except ValidationError as error:
        raise HistoricalIntegrityError(
            "Persisted Evidence Bundle violates evidence_bundle_v1"
        ) from error


def index_evidence_bundle(payload: dict[str, Any]) -> dict[str, HistoricalEvidenceOwner]:
    """Validate a frozen bundle and derive its closed evidence owner index."""

    bundle = _validated_evidence_bundle(payload)
    owners: dict[str, HistoricalEvidenceOwner] = {}
    for requirement in bundle.job.requirements:
        owners[requirement.evidence_id] = HistoricalEvidenceOwner(
            evidence_id=requirement.evidence_id,
            kind="job_requirement",
            candidate_id=None,
            result_rank=None,
        )
    for candidate in bundle.candidates:
        for item, kind in (
            *((item, "skill") for item in candidate.skills),
            *((item, "project") for item in candidate.projects),
            *((item, "project_evidence") for item in candidate.project_evidence),
        ):
            owners[item.evidence_id] = HistoricalEvidenceOwner(
                evidence_id=item.evidence_id,
                kind=kind,
                candidate_id=candidate.candidate_id,
                result_rank=candidate.result_rank,
            )
        for fact in candidate.facts:
            owners[fact.evidence_id] = HistoricalEvidenceOwner(
                evidence_id=fact.evidence_id,
                kind=fact.kind.value,
                candidate_id=candidate.candidate_id,
                result_rank=candidate.result_rank,
            )
    return owners


class FeedbackRepository:
    """Append-only Feedback persistence and historical ownership primitives."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    @staticmethod
    async def _match_run(session, match_run_id: str) -> HistoricalMatchOwner:
        run = await session.get(MatchRunModel, match_run_id)
        if run is None:
            raise HistoricalOwnerNotFoundError(
                f"Historical MatchRun {match_run_id} was not found"
            )
        if run.status != "COMPLETED":
            raise HistoricalOwnershipError(
                "Feedback requires a completed historical MatchRun"
            )
        snapshot = run.ranking_input_snapshot
        if (
            run.job_id is None
            or run.requested_job_id != run.job_id
            or not isinstance(snapshot, dict)
            or snapshot.get("job_id") != run.job_id
        ):
            raise HistoricalIntegrityError("Historical MatchRun Job lineage is invalid")
        return HistoricalMatchOwner(
            match_run_id=run.run_id,
            job_id=run.job_id,
            job_snapshot=dict(snapshot),
        )

    @staticmethod
    async def _match_result(
        session, match_run_id: str, match_result_id: int
    ) -> HistoricalResultOwner:
        result = await session.get(MatchResultModel, match_result_id)
        if result is None:
            raise HistoricalOwnerNotFoundError(
                f"Historical MatchResult {match_result_id} was not found"
            )
        if result.run_id != match_run_id:
            raise HistoricalOwnershipError(
                "Historical MatchResult belongs to another MatchRun"
            )
        snapshot = result.candidate_input_snapshot
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("candidate_id") != result.candidate_id
        ):
            raise HistoricalIntegrityError(
                "Historical MatchResult Candidate snapshot is invalid"
            )
        return HistoricalResultOwner(
            match_result_id=result.id,
            match_run_id=result.run_id,
            candidate_id=result.candidate_id,
            result_rank=result.result_rank,
            candidate_snapshot=dict(snapshot),
        )

    @staticmethod
    async def _explanation(
        session,
        match_run_id: str,
        explanation_run_id: str,
        match_explanation_id: int,
    ) -> HistoricalExplanationOwner:
        run = await session.get(ExplanationRunModel, explanation_run_id)
        if run is None or run.status != "COMPLETED":
            raise HistoricalOwnerNotFoundError(
                f"Completed ExplanationRun {explanation_run_id} was not found"
            )
        if run.match_run_id != match_run_id:
            raise HistoricalOwnershipError(
                "ExplanationRun belongs to another MatchRun"
            )
        explanation = await session.get(MatchExplanationModel, match_explanation_id)
        if explanation is None:
            raise HistoricalOwnerNotFoundError(
                f"MatchExplanation {match_explanation_id} was not found"
            )
        if explanation.explanation_run_id != explanation_run_id:
            raise HistoricalOwnershipError(
                "MatchExplanation belongs to another ExplanationRun"
            )
        result = await FeedbackRepository._match_result(
            session, match_run_id, explanation.match_result_id
        )
        if (
            explanation.candidate_id != result.candidate_id
            or explanation.result_rank != result.result_rank
        ):
            raise HistoricalIntegrityError(
                "MatchExplanation identity conflicts with its historical MatchResult"
            )
        return HistoricalExplanationOwner(
            explanation_run_id=explanation_run_id,
            match_explanation_id=explanation.id,
            match_run_id=match_run_id,
            match_result_id=result.match_result_id,
            candidate_id=result.candidate_id,
            result_rank=result.result_rank,
        )

    @staticmethod
    async def _evidence(
        session,
        explanation_run_id: str,
        evidence_reference: str,
        *,
        candidate_id: Optional[str] = None,
        result_rank: Optional[int] = None,
    ) -> HistoricalEvidenceOwner:
        run = await session.scalar(
            select(ExplanationRunModel)
            .where(ExplanationRunModel.explanation_run_id == explanation_run_id)
            .options(undefer(ExplanationRunModel.evidence_bundle_json))
        )
        if run is None or run.status != "COMPLETED" or run.evidence_bundle_json is None:
            raise HistoricalOwnerNotFoundError(
                f"Completed ExplanationRun {explanation_run_id} has no Evidence Bundle"
            )
        bundle = _validated_evidence_bundle(run.evidence_bundle_json)
        if bundle.source.match_run_id != run.match_run_id:
            raise HistoricalOwnershipError(
                "Persisted Evidence Bundle belongs to another MatchRun"
            )
        owners = index_evidence_bundle(run.evidence_bundle_json)
        owner = owners.get(evidence_reference)
        if owner is None:
            raise HistoricalOwnerNotFoundError(
                f"Evidence reference {evidence_reference} was not found"
            )
        if candidate_id is not None or result_rank is not None:
            if (
                owner.candidate_id != candidate_id
                or owner.result_rank != result_rank
            ):
                raise HistoricalOwnershipError(
                    "Evidence reference belongs to another Candidate or rank"
                )
        return owner

    @staticmethod
    def _record_matches_result(
        record: FeedbackRecordModel,
        result: HistoricalResultOwner,
        *,
        comparison: bool = False,
    ) -> None:
        if comparison:
            identity = record.comparison_candidate_id
            rank = record.comparison_result_rank
        else:
            identity = record.candidate_id
            rank = record.result_rank
        if identity != result.candidate_id or rank != result.result_rank:
            raise HistoricalOwnershipError(
                "Feedback Candidate identity or rank conflicts with MatchResult"
            )

    @staticmethod
    async def _validate_supersession(session, record: FeedbackRecordModel) -> None:
        predecessor_id = record.supersedes_feedback_id
        if predecessor_id is None:
            return
        predecessor = await session.get(FeedbackRecordModel, predecessor_id)
        if predecessor is None:
            raise FeedbackNotFoundError(
                f"Superseded Feedback {predecessor_id} was not found"
            )
        compatible = (
            predecessor.match_run_id == record.match_run_id
            and predecessor.feedback_type == record.feedback_type
            and predecessor.target_type == record.target_type
            and predecessor.match_result_id == record.match_result_id
            and predecessor.comparison_match_result_id
            == record.comparison_match_result_id
            and predecessor.explanation_run_id == record.explanation_run_id
            and predecessor.match_explanation_id == record.match_explanation_id
            and predecessor.field_locator == record.field_locator
            and predecessor.expected_candidate_reference
            == record.expected_candidate_reference
        )
        if not compatible:
            raise HistoricalOwnershipError(
                "Feedback supersession target or type is incompatible"
            )
        seen = {record.feedback_id}
        current = predecessor
        for _ in range(100):
            if current.feedback_id in seen:
                raise HistoricalOwnershipError("Feedback supersession cycle detected")
            seen.add(current.feedback_id)
            if current.supersedes_feedback_id is None:
                return
            current = await session.get(
                FeedbackRecordModel, current.supersedes_feedback_id
            )
            if current is None:
                raise HistoricalIntegrityError(
                    "Feedback supersession ancestry contains a missing predecessor"
                )
        raise HistoricalIntegrityError("Feedback supersession ancestry exceeds 100")

    @classmethod
    async def _validate_record(cls, session, record: FeedbackRecordModel) -> None:
        run = await cls._match_run(session, record.match_run_id)
        if record.job_id != run.job_id:
            raise HistoricalOwnershipError("Feedback Job identity conflicts with MatchRun")

        primary = None
        if record.match_result_id is not None:
            primary = await cls._match_result(
                session, record.match_run_id, record.match_result_id
            )
            cls._record_matches_result(record, primary)
        if record.comparison_match_result_id is not None:
            comparison = await cls._match_result(
                session,
                record.match_run_id,
                record.comparison_match_result_id,
            )
            cls._record_matches_result(record, comparison, comparison=True)
            if primary is not None and primary.match_result_id == comparison.match_result_id:
                raise HistoricalOwnershipError(
                    "Pairwise feedback requires distinct MatchRun results"
                )
        if record.target_type == "top1" and (primary is None or primary.result_rank != 1):
            raise HistoricalOwnershipError(
                "Top-1 feedback must reference the persisted rank one result"
            )

        if record.explanation_run_id is not None:
            explanation = await cls._explanation(
                session,
                record.match_run_id,
                record.explanation_run_id,
                record.match_explanation_id,
            )
            if (
                primary is None
                or explanation.match_result_id != primary.match_result_id
                or explanation.candidate_id != record.candidate_id
                or explanation.result_rank != record.result_rank
            ):
                raise HistoricalOwnershipError(
                    "Explanation feedback target conflicts with historical ownership"
                )
            if record.evidence_reference is not None:
                owner = await cls._evidence(
                    session,
                    record.explanation_run_id,
                    record.evidence_reference,
                )
                if owner.candidate_id is not None and (
                    owner.candidate_id != record.candidate_id
                    or owner.result_rank != record.result_rank
                ):
                    raise HistoricalOwnershipError(
                        "Explanation evidence belongs to another Candidate or rank"
                    )
        await cls._validate_supersession(session, record)

    async def create(
        self,
        record: FeedbackRecordModel,
        *,
        session: Optional[AsyncSession] = None,
    ) -> None:
        try:
            async with repository_session(
                self.session_factory, session, write=True
            ) as active_session:
                if await active_session.get(FeedbackRecordModel, record.feedback_id):
                    raise FeedbackConflictError("Feedback IDs are immutable and unique")
                await self._validate_record(active_session, record)
                active_session.add(record)
                await active_session.flush()
        except IntegrityError as error:
            raise FeedbackConflictError(
                "Feedback persistence violated an immutable database constraint"
            ) from error

    async def get_by_id(
        self,
        feedback_id: str,
        *,
        session: Optional[AsyncSession] = None,
    ) -> Optional[FeedbackRecordModel]:
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            return await active_session.get(FeedbackRecordModel, feedback_id)

    async def list_supersession_ancestry(
        self,
        feedback_id: str,
        *,
        max_depth: int = 100,
        session: Optional[AsyncSession] = None,
    ) -> list[FeedbackRecordModel]:
        if type(max_depth) is not int or not 1 <= max_depth <= 100:
            raise ValueError("max_depth must be an integer from 1 through 100")
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            parent = aliased(FeedbackRecordModel)
            ancestry = select(
                FeedbackRecordModel.feedback_id.label("feedback_id"),
                FeedbackRecordModel.supersedes_feedback_id.label("supersedes_feedback_id"),
                literal(0).label("depth"),
            ).where(FeedbackRecordModel.feedback_id == feedback_id).cte(
                "feedback_ancestry", recursive=True
            )
            ancestry = ancestry.union_all(
                select(
                    parent.feedback_id,
                    parent.supersedes_feedback_id,
                    (ancestry.c.depth + 1).label("depth"),
                )
                .join(
                    ancestry,
                    parent.feedback_id == ancestry.c.supersedes_feedback_id,
                )
                .where(ancestry.c.depth < max_depth + 1)
            )
            rows = (
                await active_session.execute(
                    select(FeedbackRecordModel, ancestry.c.depth)
                    .join(
                        ancestry,
                        FeedbackRecordModel.feedback_id == ancestry.c.feedback_id,
                    )
                    .order_by(ancestry.c.depth)
                    .limit(max_depth + 2)
                )
            ).all()
            if not rows or rows[0][0].feedback_id != feedback_id:
                raise FeedbackNotFoundError(f"Feedback {feedback_id} was not found")
            records = [row[0] for row in rows]
            identifiers = [item.feedback_id for item in records]
            if len(identifiers) != len(set(identifiers)):
                raise HistoricalIntegrityError(
                    "Feedback supersession ancestry contains a cycle"
                )
            if len(records) - 1 > max_depth:
                raise HistoricalIntegrityError(
                    "Feedback supersession ancestry exceeds the requested bound"
                )
            if (
                records[-1].supersedes_feedback_id is not None
                and len(records) - 1 < max_depth
            ):
                raise HistoricalIntegrityError(
                    "Feedback supersession ancestry contains a missing predecessor"
                )
            return records[1:]

    async def resolve_match_run(
        self,
        match_run_id: str,
        *,
        session: Optional[AsyncSession] = None,
    ) -> HistoricalMatchOwner:
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            return await self._match_run(active_session, match_run_id)

    async def resolve_match_result(
        self,
        match_run_id: str,
        match_result_id: int,
        *,
        session: Optional[AsyncSession] = None,
    ) -> HistoricalResultOwner:
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            await self._match_run(active_session, match_run_id)
            return await self._match_result(
                active_session, match_run_id, match_result_id
            )

    async def resolve_explanation(
        self,
        match_run_id: str,
        explanation_run_id: str,
        match_explanation_id: int,
        *,
        session: Optional[AsyncSession] = None,
    ) -> HistoricalExplanationOwner:
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            await self._match_run(active_session, match_run_id)
            return await self._explanation(
                active_session,
                match_run_id,
                explanation_run_id,
                match_explanation_id,
            )

    async def resolve_evidence(
        self,
        explanation_run_id: str,
        evidence_reference: str,
        *,
        candidate_id: Optional[str] = None,
        result_rank: Optional[int] = None,
        session: Optional[AsyncSession] = None,
    ) -> HistoricalEvidenceOwner:
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            return await self._evidence(
                active_session,
                explanation_run_id,
                evidence_reference,
                candidate_id=candidate_id,
                result_rank=result_rank,
            )

    async def resolve_profile_snapshot(
        self,
        match_run_id: str,
        *,
        match_result_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
    ) -> HistoricalProfileSnapshot:
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            run = await self._match_run(active_session, match_run_id)
            if match_result_id is None:
                return HistoricalProfileSnapshot(
                    match_run_id=match_run_id,
                    job_id=run.job_id,
                    job_snapshot=run.job_snapshot,
                    match_result_id=None,
                    candidate_id=None,
                    result_rank=None,
                    candidate_snapshot=None,
                )
            result = await self._match_result(
                active_session, match_run_id, match_result_id
            )
            return HistoricalProfileSnapshot(
                match_run_id=match_run_id,
                job_id=run.job_id,
                job_snapshot=run.job_snapshot,
                match_result_id=result.match_result_id,
                candidate_id=result.candidate_id,
                result_rank=result.result_rank,
                candidate_snapshot=result.candidate_snapshot,
            )


__all__ = [
    "FeedbackRepository",
    "HistoricalEvidenceOwner",
    "HistoricalIntegrityError",
    "HistoricalExplanationOwner",
    "HistoricalMatchOwner",
    "HistoricalProfileSnapshot",
    "HistoricalResultOwner",
    "index_evidence_bundle",
]
