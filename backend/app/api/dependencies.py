from pathlib import Path
from functools import lru_cache

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
from app.services.features.service import FeatureEngineeringService
from app.services.retrieval.embedding import SentenceTransformerEmbeddingProvider
from app.services.retrieval.service import RetrievalService
from app.services.retrieval.vector_store import QdrantDenseVectorStore


@lru_cache
def get_runtime_embedding_provider() -> SentenceTransformerEmbeddingProvider:
    settings = get_settings()
    return SentenceTransformerEmbeddingProvider(
        model_name=settings.retrieval_embedding_model,
        dimension=settings.retrieval_embedding_dimension,
    )


@lru_cache
def get_runtime_vector_store() -> QdrantDenseVectorStore:
    return QdrantDenseVectorStore(url=get_settings().qdrant_url)


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


def get_retrieval_service(
    session: AsyncSession = Depends(get_db_session),
) -> RetrievalService:
    settings = get_settings()
    if settings.retrieval_embedding_provider != "sentence_transformers":
        from app.exceptions import EmbeddingProviderUnavailableError

        raise EmbeddingProviderUnavailableError(
            f"Embedding provider '{settings.retrieval_embedding_provider}' is not implemented"
        )
    provider = get_runtime_embedding_provider()
    store = get_runtime_vector_store()
    return RetrievalService(
        candidate_repository=CandidateRepository(session),
        job_repository=JobRepository(session),
        embedding_provider=provider,
        vector_store=store,
        candidate_collection=settings.retrieval_candidate_collection,
        job_collection=settings.retrieval_job_collection,
        rrf_k=settings.retrieval_rrf_k,
        bm25_k1=settings.retrieval_bm25_k1,
        bm25_b=settings.retrieval_bm25_b,
        pool_minimum=settings.retrieval_pool_minimum,
        pool_multiplier=settings.retrieval_pool_multiplier,
    )


def get_feature_engineering_service(
    session: AsyncSession = Depends(get_db_session),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> FeatureEngineeringService:
    return FeatureEngineeringService(
        retrieval_service=retrieval_service,
        candidate_repository=CandidateRepository(session),
        job_repository=JobRepository(session),
    )
