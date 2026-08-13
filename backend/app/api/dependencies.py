from pathlib import Path

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.job_repository import JobRepository
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService
from app.core.config import get_settings
from app.exceptions import ProviderUnavailableError
from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
from app.services.profile_extraction.parser import ProfileExtractionService
from app.services.profile_extraction.provider import MOCK_PROVIDER_DESCRIPTOR


def get_candidate_service(
    session: AsyncSession = Depends(get_db_session),
) -> CandidateService:
    return CandidateService(session, CandidateRepository(session))


def get_job_service(session: AsyncSession = Depends(get_db_session)) -> JobService:
    return JobService(session, JobRepository(session))


def get_profile_extraction_service(
    session: AsyncSession = Depends(get_db_session),
) -> ProfileExtractionService:
    settings = get_settings()
    if settings.extraction_provider != "mock":
        raise ProviderUnavailableError(
            f"Extraction provider '{settings.extraction_provider}' is not implemented"
        )
    fixture_root = (
        Path(__file__).resolve().parents[3] / "data" / "samples" / "extraction"
    )
    provider = MockStructuredOutputProvider.from_fixture_directory(fixture_root)
    return ProfileExtractionService(
        provider,
        MOCK_PROVIDER_DESCRIPTOR,
        max_attempts=settings.extraction_max_attempts,
        timeout_seconds=settings.extraction_timeout_seconds,
        candidate_service=CandidateService(session, CandidateRepository(session)),
        job_service=JobService(session, JobRepository(session)),
    )
