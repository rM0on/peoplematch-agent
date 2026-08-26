from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.phase10_errors import Phase10TransactionError


@asynccontextmanager
async def repository_session(
    session_factory,
    session: Optional[AsyncSession],
    *,
    write: bool,
) -> AsyncIterator[AsyncSession]:
    """Use an active caller transaction or own one short repository transaction."""

    if session is not None:
        if not session.in_transaction():
            raise Phase10TransactionError(
                "Caller-provided repository session requires an active transaction"
            )
        yield session
        return

    async with session_factory() as owned_session:
        if write:
            async with owned_session.begin():
                yield owned_session
        else:
            yield owned_session


__all__ = ["repository_session"]
