from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.exceptions import RetrievalIndexMissingError, RetrievalIndexStaleError
from app.schemas.retrieval import RetrievalDocument
from app.services.retrieval.documents import RETRIEVAL_DOCUMENT_VERSION
from app.services.retrieval.embedding import EmbeddingProvider, validate_embeddings
from app.services.retrieval.vector_store import (
    DenseIndexPoint,
    DenseVectorStore,
    payload_for,
    point_id_for,
)


@dataclass(frozen=True)
class IndexBuildReport:
    collection_name: str
    entity_count: int
    dimension: int
    document_version: str


async def build_dense_index(
    *,
    documents: Sequence[RetrievalDocument],
    provider: EmbeddingProvider,
    store: DenseVectorStore,
    collection_name: str,
) -> IndexBuildReport:
    ordered = sorted(documents, key=lambda item: item.entity_id)
    vectors = await provider.embed_documents([document.text for document in ordered])
    vectors = validate_embeddings(
        vectors, provider.descriptor, expected_count=len(ordered)
    )
    points = [
        DenseIndexPoint(
            point_id=point_id_for(document.entity_type, document.entity_id),
            vector=vector,
            payload=payload_for(document),
        )
        for document, vector in zip(ordered, vectors)
    ]
    await store.rebuild(collection_name, provider.descriptor.dimension, points)
    version = ordered[0].document_version if ordered else RETRIEVAL_DOCUMENT_VERSION
    return IndexBuildReport(
        collection_name=collection_name,
        entity_count=len(points),
        dimension=provider.descriptor.dimension,
        document_version=version,
    )


async def validate_index_freshness(
    *,
    documents: Sequence[RetrievalDocument],
    store: DenseVectorStore,
    collection_name: str,
    expected_dimension: int,
) -> None:
    if not await store.collection_exists(collection_name):
        raise RetrievalIndexMissingError(
            f"Retrieval index '{collection_name}' is missing; rebuild it explicitly"
        )
    dimension = await store.collection_dimension(collection_name)
    if dimension != expected_dimension:
        raise RetrievalIndexStaleError(
            f"Retrieval index '{collection_name}' dimension is stale"
        )
    if await store.collection_distance(collection_name) != "Cosine":
        raise RetrievalIndexStaleError(
            f"Retrieval index '{collection_name}' distance is stale"
        )
    actual = await store.list_payloads(collection_name)
    expected = {document.entity_id: payload_for(document) for document in documents}
    if set(actual) != set(expected):
        raise RetrievalIndexStaleError(
            f"Retrieval index '{collection_name}' entity set is stale"
        )
    for entity_id, expected_payload in expected.items():
        actual_payload = actual[entity_id]
        if actual_payload != expected_payload:
            raise RetrievalIndexStaleError(
                f"Retrieval index '{collection_name}' document metadata is stale"
            )
