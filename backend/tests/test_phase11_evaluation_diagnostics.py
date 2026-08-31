from __future__ import annotations

import pytest


def test_explanation_checks_reject_cross_owner_and_unsupported_references() -> None:
    from app.services.evaluation.explanations import evaluate_explanation

    evidence = {
        "fact_1": {"candidate_id": "cand_a", "match_run_id": "run_1"},
    }
    with pytest.raises(ValueError, match="owner"):
        evaluate_explanation(
            candidate_id="cand_b", match_run_id="run_1", evidence_facts=evidence,
            referenced_fact_ids=["fact_1"], ranking_before=["cand_b"], ranking_after=["cand_b"],
            repeated_output="same", original_output="same",
        )
    result = evaluate_explanation(
        candidate_id="cand_a", match_run_id="run_1", evidence_facts=evidence,
        referenced_fact_ids=["fact_1", "missing"], ranking_before=["cand_a"], ranking_after=["cand_a"],
        repeated_output="same", original_output="same",
    )
    assert result.unsupported_claim_count == 1
    assert result.unsupported_claim_rate == 0.5
    assert result.ranking_invariance is True
    assert result.deterministic_repeatability is True


def test_explanation_ranking_invariance_violation_is_visible() -> None:
    from app.services.evaluation.explanations import evaluate_explanation

    result = evaluate_explanation(
        candidate_id="a", match_run_id="r", evidence_facts={}, referenced_fact_ids=[],
        ranking_before=["a", "b"], ranking_after=["b", "a"],
        original_output="x", repeated_output="x",
    )
    assert result.ranking_invariance is False


def test_phase10_export_rejects_truncation_and_bad_verification() -> None:
    from app.services.evaluation.diagnostics import validate_phase10_export

    with pytest.raises(ValueError, match="truncated"):
        validate_phase10_export({"contract_version": "phase10_review_export_v1", "truncated_collections": ["analyses"]})
    with pytest.raises(ValueError, match="verification"):
        validate_phase10_export({"contract_version": "phase10_review_export_v1", "verification_state": "case_specific_verified", "verification_reference": None})


def test_latency_summary_is_descriptive_only() -> None:
    from app.services.evaluation.latency import summarize_latency

    summary = summarize_latency([float(i) for i in range(1, 101)])
    assert summary.count == 100
    assert summary.p50_ms == pytest.approx(50.5)
    assert summary.p95_ms == pytest.approx(95.05)
    assert not hasattr(summary, "qps")
