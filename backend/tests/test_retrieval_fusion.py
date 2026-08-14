from __future__ import annotations

import pytest


def test_rrf_is_mathematically_correct_with_missing_channel_contributions() -> None:
    from app.services.retrieval.fusion import reciprocal_rank_fusion
    from app.schemas.retrieval import ChannelResult

    dense = [
        ChannelResult(entity_id="A", rank=1, score=0.9),
        ChannelResult(entity_id="B", rank=2, score=0.8),
        ChannelResult(entity_id="C", rank=3, score=0.7),
    ]
    sparse = [
        ChannelResult(entity_id="B", rank=1, score=4.0),
        ChannelResult(entity_id="D", rank=2, score=3.0),
        ChannelResult(entity_id="A", rank=3, score=2.0),
    ]

    fused = reciprocal_rank_fusion(dense, sparse, rrf_k=60)
    by_id = {item.entity_id: item for item in fused}

    assert by_id["A"].fusion_score == pytest.approx(1 / 61 + 1 / 63)
    assert by_id["B"].fusion_score == pytest.approx(1 / 62 + 1 / 61)
    assert by_id["C"].fusion_score == pytest.approx(1 / 63)
    assert by_id["D"].fusion_score == pytest.approx(1 / 62)
    assert [item.entity_id for item in fused] == ["B", "A", "D", "C"]


def test_rrf_stable_ties_use_best_channel_rank_then_entity_id() -> None:
    from app.services.retrieval.fusion import reciprocal_rank_fusion
    from app.schemas.retrieval import ChannelResult

    dense = [
        ChannelResult(entity_id="z", rank=1, score=1.0),
        ChannelResult(entity_id="a", rank=2, score=0.9),
    ]
    sparse = [
        ChannelResult(entity_id="a", rank=1, score=2.0),
        ChannelResult(entity_id="z", rank=2, score=1.0),
    ]

    fused = reciprocal_rank_fusion(dense, sparse, rrf_k=60)
    assert fused[0].fusion_score == fused[1].fusion_score
    assert [item.entity_id for item in fused] == ["a", "z"]
