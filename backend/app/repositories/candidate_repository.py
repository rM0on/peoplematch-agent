from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.candidate import CandidateProfileModel


class CandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _options():
        return (
            selectinload(CandidateProfileModel.skills),
            selectinload(CandidateProfileModel.projects),
            selectinload(CandidateProfileModel.evidence),
        )

    @staticmethod
    def _filters(*, seniority=None, city=None, target_role=None):
        clauses = []
        if seniority:
            clauses.append(CandidateProfileModel.seniority == seniority)
        if city:
            clauses.append(
                CandidateProfileModel.preferred_locations["cities"].contains([city])
            )
        if target_role:
            clauses.append(CandidateProfileModel.target_roles.contains([target_role]))
        return clauses

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        seniority=None,
        city=None,
        target_role=None,
    ) -> Sequence[CandidateProfileModel]:
        statement = (
            select(CandidateProfileModel)
            .where(*self._filters(seniority=seniority, city=city, target_role=target_role))
            .options(*self._options())
            .order_by(CandidateProfileModel.candidate_id)
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.scalars(statement)).all()

    async def count(self, *, seniority=None, city=None, target_role=None) -> int:
        statement = select(func.count()).select_from(CandidateProfileModel).where(
            *self._filters(seniority=seniority, city=city, target_role=target_role)
        )
        return int(await self.session.scalar(statement) or 0)

    async def get_by_id(
        self, candidate_id: str
    ) -> Optional[CandidateProfileModel]:
        statement = (
            select(CandidateProfileModel)
            .where(CandidateProfileModel.candidate_id == candidate_id)
            .options(*self._options())
        )
        return (await self.session.scalars(statement)).unique().one_or_none()

    async def exists(self, candidate_id: str) -> bool:
        statement = (
            select(func.count())
            .select_from(CandidateProfileModel)
            .where(CandidateProfileModel.candidate_id == candidate_id)
        )
        return bool(await self.session.scalar(statement))

    def create(self, model: CandidateProfileModel) -> None:
        self.session.add(model)

    def update(self, model: CandidateProfileModel) -> None:
        self.session.add(model)

    async def delete(self, model: CandidateProfileModel) -> None:
        await self.session.delete(model)
