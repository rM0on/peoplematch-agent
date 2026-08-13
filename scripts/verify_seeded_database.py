from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from sqlalchemy import func, select


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_engine, get_session_factory  # noqa: E402
from app.models.candidate import (  # noqa: E402
    CandidateProfileModel,
    CandidateProjectEvidenceModel,
    CandidateProjectModel,
    CandidateSkillModel,
)
from app.models.job import JobProfileModel, JobRequirementModel  # noqa: E402
from app.persistence.mappers import (  # noqa: E402
    candidate_record_from_model,
    job_record_from_model,
)
from app.repositories.candidate_repository import CandidateRepository  # noqa: E402
from app.repositories.job_repository import JobRepository  # noqa: E402
from app.services.dataset_validation import load_dataset  # noqa: E402


async def run() -> int:
    bundle = load_dataset(REPOSITORY_ROOT)
    expected_candidates = {profile.candidate_id: profile for profile in bundle.candidates}
    expected_jobs = {profile.job_id: profile for profile in bundle.jobs}
    try:
        async with get_session_factory()() as session:
            counts = {
                "candidates": int(
                    await session.scalar(
                        select(func.count())
                        .select_from(CandidateProfileModel)
                        .where(CandidateProfileModel.dataset_version == "1.0.0")
                    )
                    or 0
                ),
                "skills": int(
                    await session.scalar(
                        select(func.count())
                        .select_from(CandidateSkillModel)
                        .join(CandidateProfileModel)
                        .where(CandidateProfileModel.dataset_version == "1.0.0")
                    )
                    or 0
                ),
                "projects": int(
                    await session.scalar(
                        select(func.count())
                        .select_from(CandidateProjectModel)
                        .join(CandidateProfileModel)
                        .where(CandidateProfileModel.dataset_version == "1.0.0")
                    )
                    or 0
                ),
                "evidence": int(
                    await session.scalar(
                        select(func.count())
                        .select_from(CandidateProjectEvidenceModel)
                        .join(CandidateProfileModel)
                        .where(CandidateProfileModel.dataset_version == "1.0.0")
                    )
                    or 0
                ),
                "jobs": int(
                    await session.scalar(
                        select(func.count())
                        .select_from(JobProfileModel)
                        .where(JobProfileModel.dataset_version == "1.0.0")
                    )
                    or 0
                ),
                "requirements": int(
                    await session.scalar(
                        select(func.count())
                        .select_from(JobRequirementModel)
                        .join(JobProfileModel)
                        .where(JobProfileModel.dataset_version == "1.0.0")
                    )
                    or 0
                ),
            }
            expected_counts = {
                "candidates": len(bundle.candidates),
                "skills": sum(len(profile.skills) for profile in bundle.candidates),
                "projects": sum(len(profile.projects) for profile in bundle.candidates),
                "evidence": sum(len(profile.project_evidence) for profile in bundle.candidates),
                "jobs": len(bundle.jobs),
                "requirements": sum(len(profile.must_have) + len(profile.nice_to_have) for profile in bundle.jobs),
            }
            if counts != expected_counts:
                raise RuntimeError(f"Seed count mismatch: actual={counts}, expected={expected_counts}")

            for candidate_id in ("cand_005", "cand_041", "cand_048"):
                model = await CandidateRepository(session).get_by_id(candidate_id)
                if model is None or candidate_record_from_model(model).to_canonical_profile() != expected_candidates[candidate_id]:
                    raise RuntimeError(f"Seed candidate mismatch: {candidate_id}")
            for job_id in ("job_001", "job_020", "job_024"):
                model = await JobRepository(session).get_by_id(job_id)
                if model is None or job_record_from_model(model).to_canonical_profile() != expected_jobs[job_id]:
                    raise RuntimeError(f"Seed job mismatch: {job_id}")

        print(f"Seed verification PASS: {counts}; deterministic samples matched canonical input.")
        return 0
    finally:
        await get_engine().dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
