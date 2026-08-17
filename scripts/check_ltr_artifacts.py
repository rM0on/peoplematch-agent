from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dataset_validation import load_query_splits  # noqa: E402
from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION, MODEL_FEATURE_ORDER  # noqa: E402
from app.services.ranking.contract import LIGHTGBM_VERSION, OBJECTIVE, RANKER_VERSION  # noqa: E402
from app.services.ranking.dataset import (  # noqa: E402
    _source_provenance,
    matrix_for_split,
    validate_dataset_fingerprint,
)


DATASET = ROOT / "data/eval/phase6/ltr_dataset_v1.json"
MODEL = ROOT / "artifacts/phase6/ltr_ranker_v1.txt"
METADATA = ROOT / "data/eval/phase6/ltr_model_metadata_v1.json"
DEV_REPORT = ROOT / "data/eval/phase6/ltr_dev_report_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Phase 6 artifacts")
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="allow the ignored native model to be absent; not runtime-ready",
    )
    args = parser.parse_args()
    try:
        artifact = json.loads(DATASET.read_text(encoding="utf-8"))
        validate_dataset_fingerprint(artifact)
        if artifact.get("feature_version") != FEATURE_VERSION:
            raise ValueError("dataset feature version mismatch")
        if artifact.get("feature_fingerprint") != FEATURE_FINGERPRINT:
            raise ValueError("dataset feature fingerprint mismatch")
        if tuple(artifact.get("model_feature_order", ())) != MODEL_FEATURE_ORDER:
            raise ValueError("dataset feature order mismatch")
        if artifact.get("test_rows_included") is not False:
            raise ValueError("dataset Test-row flag is not false")

        query_splits = load_query_splits(ROOT)
        canonical_jobs = {
            split: {
                job_id for job_id, assigned_split in query_splits.items()
                if assigned_split == split
            }
            for split in ("train", "dev", "test")
        }
        for split in ("train", "dev"):
            matrix = matrix_for_split(artifact, split)
            if set(matrix.query_ids) != canonical_jobs[split]:
                raise ValueError(f"artifact {split} query IDs differ from canonical split")
            row_job_ids = {
                str(row["job_id"]) for row in artifact["splits"][split]["rows"]
            }
            if row_job_ids & canonical_jobs["test"]:
                raise ValueError("artifact contains canonical Test Job rows")
            if not row_job_ids <= canonical_jobs[split]:
                raise ValueError(f"artifact {split} contains unexpected Job rows")

        expected_sources = _source_provenance(ROOT)[1]
        if artifact.get("source_fingerprints") != expected_sources:
            raise ValueError("dataset source provenance mismatch")

        metadata = json.loads(METADATA.read_text(encoding="utf-8"))
        for key, expected in (
            ("ranker_version", RANKER_VERSION),
            ("lightgbm_version", LIGHTGBM_VERSION),
            ("objective", OBJECTIVE),
            ("feature_version", FEATURE_VERSION),
            ("feature_fingerprint", FEATURE_FINGERPRINT),
        ):
            if metadata.get(key) != expected:
                raise ValueError(f"metadata {key} mismatch")
        if metadata.get("model_feature_order") != list(MODEL_FEATURE_ORDER):
            raise ValueError("metadata feature order mismatch")
        if metadata.get("ltr_dataset_fingerprint") != artifact["ltr_dataset_fingerprint"]:
            raise ValueError("metadata dataset fingerprint mismatch")
        if metadata.get("train_job_ids") != sorted(canonical_jobs["train"]):
            raise ValueError("metadata Train Job IDs mismatch")
        if metadata.get("dev_job_ids") != sorted(canonical_jobs["dev"]):
            raise ValueError("metadata Dev Job IDs mismatch")
        if metadata.get("test_used") is not False or metadata.get("test_metrics") is not None:
            raise ValueError("metadata contains Test usage")

        if not MODEL.is_file() and not args.metadata_only:
            raise ValueError(
                "native model is missing; run scripts/train_ltr.py --write before runtime closeout"
            )
        if MODEL.is_file():
            actual_sha = hashlib.sha256(MODEL.read_bytes()).hexdigest()
            if metadata.get("model_sha256") != actual_sha:
                raise ValueError("model SHA-256 mismatch")

        report = json.loads(DEV_REPORT.read_text(encoding="utf-8"))
        if report.get("evaluation_scope") != "judged_set_reranking":
            raise ValueError("Dev report scope mismatch")
        if report.get("test_evaluated") is not False:
            raise ValueError("Dev report contains Test evaluation")
        if report.get("ltr_dataset_fingerprint") != artifact["ltr_dataset_fingerprint"]:
            raise ValueError("Dev report dataset fingerprint mismatch")
        if report.get("query_ids") != sorted(canonical_jobs["dev"]):
            raise ValueError("Dev report query IDs mismatch")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        print(f"LTR artifact check failed: {error}")
        return 1
    print("LTR artifact check PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
