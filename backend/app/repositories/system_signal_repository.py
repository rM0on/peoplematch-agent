from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import SystemSignalModel
from app.repositories.phase10_transaction import repository_session


class SystemSignalRepository:
    """Read-only lookup for deterministically persisted Phase 10 signals."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def get_by_id(
        self,
        signal_id: str,
        *,
        session: Optional[AsyncSession] = None,
    ) -> Optional[SystemSignalModel]:
        async with repository_session(
            self.session_factory, session, write=False
        ) as active_session:
            return await active_session.get(SystemSignalModel, signal_id)


__all__ = ["SystemSignalRepository"]
