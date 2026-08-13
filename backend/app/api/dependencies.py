from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.job_repository import JobRepository
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService


def get_candidate_service(
    session: AsyncSession = Depends(get_db_session),
) -> CandidateService:
    return CandidateService(session, CandidateRepository(session))


def get_job_service(session: AsyncSession = Depends(get_db_session)) -> JobService:
    return JobService(session, JobRepository(session))
