from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.exceptions import RankingContractMismatchError
from app.schemas.ranking import RankingRequest, RankingResponseData, RankingResult
from app.schemas.retrieval import RetrievalRequest, RetrievalStrategy
from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION
from app.services.ranking.metrics import deterministic_rank_order


class RankingService:
    def __init__(self, *, feature_service, ranking_model) -> None:
        self.feature_service = feature_service
        self.ranking_model = ranking_model

    async def rank_job_candidates(
        self, job_id: str, request: RankingRequest
    ) -> RankingResponseData:
        feature_response = await self.feature_service.features_for_job_candidates(
            job_id,
            RetrievalRequest(
                strategy=RetrievalStrategy.HYBRID,
                top_k=request.candidate_pool_k,
                filters=request.filters,
            ),
        )
        if feature_response.feature_version != FEATURE_VERSION:
            raise RankingContractMismatchError("Feature version mismatch at ranking")
        if feature_response.feature_fingerprint != FEATURE_FINGERPRINT:
            raise RankingContractMismatchError("Feature fingerprint mismatch at ranking")
        feature_results = feature_response.results
        vectors = [item.feature_vector for item in feature_results]
        scores = np.asarray(self.ranking_model.predict(vectors), dtype=float)
        if scores.shape != (len(feature_results),) or not np.isfinite(scores).all():
            raise RankingContractMismatchError("Ranking model returned invalid scores")
        sortable = [
            {
                "entity_id": item.entity_id,
                "retrieval_rank": item.retrieval.rank,
                "score": float(score),
                "item": item,
            }
            for item, score in zip(feature_results, scores)
        ]
        ordered = deterministic_rank_order(sortable)
        results = [
            RankingResult(
                entity_id=row["entity_id"],
                ltr_rank=rank,
                ltr_score_raw=row["score"],
                retrieval=row["item"].retrieval,
                feature_vector=row["item"].feature_vector,
                feature_diagnostics=row["item"].feature_diagnostics,
            )
            for rank, row in enumerate(ordered[: request.top_k], start=1)
        ]
        return RankingResponseData(
            ranker_version=self.ranking_model.ranker_version,
            model_sha256=self.ranking_model.model_sha256,
            feature_version=FEATURE_VERSION,
            feature_fingerprint=FEATURE_FINGERPRINT,
            candidate_pool_k=request.candidate_pool_k,
            results=results,
            retrieval_diagnostics=feature_response.retrieval_diagnostics,
        )
