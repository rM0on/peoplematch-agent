from __future__ import annotations


def test_ndcg_uses_graded_gain_and_known_ideal_order() -> None:
    from app.services.ranking.metrics import ndcg_at_k

    assert ndcg_at_k([3, 2, 1, 0], 4) == 1.0
    assert 0.0 < ndcg_at_k([0, 1, 2, 3], 4) < 1.0
    assert ndcg_at_k([], 5) == 0.0


def test_mrr_uses_relevance_grade_two_threshold() -> None:
    from app.services.ranking.metrics import reciprocal_rank

    assert reciprocal_rank([0, 1, 2, 3], relevance_threshold=2) == 1 / 3
    assert reciprocal_rank([0, 1, 1], relevance_threshold=2) == 0.0


def test_pairwise_accuracy_scores_win_loss_and_tie() -> None:
    from app.services.ranking.metrics import pairwise_accuracy

    preferences = [
        ("winner", "loser"),
        ("winner", "tie"),
        ("loser", "winner"),
    ]
    scores = {"winner": 2.0, "loser": 1.0, "tie": 2.0}

    assert pairwise_accuracy(scores, preferences) == (1.0 + 0.5 + 0.0) / 3


def test_deterministic_rerank_uses_retrieval_rank_then_entity_id_for_ties() -> None:
    from app.services.ranking.metrics import deterministic_rank_order

    rows = [
        {"entity_id": "cand_b", "retrieval_rank": 2, "score": 1.0},
        {"entity_id": "cand_c", "retrieval_rank": 1, "score": 1.0},
        {"entity_id": "cand_a", "retrieval_rank": 1, "score": 1.0},
        {"entity_id": "cand_d", "retrieval_rank": 4, "score": 2.0},
    ]

    assert [item["entity_id"] for item in deterministic_rank_order(rows)] == [
        "cand_d",
        "cand_a",
        "cand_c",
        "cand_b",
    ]
