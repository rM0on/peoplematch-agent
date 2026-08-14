from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _records(path: str, model):
    return [
        model.model_validate(json.loads(line))
        for line in (REPOSITORY_ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class CandidateRepo:
    def __init__(self, records):
        self.records = records

    async def get_record_by_id(self, entity_id):
        return next((item for item in self.records if item.candidate_id == entity_id), None)

    async def list_all_records(self):
        return list(self.records)


class JobRepo:
    def __init__(self, records):
        self.records = records

    async def get_record_by_id(self, entity_id):
        return next((item for item in self.records if item.job_id == entity_id), None)

    async def list_all_records(self):
        return list(self.records)


class MemoryStore:
    def __init__(self, provider):
        self.provider = provider
        self.documents = {}
        self.last_search_limit = None

    async def collection_exists(self, collection_name):
        return collection_name in self.documents

    async def collection_dimension(self, collection_name):
        return self.provider.descriptor.dimension

    async def collection_distance(self, collection_name):
        return "Cosine"

    async def list_payloads(self, collection_name):
        from app.services.retrieval.vector_store import payload_for

        return {
            document.entity_id: payload_for(document)
            for document in self.documents[collection_name]
        }

    async def search(self, *, collection_name, query_vector, limit, filters):
        from app.schemas.retrieval import ChannelResult

        self.last_search_limit = limit
        candidates = self.documents[collection_name]
        if filters and filters.cities:
            candidates = [
                item for item in candidates if set(item.cities) & set(filters.cities)
            ]
        if filters and filters.seniorities:
            candidates = [
                item
                for item in candidates
                if set(item.seniorities) & set(filters.seniorities)
            ]
        vectors = await self.provider.embed_documents([item.text for item in candidates])
        scored = sorted(
            (
                (item.entity_id, sum(a * b for a, b in zip(query_vector, vector)))
                for item, vector in zip(candidates, vectors)
            ),
            key=lambda value: (-value[1], value[0]),
        )[:limit]
        return [
            ChannelResult(entity_id=entity_id, rank=rank, score=score)
            for rank, (entity_id, score) in enumerate(scored, start=1)
        ]


def _service():
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobProfile
    from app.services.retrieval.documents import (
        build_candidate_document,
        build_job_document,
    )
    from app.services.retrieval.embedding import DeterministicTestEmbeddingProvider
    from app.services.retrieval.service import RetrievalService

    candidates = _records("data/samples/candidates.jsonl", CandidateProfile)[:4]
    jobs = _records("data/samples/jobs.jsonl", JobProfile)[:3]
    provider = DeterministicTestEmbeddingProvider(dimension=8)
    store = MemoryStore(provider)
    store.documents["candidates"] = [build_candidate_document(item) for item in candidates]
    store.documents["jobs"] = [build_job_document(item) for item in jobs]
    return RetrievalService(
        candidate_repository=CandidateRepo(candidates),
        job_repository=JobRepo(jobs),
        embedding_provider=provider,
        vector_store=store,
        candidate_collection="candidates",
        job_collection="jobs",
        rrf_k=60,
        bm25_k1=1.5,
        bm25_b=0.75,
        pool_minimum=20,
        pool_multiplier=3,
    ), candidates, jobs


@pytest.mark.parametrize("strategy", ["dense", "sparse", "hybrid"])
def test_job_to_candidates_supports_every_strategy_without_labels(strategy) -> None:
    from app.schemas.retrieval import RetrievalRequest

    service, candidates, jobs = _service()
    response = asyncio.run(
        service.retrieve_candidates(
            jobs[0].job_id,
            RetrievalRequest(strategy=strategy, top_k=3),
        )
    )

    assert 1 <= len(response.results) <= 3
    assert {item.entity_id for item in response.results} <= {
        item.candidate_id for item in candidates
    }
    assert [item.rank for item in response.results] == list(
        range(1, len(response.results) + 1)
    )
    assert response.diagnostics.strategy.value == strategy
    assert response.diagnostics.corpus_size == len(candidates)
    assert response.diagnostics.eligible_count == len(candidates)
    assert response.diagnostics.filters_applied is False
    serialized = response.model_dump_json()
    assert "relevance" not in serialized
    assert "grade" not in serialized
    assert "vector" not in serialized
    assert "location_score" not in serialized


@pytest.mark.parametrize("strategy", ["dense", "sparse", "hybrid"])
def test_candidate_to_jobs_reuses_every_strategy(strategy) -> None:
    from app.schemas.retrieval import RetrievalRequest

    service, candidates, jobs = _service()
    response = asyncio.run(
        service.retrieve_jobs(
            candidates[0].candidate_id,
            RetrievalRequest(strategy=strategy, top_k=2),
        )
    )

    assert len(response.results) <= 2
    assert {item.entity_id for item in response.results} <= {item.job_id for item in jobs}
    assert response.diagnostics.query_type.value == "candidate"
    assert response.diagnostics.result_type.value == "job"


def test_explicit_filter_reduces_eligible_corpus_without_adding_score() -> None:
    from app.schemas.retrieval import RetrievalFilters, RetrievalRequest

    service, _, jobs = _service()
    city = service.vector_store.documents["candidates"][0].cities[0]
    response = asyncio.run(
        service.retrieve_candidates(
            jobs[0].job_id,
            RetrievalRequest(
                strategy="hybrid",
                top_k=10,
                filters=RetrievalFilters(cities=[city]),
            ),
        )
    )

    assert response.diagnostics.filters_applied is True
    assert response.diagnostics.eligible_count < response.diagnostics.corpus_size
    eligible = {
        item.entity_id
        for item in service.vector_store.documents["candidates"]
        if city in item.cities
    }
    assert {item.entity_id for item in response.results} <= eligible
    assert all(not hasattr(item, "metadata_score") for item in response.results)


def test_explicit_seniority_filter_reduces_reverse_job_corpus() -> None:
    from app.schemas.retrieval import RetrievalFilters, RetrievalRequest

    service, candidates, _ = _service()
    seniority = service.vector_store.documents["jobs"][0].seniorities[0]
    response = asyncio.run(
        service.retrieve_jobs(
            candidates[0].candidate_id,
            RetrievalRequest(
                strategy="hybrid",
                top_k=10,
                filters=RetrievalFilters(seniorities=[seniority]),
            ),
        )
    )

    eligible = {
        item.entity_id
        for item in service.vector_store.documents["jobs"]
        if seniority in item.seniorities
    }
    assert response.diagnostics.filters_applied is True
    assert {item.entity_id for item in response.results} <= eligible


def test_empty_filter_object_is_reported_as_not_applied() -> None:
    from app.schemas.retrieval import RetrievalFilters, RetrievalRequest

    service, candidates, jobs = _service()
    response = asyncio.run(
        service.retrieve_candidates(
            jobs[0].job_id,
            RetrievalRequest(
                strategy="sparse", top_k=3, filters=RetrievalFilters()
            ),
        )
    )

    assert response.diagnostics.eligible_count == len(candidates)
    assert response.diagnostics.filters_applied is False


def test_dense_search_stabilizes_all_eligible_hits_before_pool_truncation() -> None:
    from app.schemas.retrieval import RetrievalRequest

    service, candidates, jobs = _service()
    service.pool_minimum = 1
    service.pool_multiplier = 1
    response = asyncio.run(
        service.retrieve_candidates(
            jobs[0].job_id,
            RetrievalRequest(strategy="dense", top_k=1),
        )
    )

    assert service.vector_store.last_search_limit == len(candidates)
    assert response.diagnostics.dense_pool_size == 1


def test_missing_query_uses_existing_profile_not_found_semantics() -> None:
    from app.exceptions import ProfileNotFoundError
    from app.schemas.retrieval import RetrievalRequest

    service, _, _ = _service()
    with pytest.raises(ProfileNotFoundError):
        asyncio.run(
            service.retrieve_candidates("job_missing", RetrievalRequest())
        )

    with pytest.raises(ProfileNotFoundError):
        asyncio.run(
            service.retrieve_jobs("candidate_missing", RetrievalRequest())
        )
