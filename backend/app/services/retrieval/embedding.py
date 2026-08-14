from __future__ import annotations

import asyncio
import hashlib
import math
import threading
from dataclasses import dataclass
from typing import Protocol, Sequence

from app.exceptions import (
    EmbeddingDimensionMismatchError,
    EmbeddingProviderUnavailableError,
)


@dataclass(frozen=True)
class EmbeddingProviderDescriptor:
    name: str
    model: str
    dimension: int
    provider_kind: str


class EmbeddingProvider(Protocol):
    descriptor: EmbeddingProviderDescriptor

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed corpus documents in input order."""

    async def embed_query(self, text: str) -> list[float]:
        """Embed one retrieval query."""


def validate_embeddings(
    vectors: Sequence[Sequence[float]],
    descriptor: EmbeddingProviderDescriptor,
    *,
    expected_count: int,
) -> list[list[float]]:
    if len(vectors) != expected_count:
        raise EmbeddingDimensionMismatchError(
            f"Embedding provider returned {len(vectors)} vectors; expected {expected_count} vectors"
        )
    validated: list[list[float]] = []
    for vector in vectors:
        if len(vector) != descriptor.dimension:
            raise EmbeddingDimensionMismatchError(
                f"Embedding dimension {len(vector)} does not match expected {descriptor.dimension}"
            )
        validated.append([float(value) for value in vector])
    return validated


class DeterministicTestEmbeddingProvider:
    """Deterministic hash projection for tests only; not a semantic baseline."""

    def __init__(self, *, dimension: int = 8) -> None:
        self.descriptor = EmbeddingProviderDescriptor(
            name="deterministic_test",
            model="sha256_projection_test_only",
            dimension=dimension,
            provider_kind="test",
        )

    def _embed(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.descriptor.dimension:
            digest = hashlib.sha256(f"{counter}\0{text}".encode("utf-8")).digest()
            for byte in digest:
                values.append(byte / 127.5 - 1.0)
                if len(values) == self.descriptor.dimension:
                    break
            counter += 1
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = [self._embed(text) for text in texts]
        return validate_embeddings(
            vectors, self.descriptor, expected_count=len(texts)
        )

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]


class SentenceTransformerEmbeddingProvider:
    def __init__(self, *, model_name: str, dimension: int) -> None:
        self.descriptor = EmbeddingProviderDescriptor(
            name="sentence_transformers",
            model=model_name,
            dimension=dimension,
            provider_kind="local_pretrained",
        )
        self._model = None
        self._load_lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load_model(self):
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer

                model = SentenceTransformer(self.descriptor.model)
            except Exception as exc:
                raise EmbeddingProviderUnavailableError(
                    "Local embedding provider could not be loaded"
                ) from exc
            actual_dimension = model.get_sentence_embedding_dimension()
            if actual_dimension != self.descriptor.dimension:
                raise EmbeddingDimensionMismatchError(
                    f"Embedding model dimension {actual_dimension} does not match expected "
                    f"{self.descriptor.dimension}"
                )
            self._model = model
            return model

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load_model()
        try:
            encoded = model.encode(
                list(texts),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingProviderUnavailableError(
                "Local embedding provider failed to encode retrieval text"
            ) from exc
        vectors = encoded.tolist()
        return validate_embeddings(
            vectors, self.descriptor, expected_count=len(texts)
        )

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._encode, texts)

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]
