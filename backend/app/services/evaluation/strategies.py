from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from app.schemas.cross_encoder import CrossEncoderRerankingRequest
from app.schemas.ranking import RankingRequest
from app.schemas.retrieval import RetrievalEntityType, RetrievalRequest, RetrievalStrategy
from app.services.cross_encoder.contract import MODEL_ID, MODEL_REVISION, TEXT_CONTRACT_FINGERPRINT
from app.services.evaluation.errors import EvaluationIntegrityError
from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION, MODEL_FEATURE_ORDER
from app.services.match_runs.contracts import CE_SNAPSHOT_FINGERPRINT, RANKER_MODEL_SHA256
from app.services.match_runs.contracts import RETRIEVAL_CONFIGURATION_FINGERPRINT, canonical_fingerprint
from app.services.ranking.contract import RANKER_VERSION
from app.services.retrieval.documents import RETRIEVAL_DOCUMENT_VERSION
from app.services.retrieval.embedding import EmbeddingProviderDescriptor
from app.services.retrieval.vector_store import point_id_for


R1_STRATEGY_ENUM = {
    "dense_v4": RetrievalStrategy.DENSE,
    "sparse_bm25_v4": RetrievalStrategy.SPARSE,
    "hybrid_rrf_v4": RetrievalStrategy.HYBRID,
}


@dataclass(frozen=True)
class StrategyOutput:
    strategy_id: str
    ordered_candidate_ids: tuple[str, ...]
    scores: dict[str, float]
    diagnostics: dict[str, Any]


class IndexedQueryEmbeddingProvider:
    """Read query vectors from a fingerprint-validated derived Job index."""

    def __init__(self, *, store: Any, collection_name: str, query_documents: dict[str, Any], model_name: str, dimension: int) -> None:
        self.store = store
        self.collection_name = collection_name
        self.query_documents_by_text = {document.text: document for document in query_documents.values()}
        self.descriptor = EmbeddingProviderDescriptor(
            name="frozen_qdrant_query_vector",
            model=model_name,
            dimension=dimension,
            provider_kind="derived_frozen_index",
        )

    async def embed_query(self, text: str) -> list[float]:
        document = self.query_documents_by_text.get(text)
        if document is None:
            raise EvaluationIntegrityError("query text is absent from the frozen Job index contract")
        payloads = await self.store.list_payloads(self.collection_name)
        payload = payloads.get(document.entity_id)
        if payload is None or payload.get("document_version") != RETRIEVAL_DOCUMENT_VERSION or payload.get("document_fingerprint") != document.document_fingerprint:
            raise EvaluationIntegrityError("frozen Job query-vector index fingerprint mismatch")
        records = await self.store.client.retrieve(
            collection_name=self.collection_name,
            ids=[point_id_for(RetrievalEntityType.JOB, document.entity_id)],
            with_payload=False,
            with_vectors=True,
        )
        if len(records) != 1 or not isinstance(records[0].vector, list):
            raise EvaluationIntegrityError("frozen Job query vector is unavailable")
        vector = [float(value) for value in records[0].vector]
        if len(vector) != self.descriptor.dimension or any(not math.isfinite(value) for value in vector):
            raise EvaluationIntegrityError("frozen Job query vector is invalid")
        return vector

    async def embed_documents(self, texts: Any) -> list[list[float]]:
        return [await self.embed_query(text) for text in texts]


