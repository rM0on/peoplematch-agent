from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.exceptions import (
    DomainValidationError,
    DuplicateProfileError,
    FrozenRecordError,
    ProfileNotFoundError,
)
from app.persistence.mappers import (
    apply_candidate_record,
    candidate_model_from_record,
    candidate_record_from_model,
)
from app.schemas.mutations import CandidateCreate, CandidatePatch
from app.schemas.persistence import CandidateRecord, DataOrigin


class CandidateService:
    def __init__(self, session, repository) -> None:
        self.session = session
        self.repository = repository

    async def get(self, candidate_id: str) -> CandidateRecord:
        model = await self.repository.get_by_id(candidate_id)
        if model is None:
            raise ProfileNotFoundError(f"Candidate {candidate_id} was not found")
        return candidate_record_from_model(model)

    async def list(
        self, *, limit: int, offset: int, seniority=None, city=None, target_role=None
    ):
        models = await self.repository.list(
            limit=limit,
            offset=offset,
            seniority=seniority,
            city=city,
            target_role=target_role,
        )
        total = await self.repository.count(seniority=seniority, city=city, target_role=target_role)
        return [candidate_record_from_model(model) for model in models], total

    async def create(self, payload: CandidateCreate) -> CandidateRecord:
        candidate_id = f"cand_usr_{uuid4().hex}"
        try:
            record = CandidateRecord.model_validate(
                {
                    "candidate_id": candidate_id,
                    **payload.model_dump(mode="json"),
                    "archetype": None,
                    "data_origin": DataOrigin.USER_CREATED,
                    "schema_version": "1.0",
                    "dataset_version": None,
                }
            )
        except ValidationError as exc:
            raise DomainValidationError(str(exc)) from exc
        try:
            async with self.session.begin_nested():
                self.repository.create(candidate_model_from_record(record))
                await self.session.flush()
        except IntegrityError as exc:
            raise DuplicateProfileError("Candidate or nested ID already exists") from exc
        return await self.get(candidate_id)

    async def patch(self, candidate_id: str, payload: CandidatePatch) -> CandidateRecord:
        try:
            async with self.session.begin_nested():
                model = await self.repository.get_by_id(candidate_id)
                if model is None:
                    raise ProfileNotFoundError(f"Candidate {candidate_id} was not found")
                if model.dataset_version is not None:
                    raise FrozenRecordError("Frozen dataset candidates are read-only")
                current = candidate_record_from_model(model)
                merged = current.model_dump(mode="json")
                merged.update(payload.model_dump(mode="json", exclude_unset=True))
                try:
                    updated = CandidateRecord.model_validate(merged)
                except ValidationError as exc:
                    raise DomainValidationError(str(exc)) from exc
                apply_candidate_record(
                    model,
                    updated,
                    changed_fields=set(payload.model_fields_set),
                )
                model.updated_at = datetime.now(timezone.utc)
                self.repository.update(model)
                await self.session.flush()
        except IntegrityError as exc:
            raise DuplicateProfileError("Candidate or nested ID already exists") from exc
        return await self.get(candidate_id)

    async def delete(self, candidate_id: str) -> None:
        async with self.session.begin_nested():
            model = await self.repository.get_by_id(candidate_id)
            if model is None:
                raise ProfileNotFoundError(f"Candidate {candidate_id} was not found")
            if model.dataset_version is not None:
                raise FrozenRecordError("Frozen dataset candidates are read-only")
            await self.repository.delete(model)
