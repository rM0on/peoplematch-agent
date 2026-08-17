from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.services.features.contract import FEATURE_FINGERPRINT
from app.services.ranking.contract import RANKER_VERSION
from app.services.ranking.dataset import matrix_for_split
from app.services.ranking.metrics import (
    ndcg_at_k,
    pairwise_accuracy,
    reciprocal_rank,
)


def _preference_parts(preference: Any) -> tuple[str, str, str]:
    if isinstance(preference, tuple):
        return preference
    return (
        str(preference.job_id),
        str(preference.winner_candidate_id),
        str(preference.loser_candidate_id),
    )


def _aggregate(per_query: Sequence[dict[str, float]]) -> dict[str, float]:
    if not per_query:
        return {
            "ndcg_at_5": 0.0,
            "ndcg_at_10": 0.0,
            "mrr": 0.0,
            "pairwise_accuracy": 0.0,
        }
    metric_keys = ("ndcg_at_5", "ndcg_at_10", "mrr", "pairwise_accuracy")
    return {
        key: sum(float(item[key]) for item in per_query) / len(per_query)
        for key in metric_keys
    }


def build_dev_report(
    *,
    artifact: dict[str, Any],
    dev_scores: Sequence[float],
    pairwise_preferences: Sequence[Any],
    ranker_version: str = RANKER_VERSION,
) -> dict[str, Any]:
    matrix = matrix_for_split(artifact, "dev")
    if len(dev_scores) != len(matrix.pair_ids):
        raise ValueError("Dev score count does not match the Dev matrix")
    preferences_by_job: dict[str, list[tuple[str, str]]] = {
        job_id: [] for job_id in matrix.query_ids
    }
    for preference in pairwise_preferences:
        job_id, winner, loser = _preference_parts(preference)
        if job_id in preferences_by_job:
            preferences_by_job[job_id].append((winner, loser))

    per_query: dict[str, dict[str, list[dict[str, float]]]] = {
        "hybrid": [],
        "ltr": [],
    }
    offset = 0
    for job_id, group_size in zip(matrix.query_ids, matrix.groups):
        rows = artifact["splits"]["dev"]["rows"][offset : offset + group_size]
        scores = [float(value) for value in dev_scores[offset : offset + group_size]]
        offset += group_size
        grades = [int(row["relevance_grade"]) for row in rows]
        hybrid_scores = {
            str(row["candidate_id"]): -index for index, row in enumerate(rows)
        }
        ltr_order = sorted(
            range(group_size),
            key=lambda index: (-scores[index], index, str(rows[index]["candidate_id"])),
        )
        ltr_grades = [grades[index] for index in ltr_order]
        ltr_scores = {
            str(row["candidate_id"]): score
            for row, score in zip(rows, scores)
        }
        preferences = preferences_by_job[job_id]
        for name, ordered_grades, score_map in (
            ("hybrid", grades, hybrid_scores),
            ("ltr", ltr_grades, ltr_scores),
        ):
            per_query[name].append(
                {
                    "job_id": job_id,
                    "ndcg_at_5": ndcg_at_k(ordered_grades, 5),
                    "ndcg_at_10": ndcg_at_k(ordered_grades, 10),
                    "mrr": reciprocal_rank(ordered_grades, relevance_threshold=2),
                    "pairwise_accuracy": pairwise_accuracy(score_map, preferences),
                }
            )
    return {
        "artifact_version": "ltr_dev_report_v1",
        "evaluation_scope": "judged_set_reranking",
        "incomplete_judgments": True,
        "test_evaluated": False,
        "relevance_threshold": 2,
        "gain_policy": "2^relevance_minus_1",
        "query_ids": list(matrix.query_ids),
        "judged_row_count": len(matrix.pair_ids),
        "ranker_version": ranker_version,
        "ltr_dataset_fingerprint": artifact["ltr_dataset_fingerprint"],
        "feature_fingerprint": FEATURE_FINGERPRINT,
        "per_query": per_query,
        "metrics": {
            "hybrid": _aggregate(per_query["hybrid"]),
            "ltr": _aggregate(per_query["ltr"]),
        },
    }