async def qdrant_index_fingerprint(store: Any, collection_names: list[str]) -> str:
    collections: list[dict[str, Any]] = []
    for collection_name in collection_names:
        points: list[dict[str, Any]] = []
        offset = None
        while True:
            records, offset = await store.client.scroll(
                collection_name=collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            for record in records:
                if not isinstance(record.vector, list):
                    raise EvaluationIntegrityError("Qdrant index contains an unsupported vector")
                points.append({"point_id": str(record.id), "payload": dict(record.payload or {}), "vector": [float(value) for value in record.vector]})
            if offset is None:
                break
        collections.append({
            "collection": collection_name,
            "dimension": await store.collection_dimension(collection_name),
            "distance": await store.collection_distance(collection_name),
            "points": sorted(points, key=lambda item: item["point_id"]),
        })
    return canonical_fingerprint({"contract": "phase11_qdrant_index_state_v1", "collections": collections})


def validate_frozen_models(ltr_model: Any, ce_model: Any) -> None:
    ltr_expected = {
        "ranker_version": RANKER_VERSION,
        "model_sha256": RANKER_MODEL_SHA256,
    }
    if any(getattr(ltr_model, key, None) != value for key, value in ltr_expected.items()):
        raise EvaluationIntegrityError("LTR frozen model identity mismatch")
    metadata = getattr(ltr_model, "metadata", {})
    if (
        metadata.get("feature_version") != FEATURE_VERSION
        or metadata.get("feature_fingerprint") != FEATURE_FINGERPRINT
        or metadata.get("model_feature_order") != list(MODEL_FEATURE_ORDER)
    ):
        raise EvaluationIntegrityError("LTR feature contract mismatch")
    ce_expected = {
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "snapshot_fingerprint": CE_SNAPSHOT_FINGERPRINT,
    }
    if any(getattr(ce_model, key, None) != value for key, value in ce_expected.items()):
        raise EvaluationIntegrityError("CE frozen model identity mismatch")
    manifest = getattr(ce_model, "manifest", {})
    if manifest.get("text_contract_fingerprint") != TEXT_CONTRACT_FINGERPRINT:
        raise EvaluationIntegrityError("CE text contract fingerprint mismatch")


class FrozenStrategyAdapter:
    def __init__(self, *, retrieval_service: Any, ranking_service: Any, cross_encoder_service: Any, ltr_model: Any, ce_model: Any) -> None:
        validate_frozen_models(ltr_model, ce_model)
        self.retrieval_service = retrieval_service
        self.ranking_service = ranking_service
        self.cross_encoder_service = cross_encoder_service

    async def retrieve(self, job_id: str, strategy: str, top_k: int) -> StrategyOutput:
        if strategy not in R1_STRATEGY_ENUM:
            raise EvaluationIntegrityError(f"unknown frozen retrieval strategy: {strategy}")
        response = await self.retrieval_service.retrieve_candidates(
            job_id, RetrievalRequest(strategy=R1_STRATEGY_ENUM[strategy], top_k=top_k)
        )
        scores: dict[str, float] = {}
        for result in response.results:
            value = result.fusion_score if strategy == "hybrid_rrf_v4" else result.dense_score if strategy == "dense_v4" else result.sparse_score
            if value is None:
                raise EvaluationIntegrityError("frozen retrieval strategy returned a missing score")
            scores[result.entity_id] = float(value)
        return StrategyOutput(
            strategy, tuple(item.entity_id for item in response.results), scores,
            response.diagnostics.model_dump(mode="json"),
        )

    async def rank_ltr(self, job_id: str, pool_k: int, top_k: int) -> StrategyOutput:
        response = await self.ranking_service.rank_job_candidates(
            job_id, RankingRequest(candidate_pool_k=pool_k, top_k=top_k)
        )
        return StrategyOutput(
            "ltr_ranker_v1", tuple(item.entity_id for item in response.results),
            {item.entity_id: float(item.ltr_score_raw) for item in response.results},
            {
                "model_sha256": response.model_sha256,
                "feature_version": response.feature_version,
                "feature_fingerprint": response.feature_fingerprint,
                "candidate_pool_k": response.candidate_pool_k,
                "retrieval": response.retrieval_diagnostics.model_dump(mode="json"),
            },
        )

    async def rank_ce(self, job_id: str, retrieval_pool_k: int, ce_pool_k: int, top_k: int) -> StrategyOutput:
        response = await self.cross_encoder_service.rerank_job_candidates(
            job_id,
            CrossEncoderRerankingRequest(
                retrieval_pool_k=retrieval_pool_k,
                cross_encoder_pool_k=ce_pool_k,
                top_k=top_k,
            ),
        )
        return StrategyOutput(
            "cross_encoder_experiment", tuple(item.entity_id for item in response.results),
            {item.entity_id: float(item.cross_encoder_score_raw) for item in response.results},
            {
                "model_id": response.model_id,
                "model_revision": response.model_revision,
                "snapshot_fingerprint": response.snapshot_fingerprint,
                "text_contract_fingerprint": response.text_contract_fingerprint,
                "retrieval_pool_k": response.retrieval_pool_k,
                "cross_encoder_pool_k": response.cross_encoder_pool_k,
                "top_k": response.top_k,
                "experiment_role": "optional_explicit_experiment",
            },
        )
