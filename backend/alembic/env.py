import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models.base import target_metadata
from app.models.candidate import CandidateProfileModel  # noqa: F401
from app.models.job import JobProfileModel  # noqa: F401
from app.models.match_run import MatchRunModel  # noqa: F401
from app.models.explanation_run import ExplanationRunModel  # noqa: F401
from app.models.explanation_attempt import ExplanationGenerationAttemptModel  # noqa: F401
from app.models.feedback import FeedbackRecordModel, SystemSignalModel  # noqa: F401
from app.models.bad_case import (  # noqa: F401
    BadCaseAnalysisModel,
    BadCaseModel,
    BadCaseSourceLinkModel,
    BadCaseTransitionModel,
    FeedbackEvidenceLinkModel,
    ResolutionActionModel,
)


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = get_settings().database_url
if not database_url:
    raise RuntimeError("DATABASE_URL must be configured before running Alembic")
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
