from __future__ import annotations

import asyncio

from test_feature_service import _feature_service


class FakeModel:
    ranker_version = "ltr_ranker_v1"
    model_sha256 = "a" * 64

    def __init__(self) -> None:
        self.calls = 0
        self.vector_sizes: list[int] = []

    def predict(self, vectors):
        self.calls += 1
        self.vector_sizes.append(len(vectors))
        return __import__("numpy").array(
            [2.0] + [1.0] * (len(vectors) - 1), dtype=float
        )


def test_ranking_service_reuses_hybrid_feature_path_and_reranks_only_pool() -> None:
    from app.schemas.ranking import RankingRequest
    from app.services.ranking.service import RankingService

    feature_service, _, _, jobs = _feature_service()
    model = FakeModel()
    service = RankingService(feature_service=feature_service, ranking_model=model)

    response = asyncio.run(
        service.rank_job_candidates(
            jobs[0].job_id,
            RankingRequest(candidate_pool_k=4, top_k=3),
        )
    )

    assert model.calls == 1
    assert model.vector_sizes == [4]
    assert len(response.results) == 3
    assert response.results[0].ltr_rank == 1
    assert response.results[0].ltr_score_raw == 2.0
    assert response.results[0].retrieval.rank == 1
    assert response.feature_version == "feature_schema_v1"
    assert response.feature_fingerprint == (
        "dc85c7237c6c67785199d221c919ae48c31c9a6323857070e6399d3eae365e42"
    )
    assert response.candidate_pool_k == 4


def test_ranking_service_exposes_only_job_to_candidates_direction() -> None:
    from app.services.ranking.service import RankingService

    assert hasattr(RankingService, "rank_job_candidates")
    assert not hasattr(RankingService, "rank_candidate_jobs")
