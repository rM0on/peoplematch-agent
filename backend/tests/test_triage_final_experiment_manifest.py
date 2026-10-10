"""Fail-closed final experiment freeze without calling a provider."""

import json

import pytest

from narrative_triage_final_live_experiment import (
    SAMPLES, build_frozen_cases, build_manifest, canonical_hash,
    verify_manifest, verify_record_sequence,
)


def test_final_case_order_and_request_freeze_are_deterministic():
    cases = build_frozen_cases()
    assert [case["scenario_id"] for case in cases] == [sample[0] for sample in SAMPLES]
    first = build_manifest("triage_test", cases)
    second = build_manifest("triage_test", build_frozen_cases())
    assert first == second
    assert len(first["cases"]) == 8
    assert first["model"] == "qwen3.7-flash-2026-07-15"
    assert len({case["request_sha256"] for case in first["cases"]}) == 8
    assert verify_manifest(json.loads(json.dumps(first)), first)


def test_manifest_detects_fixture_request_implementation_and_order_change():
    frozen = build_manifest("triage_test", build_frozen_cases())
    for changed in (
        {**frozen, "fixture_sha256": "0" * 64},
        {**frozen, "implementation_sha256": "0" * 64},
        {**frozen, "cases": [{**frozen["cases"][0], "request_sha256": "0" * 64},
                             *frozen["cases"][1:]]},
        {**frozen, "cases": [frozen["cases"][1], frozen["cases"][0], *frozen["cases"][2:]]},
    ):
        with pytest.raises(ValueError, match="manifest_changed"):
            verify_manifest(changed, frozen)


def test_sequence_rejects_duplicate_and_unfinished_attempt():
    cases = build_frozen_cases()
    ids = [case["scenario_id"] for case in cases]
    records = [{"record_type": "case_started", "scenario_id": ids[0]},
               {"record_type": "case_result", "scenario_id": ids[0]}]
    assert verify_record_sequence(records, ids) == (ids[0],)
    with pytest.raises(ValueError, match="ambiguous_interrupted_attempt"):
        verify_record_sequence(records + [{"record_type": "case_started", "scenario_id": ids[1]}], ids)
    with pytest.raises(ValueError, match="duplicate_case"):
        verify_record_sequence(records + records[:2], ids)
    with pytest.raises(ValueError, match="case_order_changed"):
        verify_record_sequence([{"record_type": "case_started", "scenario_id": ids[1]}], ids)
    assert canonical_hash({"rows": ("a", "b")}) == canonical_hash({"rows": ["a", "b"]})
