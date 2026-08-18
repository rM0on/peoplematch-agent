from __future__ import annotations

import math

from app.exceptions import CrossEncoderContractMismatchError, ProfileNotFoundError
from app.schemas.cross_encoder import (
    CrossEncoderRerankingRequest,
    CrossEncoderRerankingResponseData,
    CrossEncoderRerankingResult,
)
from app.schemas.ranking import RankingRequest
from app.services.cross_encoder.contract import (
    DEFAULT_BATCH_SIZE,
    PAIR_ORDER,
    RERANKER_VERSION,
    TEXT_CONTRACT_FINGERPRINT,
    TEXT_SCHEMA_VERSION,
)
from app.services.cross_encoder.text import build_pair_text


class CrossEncoderRerankingService:
    def __init__(
        self,
        *,
        ranking_service,
        cross_encoder_model,
        job_repository,
        candidate_repository,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.ranking_service = ranking_service
        self.cross_encoder_model = cross_encoder_model
        self.job_repository = job_repository
        self.candidate_repository = candidate_repository
        self.batch_size = batch_size

    async def rerank_job_candidates(
        self, job_id: str, request: CrossEncoderRerankingRequest
    ) -> CrossEncoderRerankingResponseData:
        ltr_response = await self.ranking_service.rank_job_candidates(
            job_id,
            RankingRequest(
                candidate_pool_k=request.retrieval_pool_k,
                top_k=request.cross_encoder_pool_k,
                filters=request.filters,
            ),
        )
        job = await self.job_repository.get_record_by_id(job_id)
        if job is None:
            raise ProfileNotFoundError(f"Job {job_id} was not found")
        pairs = []
        selected = []
        for result in ltr_response.results:
            candidate = await self.candidate_repository.get_record_by_id(
                result.entity_id
            )
            if candidate is None:
                raise CrossEncoderContractMismatchError(
                    "LTR shortlist candidate is absent from canonical profiles"
                )
            pair = build_pair_text(job, candidate)
            pairs.append((pair.text_a, pair.text_b))
            selected.append((result, pair))

        scores = self.cross_encoder_model.predict_pairs(
            pairs,
            batch_size=self.batch_size,
        )
        if len(scores) != len(selected):
            raise CrossEncoderContractMismatchError(
                "Cross-Encoder score count does not match the LTR shortlist"
            )
        scored = []
        for result, score in zip((item[0] for item in selected), scores):
            value = float(score)
            if not math.isfinite(value):
                raise CrossEncoderContractMismatchError(
                    "Cross-Encoder returned a non-finite raw logit"
                )
            scored.append(
                {
                    "result": result,
                    "score": value,
                }
            )
        ordered = sorted(
            scored,
            key=lambda item: (
                -item["score"],
                int(item["result"].ltr_rank),
                int(item["result"].retrieval.rank),
                str(item["result"].entity_id),
            ),
        )
        results = [
            CrossEncoderRerankingResult(
                entity_id=item["result"].entity_id,
                retrieval_rank=item["result"].retrieval.rank,
                ltr_rank=item["result"].ltr_rank,
                ltr_score_raw=item["result"].ltr_score_raw,
                cross_encoder_rank=rank,
                cross_encoder_score_raw=item["score"],
                ranker_version=ltr_response.ranker_version,
                model_sha256=ltr_response.model_sha256,
                feature_version=ltr_response.feature_version,
                feature_fingerprint=ltr_response.feature_fingerprint,
            )
            for rank, item in enumerate(ordered[: request.top_k], start=1)
        ]
        return CrossEncoderRerankingResponseData(
            reranker_version=RERANKER_VERSION,
            model_id=self.cross_encoder_model.model_id,
            model_revision=self.cross_encoder_model.revision,
            snapshot_fingerprint=self.cross_encoder_model.snapshot_fingerprint,
            text_schema_version=TEXT_SCHEMA_VERSION,
            text_contract_fingerprint=TEXT_CONTRACT_FINGERPRINT,
            pair_order=PAIR_ORDER,
            retrieval_pool_k=request.retrieval_pool_k,
            cross_encoder_pool_k=request.cross_encoder_pool_k,
            top_k=request.top_k,
            results=results,
        )
