from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Sequence

from app.services.evaluation.metrics import (
    explicit_pairwise_accuracy,
    judged_condensed_mrr_at_k,
    judged_condensed_ndcg_at_k,
    macro_average,
    retrieval_recall_at_k,
)
from app.services.evaluation.errors import EvaluationIntegrityError
from app.services.evaluation.provenance import (
    assert_comparable_orders,
    build_pool_provenance,
    condense_to_judged,
)
from app.services.features.contract import FEATURE_FINGERPRINT
from app.services.match_runs.contracts import (
    CE_SNAPSHOT_FINGERPRINT,
    RANKER_MODEL_SHA256,
    RETRIEVAL_CONFIGURATION_FINGERPRINT,
    canonical_fingerprint,
)


R1_STRATEGIES = ("dense_v4", "sparse_bm25_v4", "hybrid_rrf_v4")
R2_STRATEGIES = ("hybrid_rrf_v4", "ltr_ranker_v1", "cross_encoder_experiment")


def _metric_payload(per_query: dict[str, Any]) -> dict[str, Any]:
    aggregate = macro_average(per_query)
    return {
        **asdict(aggregate),
        "per_query": {
            query_id: {"value": value.value, "exclusion_reason": value.exclusion_reason}
            for query_id, value in sorted(per_query.items())
        },
    }


def _without_timing(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_timing(item)
            for key, item in value.items()
            if "latency" not in key.casefold() and not key.casefold().endswith("_ms")
        }
    if isinstance(value, list):
        return [_without_timing(item) for item in value]
    return value


def _leader(strategies: Mapping[str, dict[str, Any]], metric_names: Sequence[str], rule: str) -> dict[str, Any]:
    def vector(strategy_id: str) -> tuple[float, ...]:
        return tuple(float(strategies[strategy_id][metric]["mean"]) for metric in metric_names)

    best = max(vector(strategy_id) for strategy_id in strategies)
    leaders = sorted(strategy_id for strategy_id in strategies if vector(strategy_id) == best)
    return {"strategy_ids": leaders, "rule": rule, "co_leader": len(leaders) > 1}


