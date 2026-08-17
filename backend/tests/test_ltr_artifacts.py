from __future__ import annotations

import json
from pathlib import Path


def test_model_metadata_records_best_iteration_and_no_test_metrics() -> None:
    root = Path(__file__).resolve().parents[2]
    metadata = json.loads(
        (root / "data/eval/phase6/ltr_model_metadata_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert metadata["best_iteration"] is None
    assert metadata["test_used"] is False
    assert metadata["test_metrics"] is None


def test_artifact_checker_rejects_actual_test_job_rows(tmp_path, monkeypatch) -> None:
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("check_ltr_artifacts", root / "scripts/check_ltr_artifacts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    artifact = json.loads((root / "data/eval/phase6/ltr_dataset_v1.json").read_text(encoding="utf-8"))
    artifact["splits"]["train"]["rows"][0]["job_id"] = "job_020"
    from app.services.ranking.dataset import attach_dataset_fingerprint

    paths = {
        "DATASET": tmp_path / "ltr_dataset.json",
        "METADATA": root / "data/eval/phase6/ltr_model_metadata_v1.json",
        "DEV_REPORT": root / "data/eval/phase6/ltr_dev_report_v1.json",
        "MODEL": root / "artifacts/phase6/ltr_ranker_v1.txt",
    }
    paths["DATASET"].write_text(json.dumps(attach_dataset_fingerprint(artifact)), encoding="utf-8")
    for name, value in paths.items():
        setattr(module, name, value)
    monkeypatch.setattr(sys, "argv", ["check_ltr_artifacts.py"])

    assert module.main() == 1


def test_artifact_checker_requires_model_by_default(tmp_path, monkeypatch) -> None:
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("check_ltr_artifacts", root / "scripts/check_ltr_artifacts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MODEL = tmp_path / "missing-model.txt"
    monkeypatch.setattr(sys, "argv", ["check_ltr_artifacts.py"])

    assert module.main() == 1


def test_compose_declares_explicit_read_only_ranking_mounts_and_paths() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "RANKING_MODEL_PATH: /app/artifacts/phase6/ltr_ranker_v1.txt" in compose
    assert "RANKING_MODEL_METADATA_PATH: /app/data/eval/phase6/ltr_model_metadata_v1.json" in compose
    assert "./artifacts:/app/artifacts:ro" in compose
    assert "./data/eval/phase6:/app/data/eval/phase6:ro" in compose


def test_backend_image_installs_lightgbm_openmp_runtime() -> None:
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "backend/Dockerfile").read_text(encoding="utf-8")

    assert "libgomp1" in dockerfile
