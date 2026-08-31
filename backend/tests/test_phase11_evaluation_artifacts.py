from __future__ import annotations

import json
from pathlib import Path

import pytest


def _identity() -> dict[str, object]:
    return {
        "protocol_version": "phase11_eval_protocol_v1",
        "metric_semantics_version": "phase11_metric_semantics_v1",
        "dataset_version": "1.0.0",
        "dataset_fingerprint": "a" * 64,
        "split": "dev",
        "query_ids": ["fixture_dev"],
        "source_commit_sha": "b" * 40,
        "source_tree_fingerprint": "c" * 64,
    }


def test_completed_artifact_is_atomic_immutable_and_quality_hash_is_stable(tmp_path: Path) -> None:
    from app.services.evaluation.artifacts import ArtifactWriter, quality_result_fingerprint

    quality = {"r1": {"dense_v4": {"retrieval_recall_at_10": 0.5}}, "excluded_queries": []}
    writer = ArtifactWriter(tmp_path, "run_a", _identity())
    writer.start()
    completed = writer.complete(
        quality=quality,
        diagnostics={"latency_ms": 1.0},
        warnings=[],
        report="# Phase 11 fixture\n",
    )
    assert completed.name == "run_a"
    manifest = json.loads((completed / "manifest.json").read_text())
    assert manifest["status"] == "COMPLETED"
    assert manifest["quality_result_fingerprint"] == quality_result_fingerprint(quality)
    from app.services.match_runs.contracts import canonical_fingerprint
    assert manifest["manifest_fingerprint"] == canonical_fingerprint(
        {key: value for key, value in manifest.items() if key != "manifest_fingerprint"}
    )
    assert (completed / "per_query.json").is_file()
    assert (completed / "report.json").is_file()
    assert (completed / "report.md").is_file()
    assert quality_result_fingerprint(quality) == quality_result_fingerprint(dict(quality))
    with pytest.raises(FileExistsError):
        ArtifactWriter(tmp_path, "run_a", _identity()).start()


def test_completed_artifact_requires_the_frozen_report_layout(tmp_path: Path) -> None:
    from app.services.evaluation.artifacts import ArtifactWriter

    writer = ArtifactWriter(tmp_path, "missing_report", _identity())
    writer.start()
    with pytest.raises(ValueError, match="report.md"):
        writer.complete(
            quality={"r1": {"strategies": {}}, "excluded_queries": []},
            diagnostics={},
            warnings=[],
            report=None,
        )


def test_partial_run_cannot_complete_or_look_successful(tmp_path: Path) -> None:
    from app.services.evaluation.artifacts import ArtifactWriter

    writer = ArtifactWriter(tmp_path, "partial", _identity())
    writer.start()
    with pytest.raises(ValueError, match="required quality"):
        writer.complete(quality={}, diagnostics={}, warnings=[])
    writer.invalidate("comparison contract failed")
    payload = json.loads((tmp_path / "partial" / "manifest.json").read_text())
    assert payload["status"] == "INVALID"
    assert "quality_result_fingerprint" not in payload
    assert (tmp_path / "partial" / "failure.json").is_file()
    assert not (tmp_path / "partial" / "report.json").exists()


def test_operational_failure_is_distinct_from_invalid(tmp_path: Path) -> None:
    from app.services.evaluation.artifacts import ArtifactWriter

    writer = ArtifactWriter(tmp_path, "failed", _identity())
    writer.start()
    writer.fail("Qdrant unavailable")
    assert json.loads((tmp_path / "failed" / "manifest.json").read_text())["status"] == "FAILED"


def test_generated_report_has_clean_lines_and_one_final_newline() -> None:
    from scripts.run_offline_evaluation import _report

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

    report = _report(quality, "dev")

    assert report.endswith("\n")
    assert not report.endswith("\n\n")
    assert all(line == line.rstrip() for line in report.splitlines())
