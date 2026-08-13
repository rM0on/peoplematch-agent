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
from app.persistence.mappers import apply_job_record, job_model_from_record, job_record_from_model
from app.schemas.mutations import JobCreate, JobPatch
from app.schemas.persistence import DataOrigin, JobRecord


class JobService:
    def __init__(self, session, repository) -> None:
        self.session = session
        self.repository = repository

    async def get(self, job_id: str) -> JobRecord:
        model = await self.repository.get_by_id(job_id)
        if model is None:
            raise ProfileNotFoundError(f"Job {job_id} was not found")
        return job_record_from_model(model)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        role_title=None,
        role_direction=None,
        city=None,
        seniority=None,
    ):
        models = await self.repository.list(
            limit=limit,
            offset=offset,
            role_title=role_title,
            role_direction=role_direction,
            city=city,
            seniority=seniority,
        )
        total = await self.repository.count(
            role_title=role_title,
            role_direction=role_direction,
            city=city,
            seniority=seniority,
        )
        return [job_record_from_model(model) for model in models], total

    async def create(self, payload: JobCreate) -> JobRecord:
        job_id = f"job_usr_{uuid4().hex}"
        try:
            record = JobRecord.model_validate(
                {
                    "job_id": job_id,
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
                self.repository.create(job_model_from_record(record))
                await self.session.flush()
        except IntegrityError as exc:
            raise DuplicateProfileError("Job or requirement ID already exists") from exc
        return await self.get(job_id)

    async def patch(self, job_id: str, payload: JobPatch) -> JobRecord:
        try:
            async with self.session.begin_nested():
                model = await self.repository.get_by_id(job_id)
                if model is None:
                    raise ProfileNotFoundError(f"Job {job_id} was not found")
                if model.dataset_version is not None:
                    raise FrozenRecordError("Frozen dataset jobs are read-only")
                current = job_record_from_model(model)
                merged = current.model_dump(mode="json")
                merged.update(payload.model_dump(mode="json", exclude_unset=True))
                try:
                    updated = JobRecord.model_validate(merged)
                except ValidationError as exc:
                    raise DomainValidationError(str(exc)) from exc
                apply_job_record(
                    model,
                    updated,
                    changed_fields=set(payload.model_fields_set),
                )
                model.updated_at = datetime.now(timezone.utc)
                self.repository.update(model)
                await self.session.flush()
        except IntegrityError as exc:
            raise DuplicateProfileError("Job or requirement ID already exists") from exc
        return await self.get(job_id)

    async def delete(self, job_id: str) -> None:
        async with self.session.begin_nested():
            model = await self.repository.get_by_id(job_id)
            if model is None:
                raise ProfileNotFoundError(f"Job {job_id} was not found")
            if model.dataset_version is not None:
                raise FrozenRecordError("Frozen dataset jobs are read-only")
            await self.repository.delete(model)
