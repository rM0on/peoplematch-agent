from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.exceptions import MatchRunConflictError, MatchRunNotFoundError
from app.models.match_run import MatchResultModel, MatchRunModel, RunStepModel


class MatchRunRepository:
    """Aggregate repository whose methods each own a durable transaction."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _load_options():
        return (
            selectinload(MatchRunModel.results),
            selectinload(MatchRunModel.steps),
        )

    @staticmethod
    async def _running(session, run_id: str) -> MatchRunModel:
        run = await session.scalar(
            select(MatchRunModel)
            .where(MatchRunModel.run_id == run_id)
            .with_for_update()
        )
        if run is None:
            raise MatchRunNotFoundError(f"Match run {run_id} was not found")
        if run.status != "RUNNING":
            raise MatchRunConflictError("Terminal match runs are immutable")
        return run

    async def create_running(self, run: MatchRunModel) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                session.add(run)

    async def resolve_job(self, *, run_id: str, **values) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                run = await self._running(session, run_id)
                for key, value in values.items():
                    setattr(run, key, value)

    async def start_step(self, step: RunStepModel) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await self._running(session, step.run_id)
                session.add(step)

    async def complete_step(self, run_id: str, sequence: int, **values) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await self._running(session, run_id)
                step = await session.scalar(
                    select(RunStepModel)
                    .where(
                        RunStepModel.run_id == run_id,
                        RunStepModel.sequence == sequence,
                    )
                    .with_for_update()
                )
                if step is None or step.status != "RUNNING":
                    raise MatchRunConflictError("Run step is not mutable")
                step.status = "COMPLETED"
                for key, value in values.items():
                    setattr(step, key, value)

    async def finalize_failed(self, run_id: str, **values) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                run = await self._running(session, run_id)
                if values.get("sequence") is not None:
                    step = await session.scalar(
                        select(RunStepModel)
                        .where(
                            RunStepModel.run_id == run_id,
                            RunStepModel.sequence == values["sequence"],
                        )
                        .with_for_update()
                    )
                    if step is None:
                        step = values["step"]
                        session.add(step)
                    elif step.status != "RUNNING":
                        raise MatchRunConflictError("Run step is not mutable")
                    step.status = "FAILED"
                    step.finished_at = values["finished_at"]
                    step.duration_ms = values["duration_ms"]
                    step.error_code = values["error_code"]
                    step.error_detail_safe = values["error_detail_safe"]
                run.status = "FAILED"
                run.completed_at = values["finished_at"]
                run.error_code = values["error_code"]
                run.error_detail_safe = values["error_detail_safe"]

    async def finalize_results_atomically(
        self,
        run_id: str,
        results: Sequence[MatchResultModel],
        **values,
    ) -> None:
        ranks = [item.result_rank for item in results]
        candidate_ids = [item.candidate_id for item in results]
        if ranks != list(range(1, len(results) + 1)):
            raise MatchRunConflictError("Result ranks must be contiguous from one")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise MatchRunConflictError("Result candidates must be unique")
        async with self.session_factory() as session:
            async with session.begin():
                run = await self._running(session, run_id)
                step = await session.scalar(
                    select(RunStepModel)
                    .where(
                        RunStepModel.run_id == run_id,
                        RunStepModel.step_name == "persist_results",
                    )
                    .with_for_update()
                )
                if step is None or step.status != "RUNNING":
                    raise MatchRunConflictError("Persist-results step is not mutable")
                session.add_all(results)
                step.status = "COMPLETED"
                step.finished_at = values["finished_at"]
                step.duration_ms = values["duration_ms"]
                step.output_refs = values["output_refs"]
                run.status = "COMPLETED"
                run.completed_at = values["finished_at"]
                run.result_count = len(results)
                run.result_fingerprint = values["result_fingerprint"]
                run.ce_provenance = values.get("ce_provenance")
                run.retrieval_provenance = values.get("retrieval_provenance")

    async def get_by_run_id(self, run_id: str) -> Optional[MatchRunModel]:
        async with self.session_factory() as session:
            statement = (
                select(MatchRunModel)
                .where(MatchRunModel.run_id == run_id)
                .options(*self._load_options())
            )
            return (await session.scalars(statement)).unique().one_or_none()

    async def list_runs(
        self,
        *,
        limit: int,
        offset: int,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        ranking_variant: Optional[str] = None,
    ) -> tuple[Sequence[MatchRunModel], int]:
        filters = []
        if job_id is not None:
            filters.append(MatchRunModel.job_id == job_id)
        if status is not None:
            filters.append(MatchRunModel.status == status)
        if ranking_variant is not None:
            filters.append(MatchRunModel.ranking_variant == ranking_variant)
        async with self.session_factory() as session:
            total = int(
                await session.scalar(
                    select(func.count()).select_from(MatchRunModel).where(*filters)
                )
                or 0
            )
            statement = (
                select(MatchRunModel)
                .where(*filters)
                .order_by(MatchRunModel.created_at.desc(), MatchRunModel.run_id.desc())
                .limit(limit)
                .offset(offset)
            )
            items = (await session.scalars(statement)).unique().all()
            return items, total
