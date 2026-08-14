from __future__ import annotations

from typing import Sequence

from app.schemas.retrieval import ChannelResult, FusedResult


def reciprocal_rank_fusion(
    dense_results: Sequence[ChannelResult],
    sparse_results: Sequence[ChannelResult],
    *,
    rrf_k: int,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
) -> list[FusedResult]:
    entries: dict[str, dict[str, float | int | None]] = {}
    for channel, results, weight in (
        ("dense", dense_results, dense_weight),
        ("sparse", sparse_results, sparse_weight),
    ):
        for result in results:
            entry = entries.setdefault(
                result.entity_id,
                {
                    "fusion_score": 0.0,
                    "dense_rank": None,
                    "dense_score": None,
                    "sparse_rank": None,
                    "sparse_score": None,
                },
            )
            entry["fusion_score"] = float(entry["fusion_score"]) + weight / (
                rrf_k + result.rank
            )
            entry[f"{channel}_rank"] = result.rank
            entry[f"{channel}_score"] = result.score

    fused = [FusedResult(entity_id=entity_id, **values) for entity_id, values in entries.items()]
    fused.sort(
        key=lambda item: (
            -item.fusion_score,
            min(
                rank
                for rank in (item.dense_rank, item.sparse_rank)
                if rank is not None
            ),
            item.entity_id,
        )
    )
    return fused
