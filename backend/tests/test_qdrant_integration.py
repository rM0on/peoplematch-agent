from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest


QDRANT_TEST_URL = os.getenv("QDRANT_TEST_URL")
pytestmark = pytest.mark.skipif(
    not QDRANT_TEST_URL,
    reason="QDRANT_TEST_URL is required for Qdrant integration tests",
)


def test_qdrant_collection_upsert_exact_search_filter_freshness_and_cleanup() -> None:
    from qdrant_client import AsyncQdrantClient

    from app.exceptions import RetrievalIndexMissingError, RetrievalIndexStaleError
    from app.schemas.retrieval import CandidateRetrievalDocument, RetrievalFilters
    from app.schemas.shared import Seniority
    from app.services.retrieval.embedding import DeterministicTestEmbeddingProvider
    from app.services.retrieval.indexing import build_dense_index, validate_index_freshness
    from app.services.retrieval.vector_store import QdrantDenseVectorStore

    collection = f"peoplematch_test_{uuid4().hex}"
    documents = [
        CandidateRetrievalDocument(
            entity_id="cand_a",
            document_version="retrieval_doc_v2",
            document_fingerprint="a" * 64,
            text="candidate retrieval ranking",
            cities=["Shanghai"],
            seniorities=[Seniority.MID],
        ),
        CandidateRetrievalDocument(
            entity_id="cand_b",
            document_version="retrieval_doc_v2",
            document_fingerprint="b" * 64,
            text="frontend product interaction",
            cities=["Beijing"],
            seniorities=[Seniority.SENIOR],
        ),
    ]

    async def scenario() -> None:
        client = AsyncQdrantClient(url=QDRANT_TEST_URL)
        store = QdrantDenseVectorStore(client=client)
        provider = DeterministicTestEmbeddingProvider(dimension=8)
        try:
            assert not await store.collection_exists(collection)
            with pytest.raises(RetrievalIndexMissingError):
                await validate_index_freshness(
                    documents=documents,
                    store=store,
                    collection_name=collection,
                    expected_dimension=8,
                )

            report = await build_dense_index(
                documents=documents,
                provider=provider,
                store=store,
                collection_name=collection,
            )
            assert report.entity_count == 2
            assert report.dimension == 8
            assert await store.collection_dimension(collection) == 8
            payloads = await store.list_payloads(collection)
            assert set(payloads) == {"cand_a", "cand_b"}
            assert payloads["cand_a"] == {
                "entity_id": "cand_a",
                "document_version": "retrieval_doc_v2",
                "document_fingerprint": "a" * 64,
                "cities": ["Shanghai"],
                "seniorities": ["mid"],
            }
            await validate_index_freshness(
                documents=documents,
                store=store,
                collection_name=collection,
                expected_dimension=8,
            )

            query = await provider.embed_query(documents[0].text)
            unfiltered = await store.search(
                collection_name=collection,
                query_vector=query,
                limit=2,
                filters=None,
            )
            assert unfiltered[0].entity_id == "cand_a"
            filtered = await store.search(
                collection_name=collection,
                query_vector=query,
                limit=2,
                filters=RetrievalFilters(cities=["Beijing"]),
            )
            assert [item.entity_id for item in filtered] == ["cand_b"]

            changed = documents[0].model_copy(
                update={"document_fingerprint": "c" * 64}
            )
            with pytest.raises(RetrievalIndexStaleError):
                await validate_index_freshness(
                    documents=[changed, documents[1]],
                    store=store,
                    collection_name=collection,
                    expected_dimension=8,
                )
        finally:
            if await store.collection_exists(collection):
                await store.delete_collection(collection)
            await client.close()

    asyncio.run(scenario())
