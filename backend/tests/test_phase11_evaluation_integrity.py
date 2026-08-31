from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_frozen_judgment_bundle_is_exact_and_hash_validated() -> None:
    from app.services.evaluation.judgments import load_frozen_judgments

    bundle = load_frozen_judgments(ROOT)
    assert len(bundle.candidate_ids) == 48
    assert len(bundle.job_ids) == 24
    assert len(bundle.labels) == 288
    assert len(bundle.pairs) == 48
    assert all(len(bundle.grades_by_job[job_id]) == 12 for job_id in bundle.job_ids)
    assert all(len(bundle.pairs_by_job[job_id]) == 2 for job_id in bundle.job_ids)


def test_dataset_hash_mismatch_is_invalid(tmp_path: Path) -> None:
    from app.services.evaluation.judgments import EvaluationIntegrityError, load_frozen_judgments

    manifest = json.loads((ROOT / "data/eval/dataset_freeze_manifest.json").read_text())
    manifest["canonical_files"]["data/samples/labels.jsonl"] = "0" * 64
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(EvaluationIntegrityError, match="SHA-256"):
        load_frozen_judgments(ROOT, manifest_path=manifest_path)


def test_full_pool_validation_and_fingerprints_fail_closed() -> None:
    from app.services.evaluation.provenance import (
        EvaluationIntegrityError,
        assert_comparable_orders,
        build_pool_provenance,
        condense_to_judged,
    )

    expected = ["a", "b", "c"]
    pool = build_pool_provenance("job_x", expected, expected)
    assert pool.pool_fingerprint != pool.order_fingerprint
    assert condense_to_judged(["x", "c", "a", "b"], {"a", "b", "c"}) == ["c", "a", "b"]
    with pytest.raises(EvaluationIntegrityError, match="duplicate"):
        build_pool_provenance("job_x", expected, ["a", "a", "c"])
    with pytest.raises(EvaluationIntegrityError, match="unknown"):
        build_pool_provenance("job_x", expected, ["a", "b", "x"])
    with pytest.raises(EvaluationIntegrityError, match="missing"):
        build_pool_provenance("job_x", expected, ["a", "b"])
    with pytest.raises(EvaluationIntegrityError, match="pool fingerprint"):
        assert_comparable_orders({"hybrid": pool, "ltr": pool.model_copy(update={"pool_fingerprint": "0" * 64})})


def test_phase10_objects_cannot_become_evaluation_truth() -> None:
    from app.services.evaluation.integrity import reject_phase10_truth_source

    for value in ("FeedbackRecord", "SystemSignal", "BadCase", "ResolutionAction", "VERIFIED"):
        with pytest.raises(ValueError, match="evaluation truth"):
            reject_phase10_truth_source(value)


def test_test_guard_uses_fake_ids_and_requires_all_frozen_fingerprints() -> None:
    from app.services.evaluation.contracts import PHASE4_TEST_EXPOSURE_CAVEAT
    from app.services.evaluation.guard import TestSeal, validate_split_request

    seal = TestSeal(protocol="p", metrics="m", strategies="s", slices="z", report="r")
    memberships = {"fixture_test_query": "test", "fixture_dev": "dev", "fixture_test": "test"}
    test_audit = {
        "access_reason": "final",
        "protocol_git_commit": "a" * 40,
        "freeze_gate_attested": True,
        "phase4_exposure_acknowledged": True,
        "phase4_exposure_caveat": PHASE4_TEST_EXPOSURE_CAVEAT,
    }
    with pytest.raises(ValueError, match="allow-test"):
        validate_split_request("test", ["fixture_test_query"], allow_test=False, expected=seal, actual=seal, split_by_query=memberships)
    with pytest.raises(ValueError, match="fingerprint"):
        validate_split_request("test", ["fixture_test_query"], allow_test=True, expected=seal, actual=seal.model_copy(update={"metrics": "changed"}), split_by_query=memberships, **test_audit)
    with pytest.raises(ValueError, match="mixed"):
        validate_split_request("dev", ["fixture_dev", "fixture_test"], allow_test=False, expected=seal, actual=seal, split_by_query=memberships)
    with pytest.raises(ValueError, match="clean frozen"):
        validate_split_request("test", ["fixture_test_query"], allow_test=True, expected=seal, actual=seal, split_by_query=memberships, source_dirty=True, **test_audit)
