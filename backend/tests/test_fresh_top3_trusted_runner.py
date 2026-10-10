"""No-network invariants for the opt-in Fresh Top-3 runner."""

from __future__ import annotations

import pytest

from fresh_top3_trusted_chain import (
    COHORT_FILTERS, FIXTURE, IMPLEMENTATION, StageFailure, _candidate_record_hashes,
    _check_brief, _check_explanation_readback, _snapshot,
    _validate_candidate_cohort, health_url,
)


def test_health_preflight_uses_root_route_not_versioned_api_route():
    assert health_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000/health"
    assert health_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000/health"


def test_runner_snapshot_detects_order_score_or_fingerprint_change():
    run = {"results": [{"candidate_id": "a", "ltr_score_raw": 0.5},
                       {"candidate_id": "b", "ltr_score_raw": 0.4}],
           "result_fingerprint": "f" * 64}
    before = _snapshot(run)
    assert before == {"order": ["a", "b"], "ltr_scores": [0.5, 0.4],
                      "ranking_fingerprint": "f" * 64}
    run["results"][0]["ltr_score_raw"] = 0.6
    assert _snapshot(run) != before


def test_runner_rejects_foreign_candidate_before_reporting_a_brief():
    run = {"run_id": "fresh", "result_fingerprint": "f" * 64}
    result = {"candidate_id": "a", "result_rank": 1}
    brief = {"match_run_id": "fresh", "ranking_fingerprint": "f" * 64,
             "source_explanation_id": 42, "candidate_id": "b", "result_rank": 1,
             "review_status": "TRUSTED_STRUCTURED"}
    with pytest.raises(StageFailure, match="structured_brief_identity_or_ranking_mismatch"):
        _check_brief(brief, result, run, 42)


def test_fresh_cohort_is_predeclared_and_fails_closed_on_non_synthetic_records():
    assert COHORT_FILTERS == {"cities": ["Beijing"], "seniorities": ["mid"]}
    good = [
        {"candidate_id": "sandbox-a", "data_origin": "synthetic_sandbox",
         "dataset_version": "1.0.0", "seniority": "mid",
         "preferred_locations": {"cities": ["Beijing"]}},
        {"candidate_id": "sandbox-b", "data_origin": "synthetic_sandbox",
         "dataset_version": "1.0.0", "seniority": "mid",
         "preferred_locations": {"cities": ["Beijing"]}},
        {"candidate_id": "sandbox-c", "data_origin": "synthetic_sandbox",
         "dataset_version": "1.0.0", "seniority": "mid",
         "preferred_locations": {"cities": ["Beijing"]}},
    ]
    ids, record_hash = _validate_candidate_cohort(good)
    assert ids == ("sandbox-a", "sandbox-b", "sandbox-c")
    assert len(record_hash) == 64
    assert _validate_candidate_cohort(list(reversed(good))) == (ids, record_hash)
    assert _validate_candidate_cohort([{**good[0], "target_roles": ["Backend Engineer"]},
                                       *good[1:]])[1] != record_hash
    with pytest.raises(StageFailure, match="candidate_pool_non_synthetic"):
        _validate_candidate_cohort(good[:-1] + [{**good[-1], "data_origin": "user_created"}])
    with pytest.raises(StageFailure, match="candidate_pool_duplicate"):
        _validate_candidate_cohort(good + [good[0]])


def test_final_experiment_uses_new_input_and_freezes_individual_candidate_records():
    assert FIXTURE.name == "fresh_top3_trusted_jd_20261009.txt"
    assert FIXTURE.read_text(encoding="utf-8") != FIXTURE.with_name(
        "fresh_top3_trusted_jd_20261008.txt"
    ).read_text(encoding="utf-8")
    records = [
        {"candidate_id": "sandbox-b", "data_origin": "synthetic_sandbox", "value": 2},
        {"candidate_id": "sandbox-a", "data_origin": "synthetic_sandbox", "value": 1},
    ]
    hashes = _candidate_record_hashes(records)
    assert list(hashes) == ["sandbox-a", "sandbox-b"]
    assert all(len(value) == 64 for value in hashes.values())
    assert hashes == _candidate_record_hashes(list(reversed(records)))
    assert hashes["sandbox-a"] != _candidate_record_hashes(
        [{**records[0]}, {**records[1], "value": 3}]
    )["sandbox-a"]


def test_final_experiment_freezes_phase9_selection_and_grounding_code():
    frozen_names = {path.name for path in IMPLEMENTATION}
    assert {"semantic_selection.py", "explanation_prompt_v4.txt", "pipeline.py"} <= frozen_names


def test_explanation_readback_requires_exact_persisted_ownership_and_refs():
    expected = [
        {"match_explanation_id": 11, "candidate_id": "a", "result_rank": 1},
        {"match_explanation_id": 12, "candidate_id": "b", "result_rank": 2},
        {"match_explanation_id": 13, "candidate_id": "c", "result_rank": 3},
    ]
    detail = {"status": "COMPLETED", "explanation_count": 3,
              "explanations": [{**item, "summary": {"evidence_refs": [
                  "job_requirement:r1", f"candidate:{item['result_rank']}:project:p1"]}}
                               for item in expected]}
    assert _check_explanation_readback(detail, expected) == (11, 12, 13)
    detail["explanations"][1]["summary"]["evidence_refs"][1] = "candidate:1:project:p1"
    with pytest.raises(StageFailure, match="explanation_cross_candidate_reference"):
        _check_explanation_readback(detail, expected)
