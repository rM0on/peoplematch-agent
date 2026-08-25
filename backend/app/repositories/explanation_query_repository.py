from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.explanation_run import ExplanationRunModel
from app.models.match_run import MatchRunModel


class ExplanationQueryRepository:
    """Read optimized explanation runs without loading audit JSON by default."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def get_detail(self, explanation_run_id: str) -> ExplanationRunModel | None:
        async with self.session_factory() as session:
            return (
                await session.scalars(
                    select(ExplanationRunModel)
                    .where(
                        ExplanationRunModel.explanation_run_id
                        == explanation_run_id
                    )
                    .options(selectinload(ExplanationRunModel.explanations))
                )
            ).unique().one_or_none()

    async def match_run_exists(self, match_run_id: str) -> bool:
        async with self.session_factory() as session:
            return (
                await session.scalar(
                    select(MatchRunModel.run_id).where(
                        MatchRunModel.run_id == match_run_id
                    )
                )
            ) is not None

    async def list_for_match_run(
        self,
        match_run_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[ExplanationRunModel], int]:
        async with self.session_factory() as session:
            total = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ExplanationRunModel)
                    .where(ExplanationRunModel.match_run_id == match_run_id)
                )
                or 0
            )
            items = (
                await session.scalars(
                    select(ExplanationRunModel)
                    .where(ExplanationRunModel.match_run_id == match_run_id)
                    .order_by(
                        ExplanationRunModel.created_at.desc(),
                        ExplanationRunModel.explanation_run_id.desc(),
                    )
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return items, total


__all__ = ["ExplanationQueryRepository"]
