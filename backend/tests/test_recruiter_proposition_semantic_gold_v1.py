"""Offline-only integrity and evaluation tests for the six historical synthetic outputs."""

from __future__ import annotations

from copy import deepcopy

import pytest

from semantic_gold_proposition_v1 import (
    evaluate_historical_semantic_audit_v1,
    load_semantic_gold_v1,
    validate_semantic_gold_v1,
)


def test_six_historical_narratives_and_original_blind_atoms_are_archived():
    gold, historical, provenance = load_semantic_gold_v1()
    assert len(gold["cases"]) == len(historical["cases"]) == len(provenance["cases"]) == 6
    assert sum(len(case["gold"]) for case in gold["cases"]) >= 60
    assert sum(len(paragraph["atoms"]) for case in historical["cases"]
               for paragraph in case["semantic_atoms"]) == 70
    assert all(case["model"] == "qwen3.7-flash-2026-07-15" for case in historical["cases"])


def test_gold_provenance_and_original_predictions_rebuild_exactly():
    gold, historical, provenance = load_semantic_gold_v1()
    validate_semantic_gold_v1(gold, historical, provenance)


def test_gold_quote_must_be_exact_and_candidate_identity_isolated():
    gold, historical, provenance = load_semantic_gold_v1()
    changed = deepcopy(gold)
    changed["cases"][0]["gold"][0]["quote"] = "absent gold quote"
    with pytest.raises(ValueError, match="gold_quote_not_unique_in_paragraph"):
        validate_semantic_gold_v1(changed, historical, provenance)
    changed = deepcopy(historical)
    changed["cases"][0]["candidate_id"] = "candidate_002"
    with pytest.raises(ValueError, match="candidate_identity_mismatch"):
        validate_semantic_gold_v1(gold, changed, provenance)


def test_baseline_metrics_are_reproducible_and_not_model_handle_self_report():
    gold, historical, provenance = load_semantic_gold_v1()
    first = evaluate_historical_semantic_audit_v1(gold, historical, provenance)
    second = evaluate_historical_semantic_audit_v1(gold, historical, provenance)
    assert first == second
    assert first["sample_count"] == 6
    assert first["auditor_atom_count"] == 70
    assert first["semantic_item_detection"]["denominator"] > 0
    assert first["unsupported_detection"]["precision"] is not None
    assert first["unsupported_detection"]["recall"] is not None
    assert first["category_accuracy"]["denominator"] > 0
    assert first["historical_audit_pass_count"] == 0
    assert first["replayed_issue_match_count"] == 6
    assert "selected_handles" not in first


def test_missing_real_blind_atoms_fail_closed_instead_of_inventing_metrics():
    gold, historical, provenance = load_semantic_gold_v1()
    changed = deepcopy(historical)
    changed["cases"][0]["semantic_atoms"] = []
    with pytest.raises(ValueError, match="historical_blind_atoms_missing"):
        evaluate_historical_semantic_audit_v1(gold, changed, provenance)
