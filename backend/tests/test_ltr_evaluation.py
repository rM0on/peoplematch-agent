from __future__ import annotations

from test_ltr_training import _training_artifact


def test_dev_report_is_judged_set_only_and_compares_hybrid_and_ltr() -> None:
    from app.services.ranking.evaluation import build_dev_report

    artifact = _training_artifact()
    dev_rows = artifact["splits"]["dev"]["rows"]
    report = build_dev_report(
        artifact=artifact,
        dev_scores=[float(index) for index in range(len(dev_rows))],
        pairwise_preferences=[
            ("job_015", dev_rows[0]["candidate_id"], dev_rows[-1]["candidate_id"])
        ],
        ranker_version="ltr_ranker_v1",
    )

    assert report["evaluation_scope"] == "judged_set_reranking"
    assert report["incomplete_judgments"] is True
    assert report["test_evaluated"] is False
    assert report["relevance_threshold"] == 2
    assert report["gain_policy"] == "2^relevance_minus_1"
    assert report["query_ids"] == ["job_015"]
    assert report["judged_row_count"] == 12
    assert set(report["metrics"]) == {"hybrid", "ltr"}
    assert set(report["metrics"]["ltr"]) == {
        "ndcg_at_5",
        "ndcg_at_10",
        "mrr",
        "pairwise_accuracy",
    }
