from __future__ import annotations


def test_cross_encoder_evaluation_uses_identical_judged_sets_and_no_test() -> None:
    from scripts.evaluate_cross_encoder import build_evaluation_report

    report = build_evaluation_report(
        query_ids=["job_015"],
        judged_rows=[
            {"job_id": "job_015", "candidate_id": "cand_001", "relevance_grade": 3},
            {"job_id": "job_015", "candidate_id": "cand_002", "relevance_grade": 1},
        ],
        ltr_scores=[0.2, 0.1],
        ce_scores=[0.1, 0.2],
        pairwise_preferences=[("job_015", "cand_001", "cand_002")],
        model_metadata={"model_id": "model", "revision": "r"},
    )
    assert report["evaluation_scope"] == "cross_encoder_judged_set_dev_reranking"
    assert report["incomplete_judgments"] is True
    assert report["test_evaluated"] is False
    assert report["judged_row_count"] == 2
    assert report["candidate_set_policy"] == "identical_judged_candidates_for_ltr_and_cross_encoder"
    assert report["metrics"]["ltr"]["pairwise_accuracy"] == 1.0
    assert report["metrics"]["cross_encoder"]["pairwise_accuracy"] == 0.0


def test_evaluation_rejects_test_queries() -> None:
    import pytest

    from scripts.evaluate_cross_encoder import build_evaluation_report

    with pytest.raises(ValueError, match="Test"):
        build_evaluation_report(
            query_ids=["job_020"],
            judged_rows=[],
            ltr_scores=[],
            ce_scores=[],
            pairwise_preferences=[],
            model_metadata={},
        )


def test_cross_encoder_ties_follow_ltr_then_retrieval_fallback() -> None:
    from scripts.evaluate_cross_encoder import _ordered_indices

    rows = [
        {"candidate_id": "cand_a"},
        {"candidate_id": "cand_b"},
    ]
    # Candidate B is the stronger LTR result, so it must win an otherwise
    # tied CE score without consulting relevance grades.
    assert _ordered_indices(
        rows,
        scores=[1.0, 2.0],
        tie_ranks={0: 2, 1: 1},
    ) == [1, 0]
