from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[2]
COMMIT = "a" * 40
FINGERPRINT = "b" * 64
EXPOSURE_CAVEAT = "post_exposure_fixed_synthetic_sandbox_evaluation"


def _seal():
    from app.services.evaluation.guard import TestSeal

    return TestSeal(protocol="p", metrics="m", strategies="s", slices="z", report="r")


def _validate_test(**overrides):
    from app.services.evaluation.guard import validate_split_request

    seal = _seal()
    arguments = {
        "allow_test": True,
        "access_reason": "final",
        "protocol_git_commit": COMMIT,
        "freeze_gate_attested": True,
        "phase4_exposure_acknowledged": True,
        "phase4_exposure_caveat": EXPOSURE_CAVEAT,
        "prior_final_run_id": None,
        "prior_final_input_fingerprint": None,
        "expected": seal,
        "actual": seal,
        "split_by_query": {"fixture_test": "test"},
        "source_dirty": False,
    }
    arguments.update(overrides)
    return validate_split_request("test", ["fixture_test"], **arguments)


def test_test_allow_without_access_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="access reason"):
        _validate_test(access_reason=None)


def test_unknown_test_access_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="access reason"):
        _validate_test(access_reason="exploration")


def test_final_requires_protocol_commit_and_positive_freeze_attestation() -> None:
    with pytest.raises(ValueError, match="protocol Git commit"):
        _validate_test(protocol_git_commit=None)
    with pytest.raises(ValueError, match="freeze-gate"):
        _validate_test(freeze_gate_attested=False)


def test_test_requires_phase4_exposure_acknowledgement_and_caveat() -> None:
    with pytest.raises(ValueError, match="Phase 4 Test exposure"):
        _validate_test(phase4_exposure_acknowledged=False)
    with pytest.raises(ValueError, match="exposure caveat"):
        _validate_test(phase4_exposure_caveat=None)


def test_frozen_seal_fingerprint_mismatch_remains_rejected() -> None:
    with pytest.raises(ValueError, match="fingerprint"):
        _validate_test(actual=_seal().model_copy(update={"metrics": "changed"}))


def test_reproduction_requires_prior_final_reference_and_matching_input() -> None:
    from app.services.evaluation.guard import validate_reproduction_input

    with pytest.raises(ValueError, match="prior final"):
        _validate_test(access_reason="reproduction")
    audit = _validate_test(
        access_reason="reproduction",
        prior_final_run_id="formal_test_v1",
        prior_final_input_fingerprint=FINGERPRINT,
    )
    with pytest.raises(ValueError, match="input fingerprint"):
        validate_reproduction_input(audit, "c" * 64)


def test_valid_final_returns_closed_audit_provenance() -> None:
    audit = _validate_test()
    assert audit.model_dump(mode="json") == {
        "allow_test": True,
        "access_reason": "final",
        "protocol_git_commit": COMMIT,
        "freeze_gate_attested": True,
        "phase4_test_exposure_acknowledged": True,
        "phase4_test_exposure_caveat": EXPOSURE_CAVEAT,
        "prior_final_run_id": None,
        "prior_final_input_fingerprint": None,
    }


def _manifest_payload(split: str) -> dict[str, object]:
    return {
        "contract_version": "phase11_evaluation_manifest_v1",
        "evaluation_run_id": "fixture",
        "protocol_version": "phase11_eval_protocol_v1",
        "metric_semantics_version": "phase11_metric_semantics_v1",
        "dataset_version": "1.0.0",
        "dataset_fingerprint": FINGERPRINT,
        "split": split,
        "query_ids": [f"fixture_{split}"],
        "source_commit_sha": COMMIT,
        "source_tree_fingerprint": FINGERPRINT,
        "status": "RUNNING",
        "recorded_at": "2026-09-01T00:00:00+00:00",
        "started_at": "2026-09-01T00:00:00+00:00",
        "manifest_fingerprint": FINGERPRINT,
    }


def test_test_manifest_requires_closed_execution_audit() -> None:
    from app.services.evaluation.contracts import EvaluationManifestV1

    with pytest.raises(ValidationError, match="test_execution_audit"):
        EvaluationManifestV1.model_validate(_manifest_payload("test"))


def test_manifest_json_schema_requires_test_execution_audit_fields() -> None:
    schema = json.loads(
        (ROOT / "data/contracts/phase11_evaluation_manifest_v1.json").read_text(encoding="utf-8")
    )
    audit = schema["properties"]["test_execution_audit"]
    assert audit["additionalProperties"] is False
    assert set(audit["required"]) >= {
        "allow_test",
        "access_reason",
        "protocol_git_commit",
        "freeze_gate_attested",
        "phase4_test_exposure_acknowledged",
        "phase4_test_exposure_caveat",
    }
    assert schema["allOf"]


def test_dev_manifest_does_not_require_test_authorization() -> None:
    from app.services.evaluation.contracts import EvaluationManifestV1

    assert EvaluationManifestV1.model_validate(_manifest_payload("dev")).test_execution_audit is None


def test_test_report_discloses_execution_and_phase4_exposure() -> None:
    from scripts.run_offline_evaluation import _apply_split_selection_context, _report

    metric = {"mean": 0.5}
    quality = {
        "r1": {
            "strategies": {
                "dense_v4": {
                    "retrieval_recall_at_5": metric,
                    "retrieval_recall_at_10": metric,
                    "retrieval_recall_at_20": metric,
                }
            },
            "leader": {"strategy_ids": ["dense_v4"]},
        },
        "r2": {
            "strategies": {
                "ltr_ranker_v1": {
                    "judged_condensed_ndcg_at_5": metric,
                    "judged_condensed_ndcg_at_10": metric,
                    "judged_condensed_mrr_at_10": metric,
                    "explicit_pairwise_accuracy": metric,
                }
            },
            "leader": {"strategy_ids": ["ltr_ranker_v1"]},
        },
    }

    quality["r1"]["leader"] = {"strategy_ids": ["dense_v4"]}
    quality["r2"]["leader"] = {"strategy_ids": ["cross_encoder_experiment"]}
    bounded = _apply_split_selection_context(quality, "test")
    report = _report(bounded, "test", test_access_reason="final")

    assert "Formal Test: EXECUTED" in report
    assert "post-exposure fixed synthetic sandbox evaluation" in report
    assert "pristine held-out" in report
    assert "SEALED / NOT RUN" not in report
    assert "Predeclared Dev leader: sparse_bm25_v4" in report
    assert "Predeclared Dev leader: ltr_ranker_v1" in report
    assert "Observed Test ordering: dense_v4" in report
    assert "Observed Test ordering: cross_encoder_experiment" in report
    assert "leader" not in bounded["r1"]
    assert "leader" not in bounded["r2"]
