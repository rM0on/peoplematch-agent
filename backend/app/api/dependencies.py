from pathlib import Path
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import (
    get_db_session,
    get_repeatable_read_session_factory,
    get_session_factory,
)
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.job_repository import JobRepository
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService
from app.core.config import get_settings
from app.exceptions import ProviderUnavailableError
from app.services.profile_extraction.parser import ProfileExtractionService
from app.services.profile_extraction.factory import build_profile_extraction_provider
from app.services.features.service import FeatureEngineeringService
from app.services.retrieval.embedding import SentenceTransformerEmbeddingProvider
from app.services.retrieval.service import RetrievalService
from app.services.retrieval.vector_store import QdrantDenseVectorStore
from app.services.ranking.model import load_ranking_model
from app.services.ranking.service import RankingService
from app.services.cross_encoder.model import load_cross_encoder_model
from app.services.cross_encoder.service import CrossEncoderRerankingService
from app.repositories.match_run_repository import MatchRunRepository
from app.services.match_runs.lazy import LazyCrossEncoderRuntime
from app.services.match_runs.service import MatchRunService
from app.repositories.explanation_run_repository import ExplanationRunRepository
from app.repositories.explanation_attempt_repository import ExplanationAttemptRepository
from app.repositories.explanation_query_repository import ExplanationQueryRepository
from app.services.explanation.generation.factory import build_explanation_provider
from app.services.explanation.generation.provider import (
    ExplanationProviderConfigurationError,
)
from app.services.explanation.generation.orchestration import ExplanationGenerationService
from app.services.explanation.generation.pipeline import ExplanationGenerationPipeline
from app.repositories.recruiter_narrative_repository import RecruiterNarrativeRepository
from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
from app.services.explanation.presentation.service import RecruiterNarrativeService
from app.services.explanation.presentation.service_v2 import RecruiterNarrativeV2Service
from app.services.explanation.presentation.service_v2_1 import RecruiterNarrativeV2_1Service
from app.services.explanation.presentation.structured_service import RecruiterPropositionService
from app.services.requirement_review.service import RequirementReviewService
from app.services.feedback.service import FeedbackService
from app.services.bad_cases.service import BadCaseReviewService
from app.services.demo.indexes import DemoIndexService


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


@lru_cache
def get_runtime_extraction_provider():
    fixture_root = (
        Path(__file__).resolve().parents[3] / "data" / "samples" / "extraction"
    )
    try:
        return build_profile_extraction_provider(
            get_settings(), fixture_root=fixture_root
        )
    except ExplanationProviderConfigurationError as exc:
        raise ProviderUnavailableError(str(exc)) from None


async def close_runtime_extraction_provider() -> None:
    if get_runtime_extraction_provider.cache_info().currsize == 0:
        return
    provider, _descriptor = get_runtime_extraction_provider()
    try:
        close = getattr(provider, "aclose", None)
        if close is not None:
            await close()
    finally:
        get_runtime_extraction_provider.cache_clear()


