from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job import JobProfileModel
from app.persistence.mappers import job_record_from_model


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _filters(*, role_title=None, role_direction=None, city=None, seniority=None):
        clauses = []
        if role_title:
            clauses.append(JobProfileModel.role_title.ilike(f"%{role_title}%"))
        if role_direction:
            clauses.append(JobProfileModel.role_direction.contains([role_direction]))
        if city:
            clauses.append(JobProfileModel.location["cities"].contains([city]))
        if seniority:
            clauses.append(JobProfileModel.seniority_requirement.contains([seniority]))
        return clauses

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        role_title=None,
        role_direction=None,
        city=None,
        seniority=None,
    ) -> Sequence[JobProfileModel]:
        statement = (
            select(JobProfileModel)
            .where(
                *self._filters(
                    role_title=role_title,
                    role_direction=role_direction,
                    city=city,
                    seniority=seniority,
                )
            )
            .options(selectinload(JobProfileModel.requirements))
            .order_by(JobProfileModel.job_id)
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.scalars(statement)).all()

    async def count(
        self, *, role_title=None, role_direction=None, city=None, seniority=None
    ) -> int:
        statement = (
            select(func.count())
            .select_from(JobProfileModel)
            .where(
                *self._filters(
                    role_title=role_title,
                    role_direction=role_direction,
                    city=city,
                    seniority=seniority,
                )
            )
        )
        return int(await self.session.scalar(statement) or 0)

    async def get_by_id(self, job_id: str) -> Optional[JobProfileModel]:
        statement = (
            select(JobProfileModel)
            .where(JobProfileModel.job_id == job_id)
            .options(selectinload(JobProfileModel.requirements))
        )
        return (await self.session.scalars(statement)).unique().one_or_none()

    async def exists(self, job_id: str) -> bool:
        statement = (
            select(func.count())
            .select_from(JobProfileModel)
            .where(JobProfileModel.job_id == job_id)
        )
        return bool(await self.session.scalar(statement))

    async def get_record_by_id(self, job_id: str):
        model = await self.get_by_id(job_id)
        return job_record_from_model(model) if model is not None else None

    async def list_all_records(self):
        statement = (
            select(JobProfileModel)
            .options(selectinload(JobProfileModel.requirements))
            .order_by(JobProfileModel.job_id)
        )
        models = (await self.session.scalars(statement)).unique().all()
        return [job_record_from_model(model) for model in models]

    def create(self, model: JobProfileModel) -> None:
        self.session.add(model)

    def update(self, model: JobProfileModel) -> None:
        self.session.add(model)

    async def delete(self, model: JobProfileModel) -> None:
        await self.session.delete(model)
