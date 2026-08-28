from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter

from app.models.feedback import FeedbackRecordModel
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.phase10_errors import (
    FeedbackConflictError,
    FeedbackNotFoundError,
    HistoricalIntegrityError,
    HistoricalOwnerNotFoundError,
    HistoricalOwnershipError,
)
from app.schemas.feedback import (
    ExplanationFeedbackCreate,
    FeedbackCreateRequest,
    FeedbackRecordV1,
    ProfileDataFeedbackCreate,
    RankingFeedbackCreate,
)
from app.services.feedback.contracts import FEEDBACK_CONTRACT_VERSION
from app.services.feedback.errors import (
    HistoricalTargetError,
    Phase10NotFoundError,
    ReviewConflictError,
)
from app.services.feedback.transaction import service_session


_RECORD_ADAPTER = TypeAdapter(FeedbackRecordV1)
_PROFILE_LOCATOR_KEYS = {
    "candidate.skills": ("candidate", ("skills",)),
    "candidate.project_evidence": ("candidate", ("project_evidence",)),
    "candidate.seniority": ("candidate", ("seniority",)),
    "candidate.location": ("candidate", ("preferred_locations",)),
    "candidate.role_direction": ("candidate", ("target_roles",)),
    "job.requirements": ("job", ("must_have", "nice_to_have")),
    "job.requirement_priority": ("job", ("must_have", "nice_to_have")),
    "job.seniority": ("job", ("seniority_requirement",)),
    "job.location": ("job", ("location",)),
    # Phase 8 has no persisted expectations field. It intentionally fails closed.
    "job.expectations": ("job", ("expectations",)),
}


def _value(item: Any) -> Any:
    return getattr(item, "value", item)


def _record_payload(record: FeedbackRecordModel) -> dict[str, Any]:
    base = {
        "feedback_id": record.feedback_id,
        "contract_version": record.contract_version,
        "origin": record.origin,
        "feedback_type": record.feedback_type,
        "target_type": record.target_type,
        "match_run_id": record.match_run_id,
        "comment": record.comment,
        "supersedes_feedback_id": record.supersedes_feedback_id,
        "job_id": record.job_id,
        "candidate_id": record.candidate_id,
        "result_rank": record.result_rank,
        "comparison_candidate_id": record.comparison_candidate_id,
        "comparison_result_rank": record.comparison_result_rank,
        "created_at": record.created_at,
    }
    if record.feedback_type == "ranking":
        base.update(
            subject_match_result_id=record.match_result_id,
            comparison_match_result_id=record.comparison_match_result_id,
            expected_candidate_reference=record.expected_candidate_reference,
            value=record.value,
            reason_code=record.reason_code,
        )
    elif record.feedback_type == "explanation":
        base.update(
            explanation_run_id=record.explanation_run_id,
            match_explanation_id=record.match_explanation_id,
            value=record.value,
            evidence_reference=record.evidence_reference,
        )
    else:
        base.update(
            subject_match_result_id=record.match_result_id,
            value=record.value,
            field_locator=record.field_locator,
        )
    return base


