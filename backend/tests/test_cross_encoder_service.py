from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np


ROOT = Path(__file__).resolve().parents[2]


def _record(path: str, index: int = 0) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8").splitlines()[index])


class _FakeRankingService:
    def __init__(self, response):
        self.response = response
        self.requests = []

    async def rank_job_candidates(self, job_id, request):
        self.requests.append((job_id, request))
        return self.response


class _FakeRepository:
    def __init__(self, records):
        self.records = records

    async def get_record_by_id(self, identifier):
        return next((record for record in self.records if record.model_dump().get("job_id", record.model_dump().get("candidate_id")) == identifier), None)

    async def list_all_records(self):
        return self.records


class _FakeCrossEncoder:
    model_id = "cross-encoder/ms-marco-MiniLM-L6-v2"
    revision = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
    snapshot_fingerprint = "a" * 64

    def __init__(self, scores):
        self.scores = np.asarray(scores, dtype=float)
        self.calls = []

    def predict_pairs(self, pairs, *, batch_size):
        self.calls.append((pairs, batch_size))
        return self.scores


def test_service_reuses_ltr_shortlist_and_reranks_without_score_blending() -> None:
    from app.schemas.persistence import CandidateRecord, JobRecord
    from app.schemas.retrieval import RetrievalResult
    from app.services.cross_encoder.service import CrossEncoderRerankingService

    job = JobRecord.model_validate(_record("data/samples/jobs.jsonl", 0))
    candidate_a = CandidateRecord.model_validate(_record("data/samples/candidates.jsonl", 0))
    candidate_b = CandidateRecord.model_validate(_record("data/samples/candidates.jsonl", 1))
    ltr_response = SimpleNamespace(
        ranker_version="ltr_ranker_v1",
        model_sha256="b" * 64,
        feature_version="feature_schema_v1",
        feature_fingerprint="c" * 64,
        results=[
            SimpleNamespace(
                entity_id=candidate_a.candidate_id,
                ltr_rank=1,
                ltr_score_raw=10.0,
                retrieval=RetrievalResult(entity_id=candidate_a.candidate_id, rank=2, matched_channels=[]),
            ),
            SimpleNamespace(
                entity_id=candidate_b.candidate_id,
                ltr_rank=2,
                ltr_score_raw=1.0,
                retrieval=RetrievalResult(entity_id=candidate_b.candidate_id, rank=1, matched_channels=[]),
            ),
        ],
    )
    ranking = _FakeRankingService(ltr_response)
    ce = _FakeCrossEncoder([0.5, 0.5])
    service = CrossEncoderRerankingService(
        ranking_service=ranking,
        cross_encoder_model=ce,
        job_repository=_FakeRepository([job]),
        candidate_repository=_FakeRepository([candidate_a, candidate_b]),
        batch_size=10,
    )

    from app.schemas.cross_encoder import CrossEncoderRerankingRequest

    response = asyncio.run(
        service.rerank_job_candidates(
            job.job_id,
            CrossEncoderRerankingRequest(),
        )
    )
    assert ranking.requests[0][1].candidate_pool_k == 20
    assert ranking.requests[0][1].top_k == 10
    assert len(ce.calls) == 1
    assert ce.calls[0][1] == 10
    assert [item.entity_id for item in response.results] == [candidate_a.candidate_id, candidate_b.candidate_id]
    assert response.results[0].cross_encoder_score_raw == 0.5
    assert response.results[0].cross_encoder_rank == 1
    assert response.results[0].ranker_version == "ltr_ranker_v1"


def test_request_rejects_invalid_cascade_pool_order() -> None:
    import pytest

    from app.schemas.cross_encoder import CrossEncoderRerankingRequest

    with pytest.raises(ValueError):
        CrossEncoderRerankingRequest(retrieval_pool_k=10, cross_encoder_pool_k=20, top_k=5)
