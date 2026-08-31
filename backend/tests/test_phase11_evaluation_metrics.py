from __future__ import annotations

import math

import pytest


def test_unjudged_is_not_negative_and_reference_metrics_are_hand_auditable() -> None:
    from app.services.evaluation.metrics import (
        judged_condensed_mrr_at_k,
        judged_condensed_ndcg_at_k,
        retrieval_recall_at_k,
    )

    grades = {"a": 3, "b": 2, "c": 0}
    order = ["unjudged", "b", "c", "a"]

    assert retrieval_recall_at_k(order, grades, k=2).value == pytest.approx(0.5)
    # Condensed order is b,c,a; DCG@3 = 3 + 0 + 7/2, IDCG = 7 + 3/log2(3).
    expected = (3 + 7 / 2) / (7 + 3 / math.log2(3))
    assert judged_condensed_ndcg_at_k(order, grades, k=3).value == pytest.approx(expected)
    assert judged_condensed_mrr_at_k(order, grades, k=10).value == pytest.approx(1.0)


def test_metric_undefined_queries_are_excluded_not_zero() -> None:
    from app.services.evaluation.metrics import (
        judged_condensed_mrr_at_k,
        judged_condensed_ndcg_at_k,
        retrieval_recall_at_k,
    )

    grades = {"a": 0, "b": 1}
    assert retrieval_recall_at_k(["a", "b"], grades, k=5).value is None
    assert judged_condensed_ndcg_at_k(["a", "b"], grades, k=5).value is None
    assert judged_condensed_mrr_at_k(["a", "b"], grades, k=10).value is None


def test_explicit_pairwise_accuracy_uses_exact_ties_and_rejects_missing_scores() -> None:
    from app.services.evaluation.metrics import explicit_pairwise_accuracy

    pairs = [("a", "b"), ("c", "d")]
    assert explicit_pairwise_accuracy({"a": 2.0, "b": 1.0, "c": 4.0, "d": 4.0}, pairs).value == 0.75
    with pytest.raises(ValueError, match="missing score"):
        explicit_pairwise_accuracy({"a": 2.0, "b": 1.0}, pairs)
    with pytest.raises(ValueError, match="finite"):
        explicit_pairwise_accuracy({"a": float("nan"), "b": 1.0}, [("a", "b")])


def test_standard_precision_is_rejected() -> None:
    from app.services.evaluation.metrics import unsupported_standard_precision_at_k

    with pytest.raises(ValueError, match="unsupported"):
        unsupported_standard_precision_at_k()


def test_macro_aggregation_records_exclusions() -> None:
    from app.services.evaluation.metrics import MetricValue, macro_average

    result = macro_average(
        {
            "job_001": MetricValue(value=1.0),
            "job_002": MetricValue(value=None, exclusion_reason="no_relevant_judgment"),
            "job_003": MetricValue(value=0.0),
        }
    )
    assert result.mean == 0.5
    assert result.total_queries == 3
    assert result.eligible_queries == 2
    assert result.excluded_queries == 1
    assert result.excluded_reasons == {"no_relevant_judgment": 1}
