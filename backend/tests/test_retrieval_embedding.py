from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import sys
import time
from types import SimpleNamespace

import pytest


def test_deterministic_test_embedding_is_repeatable_dimensioned_and_ordered() -> None:
    from app.services.retrieval.embedding import DeterministicTestEmbeddingProvider

    async def scenario() -> None:
        provider = DeterministicTestEmbeddingProvider(dimension=8)
        batch = await provider.embed_documents(["alpha", "beta", "alpha"])
        query = await provider.embed_query("alpha")

        assert provider.descriptor.provider_kind == "test"
        assert provider.descriptor.dimension == 8
        assert len(batch) == 3
        assert all(len(vector) == 8 for vector in batch)
        assert batch[0] == batch[2] == query
        assert batch[0] != batch[1]

    asyncio.run(scenario())


def test_embedding_output_dimension_mismatch_fails_clearly() -> None:
    from app.exceptions import EmbeddingDimensionMismatchError
    from app.services.retrieval.embedding import (
        EmbeddingProviderDescriptor,
        validate_embeddings,
    )

    descriptor = EmbeddingProviderDescriptor(
        name="broken",
        model="broken-model",
        dimension=3,
        provider_kind="test",
    )
    with pytest.raises(EmbeddingDimensionMismatchError, match="expected 3"):
        validate_embeddings([[0.0, 1.0]], descriptor, expected_count=1)

    with pytest.raises(EmbeddingDimensionMismatchError, match="expected 2 vectors"):
        validate_embeddings([[0.0, 1.0, 2.0]], descriptor, expected_count=2)


def test_sentence_transformer_provider_is_lazy_and_has_reviewed_descriptor() -> None:
    from app.services.retrieval.embedding import SentenceTransformerEmbeddingProvider

    provider = SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
    )

    assert provider.descriptor.name == "sentence_transformers"
    assert provider.descriptor.model == "sentence-transformers/all-MiniLM-L6-v2"
    assert provider.descriptor.dimension == 384
    assert provider.descriptor.provider_kind == "local_pretrained"
    assert provider.is_loaded is False


def test_sentence_transformer_provider_loads_model_once_under_concurrency(monkeypatch) -> None:
    from app.services.retrieval.embedding import SentenceTransformerEmbeddingProvider

    calls = 0
    model = SimpleNamespace(get_sentence_embedding_dimension=lambda: 384)

    def constructor(_model_name):
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return model

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=constructor),
    )
    provider = SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2", dimension=384
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        loaded = list(executor.map(lambda _value: provider._load_model(), range(2)))

    assert loaded == [model, model]
    assert calls == 1


def test_retrieval_settings_lock_server_owned_baseline_configuration() -> None:
    from app.core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.retrieval_embedding_provider == "sentence_transformers"
    assert settings.retrieval_embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.retrieval_embedding_dimension == 384
    assert settings.retrieval_candidate_collection == "peoplematch_candidates_retrieval_v1"
    assert settings.retrieval_job_collection == "peoplematch_jobs_retrieval_v1"
    assert settings.retrieval_rrf_k == 60
    assert settings.retrieval_bm25_k1 == 1.5
    assert settings.retrieval_bm25_b == 0.75
    assert settings.retrieval_pool_minimum == 20
    assert settings.retrieval_pool_multiplier == 3


def test_runtime_retrieval_dependencies_are_lazy_singletons(monkeypatch) -> None:
    from app.api import dependencies
    from app.core.config import Settings
    from app.api.dependencies import (
        get_runtime_embedding_provider,
        get_runtime_vector_store,
    )

    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: Settings(qdrant_url="http://localhost:6333", _env_file=None),
    )
    get_runtime_embedding_provider.cache_clear()
    get_runtime_vector_store.cache_clear()
    first_provider = get_runtime_embedding_provider()
    first_cache_info = get_runtime_embedding_provider.cache_info()
    second_provider = get_runtime_embedding_provider()
    second_cache_info = get_runtime_embedding_provider.cache_info()
    first_store = get_runtime_vector_store()
    second_store = get_runtime_vector_store()

    assert first_provider is second_provider, (first_cache_info, second_cache_info)
    assert first_provider.is_loaded is False
    assert first_store is second_store
    get_runtime_embedding_provider.cache_clear()
    get_runtime_vector_store.cache_clear()
