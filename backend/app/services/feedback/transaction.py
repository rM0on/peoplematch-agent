from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.feedback.errors import ReviewConflictError


@asynccontextmanager
async def service_session(
    session_factory,
    session: Optional[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Use a caller transaction or own exactly one short service transaction."""

    if session is not None:
        if not session.in_transaction():
            raise ReviewConflictError(
                "Caller-provided service session requires an active transaction"
            )
        yield session
        return

    async with session_factory() as owned_session:
        async with owned_session.begin():
            yield owned_session


__all__ = ["service_session"]