class FeedbackService:
    """Create immutable human feedback from server-resolved historical identity."""

    def __init__(self, session_factory, *, repository: FeedbackRepository | None = None):
        self.session_factory = session_factory
        self.repository = repository or FeedbackRepository(session_factory)

    async def get(self, feedback_id: str):
        try:
            record = await self.repository.get_by_id(feedback_id)
            if record is None:
                raise FeedbackNotFoundError("Feedback was not found")
            return _RECORD_ADAPTER.validate_python(_record_payload(record))
        except FeedbackNotFoundError as error:
            raise Phase10NotFoundError("Feedback was not found") from error

    async def create(self, request: FeedbackCreateRequest, *, session=None):
        try:
            async with service_session(self.session_factory, session) as active_session:
                    run = await self.repository.resolve_match_run(
                        request.match_run_id, session=active_session
                    )
                    fields: dict[str, Any] = {
                        "feedback_id": str(uuid4()),
                        "contract_version": FEEDBACK_CONTRACT_VERSION,
                        "feedback_type": _value(request.feedback_type),
                        "origin": "human",
                        "target_type": _value(request.target_type),
                        "match_run_id": request.match_run_id,
                        "job_id": run.job_id,
                        "value": _value(request.value),
                        "comment": request.comment,
                        "supersedes_feedback_id": request.supersedes_feedback_id,
                    }
                    if isinstance(request, RankingFeedbackCreate):
                        await self._ranking_fields(request, fields, active_session)
                    elif isinstance(request, ExplanationFeedbackCreate):
                        await self._explanation_fields(request, fields, active_session)
                    elif isinstance(request, ProfileDataFeedbackCreate):
                        await self._profile_fields(request, fields, active_session)
                    record = FeedbackRecordModel(**fields)
                    await self.repository.create(record, session=active_session)
                    await active_session.refresh(record)
                    return _RECORD_ADAPTER.validate_python(_record_payload(record))
        except (HistoricalOwnerNotFoundError, FeedbackNotFoundError) as error:
            raise Phase10NotFoundError("Historical review target was not found") from error
        except (HistoricalOwnershipError, HistoricalIntegrityError) as error:
            raise HistoricalTargetError("Historical review target is invalid") from error
        except FeedbackConflictError as error:
            raise ReviewConflictError("Feedback conflicts with immutable history") from error

    async def _ranking_fields(self, request, fields, session) -> None:
        fields["reason_code"] = _value(request.reason_code) if request.reason_code else None
        fields["expected_candidate_reference"] = request.expected_candidate_reference
        if request.subject_match_result_id is not None:
            subject = await self.repository.resolve_match_result(
                request.match_run_id, request.subject_match_result_id, session=session
            )
            if request.target_type.value == "top1" and subject.result_rank != 1:
                raise HistoricalTargetError("Top-1 feedback must target persisted rank one")
            fields.update(
                match_result_id=subject.match_result_id,
                candidate_id=subject.candidate_id,
                result_rank=subject.result_rank,
            )
        if request.comparison_match_result_id is not None:
            comparison = await self.repository.resolve_match_result(
                request.match_run_id,
                request.comparison_match_result_id,
                session=session,
            )
            if comparison.match_result_id == fields.get("match_result_id"):
                raise HistoricalTargetError("Pairwise feedback requires distinct results")
            fields.update(
                comparison_match_result_id=comparison.match_result_id,
                comparison_candidate_id=comparison.candidate_id,
                comparison_result_rank=comparison.result_rank,
            )

    async def _explanation_fields(self, request, fields, session) -> None:
        owner = await self.repository.resolve_explanation(
            request.match_run_id,
            request.explanation_run_id,
            request.match_explanation_id,
            session=session,
        )
        fields.update(
            match_result_id=owner.match_result_id,
            candidate_id=owner.candidate_id,
            result_rank=owner.result_rank,
            explanation_run_id=owner.explanation_run_id,
            match_explanation_id=owner.match_explanation_id,
            evidence_reference=request.evidence_reference,
        )
        if request.evidence_reference is not None:
            await self.repository.resolve_evidence(
                owner.explanation_run_id,
                request.evidence_reference,
                candidate_id=owner.candidate_id,
                result_rank=owner.result_rank,
                session=session,
            )

    async def _profile_fields(self, request, fields, session) -> None:
        snapshot = await self.repository.resolve_profile_snapshot(
            request.match_run_id,
            match_result_id=request.subject_match_result_id,
            session=session,
        )
        locator = request.field_locator.value
        owner, keys = _PROFILE_LOCATOR_KEYS[locator]
        payload = snapshot.candidate_snapshot if owner == "candidate" else snapshot.job_snapshot
        if not isinstance(payload, dict) or any(key not in payload for key in keys):
            raise HistoricalTargetError(
                "Field locator is unavailable in the persisted historical snapshot"
            )
        fields.update(
            match_result_id=snapshot.match_result_id,
            candidate_id=snapshot.candidate_id,
            result_rank=snapshot.result_rank,
            field_locator=locator,
        )


__all__ = ["FeedbackService"]