def get_profile_extraction_service(
    session: AsyncSession = Depends(get_db_session),
) -> ProfileExtractionService:
    settings = get_settings()
    provider, descriptor = get_runtime_extraction_provider()
    return ProfileExtractionService(
        provider,
        descriptor,
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


def get_demo_index_service(
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> DemoIndexService:
    return DemoIndexService(retrieval_service)


def get_feature_engineering_service(
    session: AsyncSession = Depends(get_db_session),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> FeatureEngineeringService:
    return FeatureEngineeringService(
        retrieval_service=retrieval_service,
        candidate_repository=CandidateRepository(session),
        job_repository=JobRepository(session),
    )


@lru_cache
def get_runtime_ranking_model():
    settings = get_settings()
    return load_ranking_model(
        model_path=Path(settings.ranking_model_path),
        metadata_path=Path(settings.ranking_model_metadata_path),
    )


def get_ranking_service(
    feature_service: FeatureEngineeringService = Depends(
        get_feature_engineering_service
    ),
    ranking_model=Depends(get_runtime_ranking_model),
) -> RankingService:
    return RankingService(
        feature_service=feature_service,
        ranking_model=ranking_model,
    )


@lru_cache
def get_runtime_cross_encoder_model():
    settings = get_settings()
    return load_cross_encoder_model(
        model_path=Path(settings.cross_encoder_model_path),
        manifest_path=Path(settings.cross_encoder_model_manifest_path),
        text_contract_path=Path(settings.cross_encoder_text_contract_path),
    )


def get_cross_encoder_reranking_service(
    session: AsyncSession = Depends(get_db_session),
    ranking_service: RankingService = Depends(get_ranking_service),
    cross_encoder_model=Depends(get_runtime_cross_encoder_model),
) -> CrossEncoderRerankingService:
    return CrossEncoderRerankingService(
        ranking_service=ranking_service,
        cross_encoder_model=cross_encoder_model,
        job_repository=JobRepository(session),
        candidate_repository=CandidateRepository(session),
        batch_size=get_settings().cross_encoder_batch_size,
    )


def get_match_run_service(
    session: AsyncSession = Depends(get_db_session),
) -> MatchRunService:
    def ranking_service_factory() -> RankingService:
        retrieval_service = get_retrieval_service(session)
        feature_service = get_feature_engineering_service(session, retrieval_service)
        return RankingService(
            feature_service=feature_service,
            ranking_model=get_runtime_ranking_model(),
        )

    def cross_encoder_service_factory(ranking_service) -> CrossEncoderRerankingService:
        return CrossEncoderRerankingService(
            ranking_service=ranking_service,
            cross_encoder_model=LazyCrossEncoderRuntime(get_runtime_cross_encoder_model),
            job_repository=JobRepository(session),
            candidate_repository=CandidateRepository(session),
            batch_size=get_settings().cross_encoder_batch_size,
        )

    def execution_graph_factory(execution_session: AsyncSession):
        retrieval_service = get_retrieval_service(execution_session)
        feature_service = get_feature_engineering_service(
            execution_session, retrieval_service
        )
        ranking_service_factory = lambda: RankingService(
            feature_service=feature_service,
            ranking_model=get_runtime_ranking_model(),
        )

        def execution_cross_encoder_factory(ranking_service):
            return CrossEncoderRerankingService(
                ranking_service=ranking_service,
                cross_encoder_model=LazyCrossEncoderRuntime(
                    get_runtime_cross_encoder_model
                ),
                job_repository=JobRepository(execution_session),
                candidate_repository=CandidateRepository(execution_session),
                batch_size=get_settings().cross_encoder_batch_size,
            )

        return {
            "job_repository": JobRepository(execution_session),
            "candidate_repository": CandidateRepository(execution_session),
            "ranking_service_factory": ranking_service_factory,
            "cross_encoder_service_factory": execution_cross_encoder_factory,
        }

    return MatchRunService(
        lifecycle_repository=MatchRunRepository(get_session_factory()),
        job_repository=JobRepository(session),
        candidate_repository=CandidateRepository(session),
        ranking_service_factory=ranking_service_factory,
        cross_encoder_service_factory=cross_encoder_service_factory,
        execution_session_factory=get_repeatable_read_session_factory(),
        execution_graph_factory=execution_graph_factory,
    )


@lru_cache
def get_runtime_explanation_provider():
    try:
        return build_explanation_provider(get_settings())
    except ExplanationProviderConfigurationError:
        raise ProviderUnavailableError("Explanation provider is unavailable") from None


async def close_runtime_explanation_provider() -> None:
    if get_runtime_explanation_provider.cache_info().currsize == 0:
        return
    provider = get_runtime_explanation_provider()
    try:
        close = getattr(provider, "aclose", None)
        if close is not None:
            await close()
    finally:
        get_runtime_explanation_provider.cache_clear()


def get_explanation_generation_service() -> ExplanationGenerationService:
    settings = get_settings()
    session_factory = get_session_factory()
    return ExplanationGenerationService(
        match_run_repository=MatchRunRepository(session_factory),
        explanation_repository=ExplanationRunRepository(session_factory),
        attempt_repository=ExplanationAttemptRepository(session_factory),
        query_repository=ExplanationQueryRepository(session_factory),
        provider=get_runtime_explanation_provider(),
        pipeline=ExplanationGenerationPipeline(
            max_output_tokens=settings.explanation_max_output_tokens,
            max_prompt_bytes=settings.explanation_max_prompt_bytes,
        ),
        max_attempts=settings.explanation_max_attempts,
    )


@lru_cache
def get_runtime_recruiter_narrative_provider():
    return build_recruiter_narrative_provider(get_settings())


async def close_runtime_recruiter_narrative_provider() -> None:
    if get_runtime_recruiter_narrative_provider.cache_info().currsize == 0:
        return
    provider = get_runtime_recruiter_narrative_provider()
    try:
        await provider.aclose()
    finally:
        get_runtime_recruiter_narrative_provider.cache_clear()


def get_recruiter_narrative_service() -> RecruiterNarrativeService:
    return RecruiterNarrativeService(
        repository=RecruiterNarrativeRepository(get_session_factory()),
        provider=get_runtime_recruiter_narrative_provider(),
        max_output_tokens=get_settings().recruiter_narrative_max_output_tokens,
    )


def get_recruiter_narrative_query_service() -> RecruiterNarrativeService:
    return RecruiterNarrativeService(
        repository=RecruiterNarrativeRepository(get_session_factory()),
    )


def get_recruiter_proposition_service() -> RecruiterPropositionService:
    """Read historical grounded source only; no Narrative provider is initialized."""
    return RecruiterPropositionService(
        RecruiterNarrativeRepository(get_session_factory())
    )


def get_requirement_review_service() -> RequirementReviewService:
    """Reuse canonical persisted-source and proposition validation; never call a Provider."""
    repository = RecruiterNarrativeRepository(get_session_factory())
    return RequirementReviewService(repository, RecruiterPropositionService(repository))


def get_recruiter_narrative_v2_service() -> RecruiterNarrativeV2Service:
    return RecruiterNarrativeV2Service(
        repository=RecruiterNarrativeRepository(get_session_factory()),
        provider=get_runtime_recruiter_narrative_provider(),
        max_output_tokens=get_settings().recruiter_narrative_v2_max_output_tokens,
    )


def get_recruiter_narrative_v2_query_service() -> RecruiterNarrativeV2Service:
    return RecruiterNarrativeV2Service(
        repository=RecruiterNarrativeRepository(get_session_factory()),
    )


def get_recruiter_narrative_v2_1_service() -> RecruiterNarrativeV2_1Service:
    return RecruiterNarrativeV2_1Service(
        repository=RecruiterNarrativeRepository(get_session_factory()),
        provider=get_runtime_recruiter_narrative_provider(),
        max_output_tokens=get_settings().recruiter_narrative_v2_max_output_tokens,
    )


def get_recruiter_narrative_v2_1_query_service() -> RecruiterNarrativeV2_1Service:
    return RecruiterNarrativeV2_1Service(
        repository=RecruiterNarrativeRepository(get_session_factory()),
    )


def get_feedback_service() -> FeedbackService:
    return FeedbackService(get_session_factory())


def get_bad_case_review_service() -> BadCaseReviewService:
    return BadCaseReviewService(get_session_factory())
