from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence
from uuid import UUID, uuid5

from qdrant_client import AsyncQdrantClient, models

from app.exceptions import VectorStoreUnavailableError
from app.schemas.retrieval import (
    ChannelResult,
    RetrievalDocument,
    RetrievalEntityType,
    RetrievalFilters,
)


POINT_NAMESPACE = UUID("d92baa53-fbfc-54d2-9a07-610e57cb9ba7")


@dataclass(frozen=True)
class DenseIndexPoint:
    point_id: str
    vector: list[float]
    payload: dict[str, Any]


def point_id_for(entity_type: RetrievalEntityType, entity_id: str) -> str:
    return str(uuid5(POINT_NAMESPACE, f"{entity_type.value}:{entity_id}"))


def payload_for(document: RetrievalDocument) -> dict[str, Any]:
    return {
        "entity_id": document.entity_id,
        "document_version": document.document_version,
        "document_fingerprint": document.document_fingerprint,
        "cities": list(document.cities),
        "seniorities": [value.value for value in document.seniorities],
    }


class DenseVectorStore(Protocol):
    async def collection_exists(self, collection_name: str) -> bool: ...

    async def collection_dimension(self, collection_name: str) -> int: ...

    async def collection_distance(self, collection_name: str) -> str: ...

    async def rebuild(
        self,
        collection_name: str,
        dimension: int,
        points: Sequence[DenseIndexPoint],
    ) -> None: ...

    async def list_payloads(self, collection_name: str) -> dict[str, dict[str, Any]]: ...

    async def search(
        self,
        *,
        collection_name: str,
        query_vector: Sequence[float],
        limit: int,
        filters: Optional[RetrievalFilters],
    ) -> list[ChannelResult]: ...


class QdrantDenseVectorStore:
    def __init__(
        self,
        *,
        client: Optional[AsyncQdrantClient] = None,
        url: Optional[str] = None,
    ) -> None:
        if client is None and not url:
            raise VectorStoreUnavailableError("Qdrant URL is not configured")
        self.client = client or AsyncQdrantClient(url=url, check_compatibility=False)

    async def collection_exists(self, collection_name: str) -> bool:
        try:
            return await self.client.collection_exists(collection_name)
        except Exception as exc:
            raise VectorStoreUnavailableError("Vector store is unavailable") from exc

    async def collection_dimension(self, collection_name: str) -> int:
        vectors = await self._collection_vector_params(collection_name)
        return vectors.size

    async def collection_distance(self, collection_name: str) -> str:
        vectors = await self._collection_vector_params(collection_name)
        return vectors.distance.value

    async def _collection_vector_params(self, collection_name: str) -> models.VectorParams:
        try:
            info = await self.client.get_collection(collection_name)
        except Exception as exc:
            raise VectorStoreUnavailableError("Vector store is unavailable") from exc
        vectors = info.config.params.vectors
        if not isinstance(vectors, models.VectorParams):
            raise VectorStoreUnavailableError("Vector collection configuration is unsupported")
        return vectors

    async def delete_collection(self, collection_name: str) -> None:
        try:
            await self.client.delete_collection(collection_name)
        except Exception as exc:
            raise VectorStoreUnavailableError("Vector store is unavailable") from exc

    async def rebuild(
        self,
        collection_name: str,
        dimension: int,
        points: Sequence[DenseIndexPoint],
    ) -> None:
        try:
            if await self.client.collection_exists(collection_name):
                await self.client.delete_collection(collection_name)
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                ),
            )
            if points:
                await self.client.upsert(
                    collection_name=collection_name,
                    wait=True,
                    points=[
                        models.PointStruct(
                            id=point.point_id,
                            vector=point.vector,
                            payload=point.payload,
                        )
                        for point in points
                    ],
                )
        except Exception as exc:
            raise VectorStoreUnavailableError("Vector index rebuild failed") from exc

    async def list_payloads(self, collection_name: str) -> dict[str, dict[str, Any]]:
        payloads: dict[str, dict[str, Any]] = {}
        offset = None
        try:
            while True:
                records, offset = await self.client.scroll(
                    collection_name=collection_name,
                    limit=256,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                for record in records:
                    payload = dict(record.payload or {})
                    entity_id = payload.get("entity_id")
                    if isinstance(entity_id, str):
                        payloads[entity_id] = payload
                if offset is None:
                    break
        except Exception as exc:
            raise VectorStoreUnavailableError("Vector store is unavailable") from exc
        return payloads

    @staticmethod
    def _qdrant_filter(filters: Optional[RetrievalFilters]):
        if filters is None:
            return None
        conditions = []
        if filters.cities:
            conditions.append(
                models.FieldCondition(
                    key="cities", match=models.MatchAny(any=filters.cities)
                )
            )
        if filters.seniorities:
            conditions.append(
                models.FieldCondition(
                    key="seniorities",
                    match=models.MatchAny(
                        any=[value.value for value in filters.seniorities]
                    ),
                )
            )
        return models.Filter(must=conditions) if conditions else None

    async def search(
        self,
        *,
        collection_name: str,
        query_vector: Sequence[float],
        limit: int,
        filters: Optional[RetrievalFilters],
    ) -> list[ChannelResult]:
        try:
            response = await self.client.query_points(
                collection_name=collection_name,
                query=list(query_vector),
                query_filter=self._qdrant_filter(filters),
                search_params=models.SearchParams(exact=True),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise VectorStoreUnavailableError("Vector search failed") from exc
        ranked = sorted(
            (
                (point.payload.get("entity_id"), float(point.score))
                for point in response.points
                if point.payload and isinstance(point.payload.get("entity_id"), str)
            ),
            key=lambda item: (-item[1], item[0]),
        )
        return [
            ChannelResult(entity_id=entity_id, rank=rank, score=score)
            for rank, (entity_id, score) in enumerate(ranked, start=1)
        ]
