from __future__ import annotations

import asyncio

import pytest


class FakeAdapter:
    def __init__(self, *, incomplete_ltr: bool = False) -> None:
        self.incomplete_ltr = incomplete_ltr

    async def retrieve(self, job_id: str, strategy: str, top_k: int):
        from app.services.evaluation.strategies import StrategyOutput
        orders = {"dense_v4": ["a", "x", "b"], "sparse_bm25_v4": ["b", "a"], "hybrid_rrf_v4": ["a", "b", "x"]}
        order = orders[strategy][:top_k]
        return StrategyOutput(strategy, tuple(order), {item: float(len(order) - index) for index, item in enumerate(order)}, {"returned_count": len(order)})

    async def rank_ltr(self, job_id: str, pool_k: int, top_k: int):
        from app.services.evaluation.strategies import StrategyOutput
        order = ["b", "a"] if self.incomplete_ltr else ["b", "a", "x"]
        order = order[:top_k]
        return StrategyOutput("ltr_ranker_v1", tuple(order), {item: float(len(order) - index) for index, item in enumerate(order)}, {"retrieval": {"total_ms": 1.0, "index_freshness": "fresh"}})

    async def rank_ce(self, job_id: str, retrieval_pool_k: int, ce_pool_k: int, top_k: int):
        from app.services.evaluation.strategies import StrategyOutput
        order = ["a", "x", "b"][:top_k]
        return StrategyOutput("cross_encoder_experiment", tuple(order), {item: float(len(order) - index) for index, item in enumerate(order)}, {})


def test_runner_computes_r1_r2_and_predeclared_leaders() -> None:
    from app.services.evaluation.runner import evaluate_queries

    result = asyncio.run(evaluate_queries(
        adapter=FakeAdapter(), query_ids=["job_fixture"], candidate_ids=["a", "b", "x"],
        grades_by_job={"job_fixture": {"a": 3, "b": 2}},
        pairs_by_job={"job_fixture": (("a", "b"),)}, include_r3=False,
    ))
    assert result["r1"]["leader"]["rule"] == "recall@10>recall@20>recall@5>co-leader"
    assert result["r2"]["leader"]["rule"] == "ndcg@5>ndcg@10>pairwise_accuracy>co-leader"
    assert result["r2"]["strategies"]["ltr_ranker_v1"]["judged_condensed_ndcg_at_5"]["mean"] < 1.0


def test_r3_quality_provenance_excludes_nondeterministic_timings() -> None:
    from app.services.evaluation.runner import evaluate_queries

    result = asyncio.run(evaluate_queries(
        adapter=FakeAdapter(), query_ids=["job_fixture"], candidate_ids=["a", "b", "x"],
        grades_by_job={"job_fixture": {"a": 3, "b": 2}},
        pairs_by_job={"job_fixture": (("a", "b"),)}, include_r3=True,
    ))
    provenance = result["r3"]["per_query"]["job_fixture"]["hybrid20_ltr10"]["provenance"]
    assert provenance == {"retrieval": {"index_freshness": "fresh"}}


def test_runner_invalidates_incomplete_full_pool() -> None:
    from app.services.evaluation.errors import EvaluationIntegrityError
    from app.services.evaluation.runner import evaluate_queries

    with pytest.raises(EvaluationIntegrityError, match="missing"):
        asyncio.run(evaluate_queries(
            adapter=FakeAdapter(incomplete_ltr=True), query_ids=["job_fixture"], candidate_ids=["a", "b", "x"],
            grades_by_job={"job_fixture": {"a": 3, "b": 2}},
            pairs_by_job={"job_fixture": (("a", "b"),)}, include_r3=False,
        ))


def test_frozen_strategy_contract_rejects_model_and_ce_mismatches() -> None:
    from types import SimpleNamespace
    from app.services.evaluation.strategies import validate_frozen_models

    ltr = SimpleNamespace(ranker_version="wrong", model_sha256="x", metadata={})
    ce = SimpleNamespace(model_id="wrong", revision="wrong", snapshot_fingerprint="wrong")
    with pytest.raises(ValueError, match="LTR"):
        validate_frozen_models(ltr, ce)

    from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION, MODEL_FEATURE_ORDER
    from app.services.match_runs.contracts import RANKER_MODEL_SHA256
    from app.services.ranking.contract import RANKER_VERSION
    valid_ltr = SimpleNamespace(
        ranker_version=RANKER_VERSION,
        model_sha256=RANKER_MODEL_SHA256,
        metadata={
            "feature_version": FEATURE_VERSION,
            "feature_fingerprint": FEATURE_FINGERPRINT,
            "model_feature_order": list(MODEL_FEATURE_ORDER),
        },
    )
    with pytest.raises(ValueError, match="CE"):
        validate_frozen_models(valid_ltr, ce)
