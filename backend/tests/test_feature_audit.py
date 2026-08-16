from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _records(path: str, model):
    return [
        model.model_validate(json.loads(line))
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_feature_audit_is_train_dev_only_label_free_and_deterministic() -> None:
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobProfile
    from app.services.features.audit import build_feature_audit

    candidates = _records("data/samples/candidates.jsonl", CandidateProfile)
    jobs = _records("data/samples/jobs.jsonl", JobProfile)
    split = json.loads(
        (ROOT / "data/eval/query_splits.json").read_text(encoding="utf-8")
    )["splits"]
    scope_ids = [*split["train"], *split["dev"]]

    first = build_feature_audit(
        candidates,
        jobs,
        scope_job_ids=scope_ids,
        test_job_ids=split["test"],
    )
    second = build_feature_audit(
        candidates,
        jobs,
        scope_job_ids=scope_ids,
        test_job_ids=split["test"],
    )

    assert first == second
    assert first["scope"] == "train_dev_profile_pairs_only"
    assert first["pair_count"] == 48 * 19 == 912
    assert first["candidate_count"] == 48
    assert first["job_count"] == 19
    assert not set(split["test"]) & set(first["job_ids"])
    serialized = json.dumps(first, allow_nan=False, sort_keys=True)
    for forbidden in (
        "relevance_grade",
        "label",
        "recall@",
        "ndcg",
        "mrr",
        "job_020",
        "job_021",
        "job_022",
        "job_023",
        "job_024",
    ):
        assert forbidden not in serialized.casefold()
    assert all(first["invariant_checks"].values())


def test_feature_audit_reports_bounds_missingness_and_constants_honestly() -> None:
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobProfile
    from app.services.features.audit import build_feature_audit
    from app.services.features.contract import MODEL_FEATURE_ORDER

    candidates = _records("data/samples/candidates.jsonl", CandidateProfile)
    jobs = _records("data/samples/jobs.jsonl", JobProfile)[:2]
    audit = build_feature_audit(
        candidates,
        jobs,
        scope_job_ids=[item.job_id for item in jobs],
        test_job_ids=["job_020", "job_021", "job_022", "job_023", "job_024"],
    )

    assert list(audit["features"]) == list(MODEL_FEATURE_ORDER)
    for summary in audit["features"].values():
        assert summary["missing_count"] + summary["available_count"] == 96
        assert 0 <= summary["missing_rate"] <= 1
        assert summary["distinct_value_count"] >= 0
    assert audit["features"]["semantic_score"]["missing_count"] == 96
    assert audit["features"]["sparse_score"]["missing_count"] == 96
    assert audit["features"]["location_score"]["minimum"] in {0.0, 1.0}
    assert audit["features"]["location_score"]["maximum"] in {0.0, 1.0}


def test_checked_in_audit_artifact_matches_generated_audit() -> None:
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobProfile
    from app.services.features.audit import build_feature_audit

    candidates = _records("data/samples/candidates.jsonl", CandidateProfile)
    jobs = _records("data/samples/jobs.jsonl", JobProfile)
    split = json.loads(
        (ROOT / "data/eval/query_splits.json").read_text(encoding="utf-8")
    )["splits"]
    generated = build_feature_audit(
        candidates,
        jobs,
        scope_job_ids=[*split["train"], *split["dev"]],
        test_job_ids=split["test"],
    )
    artifact = json.loads(
        (ROOT / "data/eval/phase5/feature_audit_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact == generated


def test_feature_audit_rejects_test_jobs_in_train_dev_scope() -> None:
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobProfile
    from app.services.features.audit import build_feature_audit

    candidates = _records("data/samples/candidates.jsonl", CandidateProfile)[:1]
    jobs = _records("data/samples/jobs.jsonl", JobProfile)

    with pytest.raises(ValueError, match="test Jobs"):
        build_feature_audit(
            candidates,
            jobs,
            scope_job_ids=["job_020"],
            test_job_ids=["job_020", "job_021", "job_022", "job_023", "job_024"],
        )
