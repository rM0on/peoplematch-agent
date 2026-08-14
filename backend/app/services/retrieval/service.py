from __future__ import annotations

from time import perf_counter
from typing import Sequence

from app.exceptions import ProfileNotFoundError
from app.schemas.retrieval import (
    ChannelResult,
    RetrievalDiagnostics,
    RetrievalDocument,
    RetrievalEntityType,
    RetrievalFilters,
    RetrievalRequest,
    RetrievalResponseData,
    RetrievalResult,
    RetrievalStrategy,
)
from app.services.retrieval.documents import (
    RETRIEVAL_DOCUMENT_VERSION,
    build_candidate_document,
    build_job_document,
)
from app.services.retrieval.fusion import reciprocal_rank_fusion
from app.services.retrieval.indexing import validate_index_freshness
from app.services.retrieval.sparse import BM25Document, BM25Retriever


class RetrievalService:
    def __init__(
        self,
        *,
        candidate_repository,
        job_repository,
        embedding_provider,
        vector_store,
        candidate_collection: str,
        job_collection: str,
        rrf_k: int,
        bm25_k1: float,
        bm25_b: float,
        pool_minimum: int,
        pool_multiplier: int,
    ) -> None:
        self.candidate_repository = candidate_repository
        self.job_repository = job_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.candidate_collection = candidate_collection
        self.job_collection = job_collection
        self.rrf_k = rrf_k
        self.bm25_k1 = bm25_k1
        self.bm25_b = bm25_b
        self.pool_minimum = pool_minimum
        self.pool_multiplier = pool_multiplier

    async def retrieve_candidates(
        self, job_id: str, request: RetrievalRequest
    ) -> RetrievalResponseData:
        query_record = await self.job_repository.get_record_by_id(job_id)
        if query_record is None:
            raise ProfileNotFoundError(f"Job {job_id} was not found")
        corpus_records = await self.candidate_repository.list_all_records()
        return await self._retrieve(
            query_document=build_job_document(query_record),
            corpus_documents=[build_candidate_document(item) for item in corpus_records],
            collection_name=self.candidate_collection,
            request=request,
        )

    async def retrieve_jobs(
        self, candidate_id: str, request: RetrievalRequest
    ) -> RetrievalResponseData:
        query_record = await self.candidate_repository.get_record_by_id(candidate_id)
        if query_record is None:
            raise ProfileNotFoundError(f"Candidate {candidate_id} was not found")
        corpus_records = await self.job_repository.list_all_records()
        return await self._retrieve(
            query_document=build_candidate_document(query_record),
            corpus_documents=[build_job_document(item) for item in corpus_records],
            collection_name=self.job_collection,
            request=request,
        )

    @staticmethod
    def _eligible(
        documents: Sequence[RetrievalDocument], filters: RetrievalFilters | None
    ) -> list[RetrievalDocument]:
        eligible = list(documents)
        if filters and filters.cities:
            cities = set(filters.cities)
            eligible = [item for item in eligible if set(item.cities) & cities]
        if filters and filters.seniorities:
            seniorities = set(filters.seniorities)
            eligible = [
                item for item in eligible if set(item.seniorities) & seniorities
            ]
        return sorted(eligible, key=lambda item: item.entity_id)

    async def _retrieve(
        self,
        *,
        query_document: RetrievalDocument,
        corpus_documents: Sequence[RetrievalDocument],
        collection_name: str,
        request: RetrievalRequest,
    ) -> RetrievalResponseData:
        started = perf_counter()
        eligible = self._eligible(corpus_documents, request.filters)
        pool_size = min(
            len(eligible),
            max(self.pool_minimum, request.top_k * self.pool_multiplier),
        )
        dense_results: list[ChannelResult] = []
        sparse_results: list[ChannelResult] = []
        index_freshness = "not_required"

        dense_started = perf_counter()
        if request.strategy in {RetrievalStrategy.DENSE, RetrievalStrategy.HYBRID}:
            await validate_index_freshness(
                documents=corpus_documents,
                store=self.vector_store,
                collection_name=collection_name,
                expected_dimension=self.embedding_provider.descriptor.dimension,
            )
            index_freshness = "fresh"
            if pool_size:
                query_vector = await self.embedding_provider.embed_query(
                    query_document.text
                )
                dense_results = (
                    await self.vector_store.search(
                        collection_name=collection_name,
                        query_vector=query_vector,
                        limit=len(eligible),
                        filters=request.filters,
                    )
                )[:pool_size]
        dense_ms = (perf_counter() - dense_started) * 1000

        sparse_started = perf_counter()
        if request.strategy in {RetrievalStrategy.SPARSE, RetrievalStrategy.HYBRID}:
            retriever = BM25Retriever(
                [
                    BM25Document(entity_id=document.entity_id, text=document.text)
                    for document in eligible
                ],
                k1=self.bm25_k1,
                b=self.bm25_b,
            )
            sparse_results = retriever.search(
                query_document.text, limit=pool_size
            )
        sparse_ms = (perf_counter() - sparse_started) * 1000

        fusion_started = perf_counter()
        if request.strategy == RetrievalStrategy.HYBRID:
            fused = reciprocal_rank_fusion(
                dense_results, sparse_results, rrf_k=self.rrf_k
            )[: request.top_k]
            results = [
                RetrievalResult(
                    entity_id=item.entity_id,
                    rank=rank,
                    matched_channels=[
                        channel
                        for channel, channel_rank in (
                            ("dense", item.dense_rank),
                            ("sparse", item.sparse_rank),
                        )
                        if channel_rank is not None
                    ],
                    dense_rank=item.dense_rank,
                    dense_score=item.dense_score,
                    sparse_rank=item.sparse_rank,
                    sparse_score=item.sparse_score,
                    fusion_score=item.fusion_score,
                )
                for rank, item in enumerate(fused, start=1)
            ]
        else:
            channel = "dense" if request.strategy == RetrievalStrategy.DENSE else "sparse"
            channel_results = (
                dense_results if channel == "dense" else sparse_results
            )[: request.top_k]
            results = [
                RetrievalResult(
                    entity_id=item.entity_id,
                    rank=rank,
                    matched_channels=[channel],
                    dense_rank=item.rank if channel == "dense" else None,
                    dense_score=item.score if channel == "dense" else None,
                    sparse_rank=item.rank if channel == "sparse" else None,
                    sparse_score=item.score if channel == "sparse" else None,
                )
                for rank, item in enumerate(channel_results, start=1)
            ]
        fusion_ms = (perf_counter() - fusion_started) * 1000
        total_ms = (perf_counter() - started) * 1000
        result_type = (
            RetrievalEntityType.CANDIDATE
            if query_document.entity_type == RetrievalEntityType.JOB
            else RetrievalEntityType.JOB
        )
        return RetrievalResponseData(
            results=results,
            diagnostics=RetrievalDiagnostics(
                query_type=query_document.entity_type,
                query_id=query_document.entity_id,
                result_type=result_type,
                strategy=request.strategy,
                top_k_requested=request.top_k,
                returned_count=len(results),
                corpus_size=len(corpus_documents),
                eligible_count=len(eligible),
                dense_pool_size=len(dense_results),
                sparse_pool_size=len(sparse_results),
                embedding_provider=self.embedding_provider.descriptor.name,
                embedding_model=self.embedding_provider.descriptor.model,
                document_version=RETRIEVAL_DOCUMENT_VERSION,
                rrf_k=self.rrf_k,
                filters_applied=bool(
                    request.filters
                    and (request.filters.cities or request.filters.seniorities)
                ),
                index_freshness=index_freshness,
                dense_ms=dense_ms,
                sparse_ms=sparse_ms,
                fusion_ms=fusion_ms,
                total_ms=total_ms,
            ),
        )
