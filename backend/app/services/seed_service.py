from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.mappers import (
    candidate_model_from_profile,
    candidate_record_from_model,
    job_model_from_profile,
    job_record_from_model,
)
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.job_repository import JobRepository
from app.services.dataset_validation import load_dataset


DATASET_VERSION = "1.0.0"


class SeedConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class SeedReport:
    candidates_inserted: int
    candidates_unchanged: int
    jobs_inserted: int
    jobs_unchanged: int


async def seed_frozen_profiles(
    session: AsyncSession, repository_root: Path
) -> SeedReport:
    bundle = load_dataset(repository_root)
    candidate_repository = CandidateRepository(session)
    job_repository = JobRepository(session)
    candidate_inserted = candidate_unchanged = 0
    job_inserted = job_unchanged = 0

    async with session.begin_nested():
        for profile in bundle.candidates:
            existing = await candidate_repository.get_by_id(profile.candidate_id)
            if existing is None:
                candidate_repository.create(
                    candidate_model_from_profile(
                        profile, dataset_version=DATASET_VERSION
                    )
                )
                candidate_inserted += 1
                continue
            record = candidate_record_from_model(existing)
            if (
                record.dataset_version != DATASET_VERSION
                or record.to_canonical_profile() != profile
            ):
                raise SeedConflictError(
                    f"Frozen candidate conflict: {profile.candidate_id}"
                )
            candidate_unchanged += 1

        for profile in bundle.jobs:
            existing = await job_repository.get_by_id(profile.job_id)
            if existing is None:
                job_repository.create(
                    job_model_from_profile(profile, dataset_version=DATASET_VERSION)
                )
                job_inserted += 1
                continue
            record = job_record_from_model(existing)
            if (
                record.dataset_version != DATASET_VERSION
                or record.to_canonical_profile() != profile
            ):
                raise SeedConflictError(f"Frozen job conflict: {profile.job_id}")
            job_unchanged += 1

        await session.flush()

    return SeedReport(
        candidates_inserted=candidate_inserted,
        candidates_unchanged=candidate_unchanged,
        jobs_inserted=job_inserted,
        jobs_unchanged=job_unchanged,
    )
