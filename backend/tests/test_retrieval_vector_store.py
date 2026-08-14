from __future__ import annotations

import asyncio

import pytest


def test_point_id_and_payload_are_deterministic_and_allowlisted() -> None:
    from app.schemas.retrieval import CandidateRetrievalDocument
    from app.schemas.shared import Seniority
    from app.services.retrieval.vector_store import point_id_for, payload_for

    document = CandidateRetrievalDocument(
        entity_id="cand_example",
        document_version="retrieval_doc_v2",
        document_fingerprint="a" * 64,
        text="semantic text must not enter payload",
        cities=["Shanghai"],
        seniorities=[Seniority.MID],
    )

    assert point_id_for(document.entity_type, document.entity_id) == point_id_for(
        document.entity_type, document.entity_id
    )
    assert payload_for(document) == {
        "entity_id": "cand_example",
        "document_version": "retrieval_doc_v2",
        "document_fingerprint": "a" * 64,
        "cities": ["Shanghai"],
        "seniorities": ["mid"],
    }
    assert "text" not in payload_for(document)


def test_qdrant_adapter_requires_a_typed_runtime_configuration() -> None:
    from app.exceptions import VectorStoreUnavailableError
    from app.services.retrieval.vector_store import QdrantDenseVectorStore

    with pytest.raises(VectorStoreUnavailableError, match="URL is not configured"):
        QdrantDenseVectorStore(url=None)


def test_index_build_validates_embedding_count_and_dimension() -> None:
    from app.exceptions import EmbeddingDimensionMismatchError
    from app.schemas.retrieval import CandidateRetrievalDocument
    from app.services.retrieval.embedding import (
        EmbeddingProviderDescriptor,
        DeterministicTestEmbeddingProvider,
    )
    from app.services.retrieval.indexing import build_dense_index

    class RecordingStore:
        async def rebuild(self, collection_name, dimension, points):
            raise AssertionError("store must not be called after dimension failure")

    class BrokenProvider(DeterministicTestEmbeddingProvider):
        def __init__(self):
            self.descriptor = EmbeddingProviderDescriptor(
                name="broken",
                model="broken",
                dimension=4,
                provider_kind="test",
            )

        async def embed_documents(self, texts):
            return [[0.0, 1.0]] * len(texts)

    document = CandidateRetrievalDocument(
        entity_id="cand_example",
        document_version="retrieval_doc_v2",
        document_fingerprint="a" * 64,
        text="candidate retrieval",
        cities=[],
        seniorities=[],
    )

    with pytest.raises(EmbeddingDimensionMismatchError):
        asyncio.run(
            build_dense_index(
                documents=[document],
                provider=BrokenProvider(),
                store=RecordingStore(),
                collection_name="test",
            )
        )


def test_freshness_allows_exact_match_and_rejects_missing_changed_or_extra() -> None:
    from app.exceptions import RetrievalIndexMissingError, RetrievalIndexStaleError
    from app.schemas.retrieval import CandidateRetrievalDocument
    from app.services.retrieval.indexing import validate_index_freshness

    document = CandidateRetrievalDocument(
        entity_id="cand_example",
        document_version="retrieval_doc_v2",
        document_fingerprint="a" * 64,
        text="candidate retrieval",
        cities=[],
        seniorities=[],
    )

    class Store:
        def __init__(self, *, exists=True, payloads=None, dimension=8, distance="Cosine"):
            self.exists = exists
            self.payloads = payloads or {}
            self.dimension = dimension
            self.distance = distance

        async def collection_exists(self, collection_name):
            return self.exists

        async def collection_dimension(self, collection_name):
            return self.dimension

        async def collection_distance(self, collection_name):
            return self.distance

        async def list_payloads(self, collection_name):
            return self.payloads

    fresh_payload = {
        "cand_example": {
            "entity_id": "cand_example",
            "document_version": "retrieval_doc_v2",
            "document_fingerprint": "a" * 64,
            "cities": [],
            "seniorities": [],
        }
    }
    asyncio.run(
        validate_index_freshness(
            documents=[document],
            store=Store(payloads=fresh_payload),
            collection_name="test",
            expected_dimension=8,
        )
    )

    with pytest.raises(RetrievalIndexMissingError):
        asyncio.run(
            validate_index_freshness(
                documents=[document],
                store=Store(exists=False),
                collection_name="test",
                expected_dimension=8,
            )
        )

    for payloads, dimension in (
        ({}, 8),
        ({**fresh_payload, "cand_extra": {"entity_id": "cand_extra"}}, 8),
        ({"cand_example": {**fresh_payload["cand_example"], "document_fingerprint": "b" * 64}}, 8),
        ({"cand_example": {**fresh_payload["cand_example"], "cities": ["StaleCity"]}}, 8),
        ({"cand_example": {**fresh_payload["cand_example"], "seniorities": ["senior"]}}, 8),
        ({"cand_example": {**fresh_payload["cand_example"], "relevance_grade": 3}}, 8),
        (fresh_payload, 7),
    ):
        with pytest.raises(RetrievalIndexStaleError):
            asyncio.run(
                validate_index_freshness(
                    documents=[document],
                    store=Store(payloads=payloads, dimension=dimension),
                    collection_name="test",
                    expected_dimension=8,
                    )
                )

    with pytest.raises(RetrievalIndexStaleError, match="distance"):
        asyncio.run(
            validate_index_freshness(
                documents=[document],
                store=Store(payloads=fresh_payload, distance="Dot"),
                collection_name="test",
                expected_dimension=8,
            )
        )


def test_qdrant_adapter_requests_exact_search_and_explicit_filters() -> None:
    from types import SimpleNamespace

    from app.schemas.retrieval import RetrievalFilters
    from app.services.retrieval.vector_store import QdrantDenseVectorStore

    class Client:
        def __init__(self):
            self.kwargs = None

        async def query_points(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                points=[SimpleNamespace(payload={"entity_id": "cand_a"}, score=0.9)]
            )

    async def scenario() -> None:
        client = Client()
        store = QdrantDenseVectorStore(client=client)
        results = await store.search(
            collection_name="test",
            query_vector=[0.0, 1.0],
            limit=5,
            filters=RetrievalFilters(cities=["Shanghai"], seniorities=["mid"]),
        )

        assert results[0].entity_id == "cand_a"
        assert client.kwargs["search_params"].exact is True
        assert client.kwargs["with_vectors"] is False
        conditions = client.kwargs["query_filter"].must
        assert {condition.key for condition in conditions} == {"cities", "seniorities"}

    asyncio.run(scenario())


def test_qdrant_adapter_breaks_equal_score_hits_by_entity_id() -> None:
    from types import SimpleNamespace

    from app.services.retrieval.vector_store import QdrantDenseVectorStore

    class Client:
        async def query_points(self, **_kwargs):
            return SimpleNamespace(
                points=[
                    SimpleNamespace(payload={"entity_id": "cand_b"}, score=0.5),
                    SimpleNamespace(payload={"entity_id": "cand_a"}, score=0.5),
                ]
            )

    async def scenario() -> None:
        store = QdrantDenseVectorStore(client=Client())
        results = await store.search(
            collection_name="test",
            query_vector=[0.0, 1.0],
            limit=2,
            filters=None,
        )
        assert [item.entity_id for item in results] == ["cand_a", "cand_b"]
        assert [item.rank for item in results] == [1, 2]

    asyncio.run(scenario())
