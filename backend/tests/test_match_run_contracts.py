from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.match_runs import (
    CrossEncoderMatchRunRequest,
    LtrMatchRunRequest,
    MatchRunRequest,
    MatchRunStatus,
    RankingVariant,
    RunStepStatus,
)
from app.schemas.persistence import CandidateRecord, JobRecord
from app.services.match_runs.contracts import (
    CANDIDATE_INPUT_CONTRACT_VERSION,
    DIAGNOSTICS_CONTRACT_VERSION,
    RANKING_INPUT_CONTRACT_VERSION,
    WORKFLOW_FINGERPRINT,
    WORKFLOW_VERSION,
    build_candidate_input_snapshot,
    build_job_input_snapshot,
    canonical_fingerprint,
    workflow_steps,
)


ROOT = Path(__file__).resolve().parents[2]


def _record(path: str, model):
    payload = json.loads((ROOT / path).read_text(encoding="utf-8").splitlines()[0])
    payload["dataset_version"] = "1.0.0"
    return model.model_validate(payload)


def test_match_run_contract_has_only_approved_variants_and_statuses() -> None:
    assert [item.value for item in RankingVariant] == [
        "ltr",
        "cross_encoder_experiment",
    ]
    assert [item.value for item in MatchRunStatus] == [
        "RUNNING",
        "COMPLETED",
        "FAILED",
    ]
    assert [item.value for item in RunStepStatus] == [
        "RUNNING",
        "COMPLETED",
        "FAILED",
    ]


def test_workflow_contract_records_only_observable_steps() -> None:
    assert WORKFLOW_VERSION == "match_run_workflow_v1"
    assert len(WORKFLOW_FINGERPRINT) == 64
    assert workflow_steps(RankingVariant.LTR) == (
        "resolve_inputs",
        "phase6_ltr_rank",
        "persist_results",
    )
    assert workflow_steps(RankingVariant.CROSS_ENCODER_EXPERIMENT) == (
        "resolve_inputs",
        "phase6_ltr_rank",
        "phase7_cross_encoder_rerank",
        "persist_results",
    )


def test_match_run_request_is_discriminated_and_preserves_frozen_defaults() -> None:
    adapter = TypeAdapter(MatchRunRequest)
    ltr = adapter.validate_python({"job_id": "job_001"})
    assert isinstance(ltr, LtrMatchRunRequest)
    assert ltr.ranking_variant is RankingVariant.LTR
    assert (ltr.candidate_pool_k, ltr.top_k) == (20, 10)

    ce = adapter.validate_python(
        {"job_id": "job_001", "ranking_variant": "cross_encoder_experiment"}
    )
    assert isinstance(ce, CrossEncoderMatchRunRequest)
    assert (ce.retrieval_pool_k, ce.cross_encoder_pool_k, ce.top_k) == (20, 10, 5)

    with pytest.raises(ValidationError):
        adapter.validate_python({"job_id": "job_001", "ranking_variant": "newest"})
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"job_id": "job_001", "candidate_pool_k": 3, "top_k": 4}
        )


def test_privacy_hardened_snapshots_include_only_structured_history() -> None:
    candidate = _record("data/samples/candidates.jsonl", CandidateRecord)
    job = _record("data/samples/jobs.jsonl", JobRecord)
    candidate_snapshot = build_candidate_input_snapshot(candidate)
    job_snapshot = build_job_input_snapshot(job)

    assert candidate_snapshot["contract_version"] == CANDIDATE_INPUT_CONTRACT_VERSION
    assert job_snapshot["contract_version"] == RANKING_INPUT_CONTRACT_VERSION
    assert candidate_snapshot["candidate_id"] == "cand_001"
    assert job_snapshot["job_id"] == "job_001"
    assert candidate_snapshot["project_evidence"][0] == {
        "evidence_id": "ev_cand_001_01",
        "project_id": "prj_cand_001_01",
        "supports_skills": ["Agent workflow"],
        "verification_status": "available",
        "evidence_type": "workflow_trace",
    }
    assert [item["requirement_id"] for item in job_snapshot["must_have"]]
    assert [item["requirement_id"] for item in job_snapshot["nice_to_have"]]

    serialized = json.dumps(
        {"candidate": candidate_snapshot, "job": job_snapshot},
        sort_keys=True,
    ).lower()
    for forbidden in (
        "raw_text",
        "raw_jd",
        "candidate 001",
        "northstar labs",
        "github_url",
        "artifact_ref",
        "statement",
        "summary",
        "outcomes",
        "archetype",
        "dataset_version",
        "split",
        "label",
        "explanation",
    ):
        assert forbidden not in serialized


def test_canonical_fingerprint_is_order_and_float_roundtrip_stable() -> None:
    left = {
        "score": 0.30000000000000004,
        "nested": {"nullable": None, "values": [1.0, -0.0, 2]},
    }
    right = {
        "nested": {"values": [1.0, 0.0, 2], "nullable": None},
        "score": float(format(left["score"], ".17g")),
    }
    assert canonical_fingerprint(left) == canonical_fingerprint(right)
    assert canonical_fingerprint(left) == canonical_fingerprint(
        json.loads(json.dumps(left))
    )


def test_contract_names_are_versioned() -> None:
    assert RANKING_INPUT_CONTRACT_VERSION == "ranking_input_snapshot_v1"
    assert CANDIDATE_INPUT_CONTRACT_VERSION == "candidate_input_snapshot_v1"
    assert DIAGNOSTICS_CONTRACT_VERSION == "selected_feature_diagnostics_v1"


def test_tracked_phase8_contract_artifacts_are_privacy_bounded() -> None:
    workflow = json.loads(
        (ROOT / "data/contracts/match_run_workflow_v1.json").read_text(
            encoding="utf-8"
        )
    )
    snapshot = json.loads(
        (ROOT / "data/contracts/ranking_input_snapshot_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert workflow["workflow_version"] == WORKFLOW_VERSION
    assert workflow["workflow_fingerprint"] == WORKFLOW_FINGERPRINT
    allowed = json.dumps(
        {
            "job": snapshot["job_snapshot"]["allow"],
            "candidate": snapshot["candidate_snapshot"]["allow"],
        }
    ).lower()
    for forbidden in (
        "raw_text",
        "raw_jd",
        "labels",
        "split",
        "pairwise",
        "hard_negative",
        "explanation",
    ):
        assert forbidden not in allowed
    assert "explanation" in json.dumps(snapshot["excluded"]).lower()


def test_workflow_artifact_is_the_complete_recomputable_runtime_contract() -> None:
    workflow = json.loads(
        (ROOT / "data/contracts/match_run_workflow_v1.json").read_text(
            encoding="utf-8"
        )
    )
    runtime = json.loads(json.dumps(workflow))
    declared = runtime.pop("workflow_fingerprint")
    assert canonical_fingerprint(runtime) == declared
    assert runtime["required_provenance"]
    assert runtime["cross_encoder_provenance"]
