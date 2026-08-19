from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().required_database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


@lru_cache
def get_repeatable_read_session_factory() -> async_sessionmaker[AsyncSession]:
    execution_engine = get_engine().execution_options(isolation_level="REPEATABLE READ")
    return async_sessionmaker(execution_engine, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        async with session.begin():
            yield session