async def evaluate_queries(
    *,
    adapter: Any,
    query_ids: Sequence[str],
    candidate_ids: Sequence[str],
    grades_by_job: Mapping[str, Mapping[str, int]],
    pairs_by_job: Mapping[str, Sequence[tuple[str, str]]],
    include_r3: bool = True,
    dataset_fingerprint: str = "unspecified_test_fixture",
    index_fingerprint: str = "unspecified_test_fixture",
) -> dict[str, Any]:
    r1_values = {
        strategy: {f"retrieval_recall_at_{k}": {} for k in (5, 10, 20)}
        for strategy in R1_STRATEGIES
    }
    r2_values = {
        strategy: {metric: {} for metric in (
            "judged_condensed_ndcg_at_5", "judged_condensed_ndcg_at_10",
            "judged_condensed_mrr_at_10", "explicit_pairwise_accuracy",
        )}
        for strategy in R2_STRATEGIES
    }
    per_query_provenance: dict[str, Any] = {}
    r1_provenance: dict[str, dict[str, Any]] = {strategy: {} for strategy in R1_STRATEGIES}
    r3: dict[str, Any] = {}
    pool_depth = len(candidate_ids)
    for query_id in query_ids:
        grades = grades_by_job[query_id]
        pairs = pairs_by_job[query_id]
        for strategy in R1_STRATEGIES:
            output = await adapter.retrieve(query_id, strategy, 20)
            ordered = list(output.ordered_candidate_ids)
            if len(ordered) != len(set(ordered)):
                raise EvaluationIntegrityError("R1 strategy returned duplicate Candidate IDs")
            if not set(ordered) <= set(candidate_ids):
                raise EvaluationIntegrityError("R1 strategy returned unknown Candidate IDs")
            r1_provenance[strategy][query_id] = {
                "candidate_universe": "all_frozen_candidates",
                "expected_candidate_ids": sorted(candidate_ids),
                "source_retrieval_strategy": strategy,
                "retrieval_config_fingerprint": RETRIEVAL_CONFIGURATION_FINGERPRINT,
                "requested_pool_depth": 20,
                "returned_count": len(ordered),
                "eligible_count": int(output.diagnostics.get("eligible_count", len(candidate_ids))),
                "filters": [],
                "index_state": output.diagnostics.get("index_freshness", "unknown"),
                "index_fingerprint": index_fingerprint,
                "ordered_candidate_ids": ordered,
                "sorted_unique_candidate_ids": sorted(set(ordered)),
                "pool_fingerprint": canonical_fingerprint({"query_id": query_id, "strategy": strategy, "candidate_ids": sorted(set(ordered)), "index_fingerprint": index_fingerprint}),
                "order_fingerprint": canonical_fingerprint({"query_id": query_id, "strategy": strategy, "candidate_ids": ordered}),
                "dataset_fingerprint": dataset_fingerprint,
                "score_semantics": "cosine" if strategy == "dense_v4" else "bm25" if strategy == "sparse_bm25_v4" else "equal_weight_rrf_score",
            }
            for k in (5, 10, 20):
                r1_values[strategy][f"retrieval_recall_at_{k}"][query_id] = retrieval_recall_at_k(output.ordered_candidate_ids, grades, k=k)

        hybrid = await adapter.retrieve(query_id, "hybrid_rrf_v4", pool_depth)
        ltr = await adapter.rank_ltr(query_id, pool_depth, pool_depth)
        ce = await adapter.rank_ce(query_id, pool_depth, pool_depth, pool_depth)
        outputs = {item.strategy_id: item for item in (hybrid, ltr, ce)}
        hybrid_diagnostics = hybrid.diagnostics
        score_semantics = {
            "hybrid_rrf_v4": "equal_weight_rrf_score",
            "ltr_ranker_v1": "raw_lightgbm_margin",
            "cross_encoder_experiment": "raw_cross_encoder_logit",
        }
        provenance = {
            strategy: build_pool_provenance(
                query_id, candidate_ids, output.ordered_candidate_ids,
                source_retrieval_strategy="hybrid_rrf_v4",
                retrieval_config_fingerprint=RETRIEVAL_CONFIGURATION_FINGERPRINT,
                requested_pool_depth=pool_depth,
                eligible_count=int(hybrid_diagnostics.get("eligible_count", pool_depth)),
                filters=(), index_state=str(hybrid_diagnostics.get("index_freshness", "unknown")),
                index_fingerprint=index_fingerprint, ranking_strategy=strategy,
                rerank_depth=pool_depth, score_semantics=score_semantics[strategy],
                dataset_fingerprint=dataset_fingerprint,
                feature_fingerprint=FEATURE_FINGERPRINT if strategy != "hybrid_rrf_v4" else None,
                model_fingerprint=RANKER_MODEL_SHA256 if strategy != "hybrid_rrf_v4" else None,
                ce_fingerprint=CE_SNAPSHOT_FINGERPRINT if strategy == "cross_encoder_experiment" else None,
            )
            for strategy, output in outputs.items()
        }
        assert_comparable_orders(provenance)
        judged_ids = set(grades)
        for strategy, output in outputs.items():
            condensed = condense_to_judged(output.ordered_candidate_ids, judged_ids)
            r2_values[strategy]["judged_condensed_ndcg_at_5"][query_id] = judged_condensed_ndcg_at_k(condensed, grades, k=5)
            r2_values[strategy]["judged_condensed_ndcg_at_10"][query_id] = judged_condensed_ndcg_at_k(condensed, grades, k=10)
            r2_values[strategy]["judged_condensed_mrr_at_10"][query_id] = judged_condensed_mrr_at_k(condensed, grades, k=10)
            r2_values[strategy]["explicit_pairwise_accuracy"][query_id] = explicit_pairwise_accuracy(output.scores, pairs)
        per_query_provenance[query_id] = {
            strategy: item.model_dump(mode="json") for strategy, item in provenance.items()
        }
        if include_r3:
            ltr_runtime = await adapter.rank_ltr(query_id, 20, 10)
            ce_runtime = await adapter.rank_ce(query_id, 20, 10, 5)
            r3[query_id] = {
                "hybrid20_ltr10": {
                    "ordered_candidate_ids": list(ltr_runtime.ordered_candidate_ids),
                    "relevant_coverage": retrieval_recall_at_k(ltr_runtime.ordered_candidate_ids, grades, k=10).value,
                    "input_pool_depth": 20,
                    "output_count": len(ltr_runtime.ordered_candidate_ids),
                    "retention_rate": len(ltr_runtime.ordered_candidate_ids) / 20,
                    "provenance": _without_timing(ltr_runtime.diagnostics),
                },
                "hybrid20_ltr10_ce5": {
                    "ordered_candidate_ids": list(ce_runtime.ordered_candidate_ids),
                    "relevant_coverage": retrieval_recall_at_k(ce_runtime.ordered_candidate_ids, grades, k=5).value,
                    "input_pool_depth": 10,
                    "output_count": len(ce_runtime.ordered_candidate_ids),
                    "retention_rate": len(ce_runtime.ordered_candidate_ids) / 10,
                    "provenance": _without_timing(ce_runtime.diagnostics),
                },
            }

    r1_strategies = {
        strategy: {metric: _metric_payload(per_query) for metric, per_query in metrics.items()}
        for strategy, metrics in r1_values.items()
    }
    r2_strategies = {
        strategy: {metric: _metric_payload(per_query) for metric, per_query in metrics.items()}
        for strategy, metrics in r2_values.items()
    }
    return {
        "r1": {
            "cohort": "full_corpus_retrieval",
            "strategies": r1_strategies,
            "per_query_provenance": r1_provenance,
            "leader": _leader(r1_strategies, ("retrieval_recall_at_10", "retrieval_recall_at_20", "retrieval_recall_at_5"), "recall@10>recall@20>recall@5>co-leader"),
        },
        "r2": {
            "cohort": "controlled_full_pool_then_judged_condensation",
            "strategies": r2_strategies,
            "leader": _leader(r2_strategies, ("judged_condensed_ndcg_at_5", "judged_condensed_ndcg_at_10", "explicit_pairwise_accuracy"), "ndcg@5>ndcg@10>pairwise_accuracy>co-leader"),
            "per_query_pool_provenance": per_query_provenance,
        },
        "r3": {"role": "runtime_cascade_diagnostics_only", "per_query": r3} if include_r3 else {"status": "NOT_RUN"},
    }
