from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def _dcg(relevance: Sequence[int], k: int) -> float:
    return sum(
        ((2**grade) - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(relevance[:k], start=1)
    )


def ndcg_at_k(relevance: Sequence[int], k: int) -> float:
    if not relevance or k <= 0:
        return 0.0
    ideal = _dcg(sorted(relevance, reverse=True), k)
    return _dcg(relevance, k) / ideal if ideal else 0.0


def reciprocal_rank(
    relevance: Sequence[int], *, relevance_threshold: int = 2
) -> float:
    rank = next(
        (
            rank
            for rank, grade in enumerate(relevance, start=1)
            if grade >= relevance_threshold
        ),
        None,
    )
    return 1.0 / rank if rank is not None else 0.0


def pairwise_accuracy(
    scores: Mapping[str, float], preferences: Sequence[tuple[str, str]]
) -> float:
    if not preferences:
        return 0.0
    values = []
    for winner_id, loser_id in preferences:
        winner = scores[winner_id]
        loser = scores[loser_id]
        values.append(1.0 if winner > loser else 0.5 if winner == loser else 0.0)
    return sum(values) / len(values)


def deterministic_rank_order(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        rows,
        key=lambda item: (
            -float(item["score"]),
            int(item["retrieval_rank"]),
            str(item["entity_id"]),
        ),
    )
