from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dataset_validation import validate_dataset  # noqa: E402


DATASET_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
CANONICAL_FILES = (
    "data/samples/candidates.jsonl",
    "data/samples/jobs.jsonl",
    "data/samples/labels.jsonl",
    "data/eval/pairwise_preferences.jsonl",
    "data/eval/query_splits.json",
)


def _sha256(relative_path: str) -> str:
    return hashlib.sha256((REPOSITORY_ROOT / relative_path).read_bytes()).hexdigest()


def build_freeze_manifest() -> Dict[str, Any]:
    report = validate_dataset(REPOSITORY_ROOT)
    split_payload = json.loads(
        (REPOSITORY_ROOT / "data" / "eval" / "query_splits.json").read_text(
            encoding="utf-8"
        )
    )
    splits = split_payload["splits"]

    return {
        "dataset_version": DATASET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "candidate_count": report.candidate_count,
        "job_count": report.job_count,
        "label_count": report.label_count,
        "pairwise_count": report.pairwise_count,
        "train_job_ids": splits["train"],
        "dev_job_ids": splits["dev"],
        "test_job_ids": splits["test"],
        "canonical_files": {
            relative_path: _sha256(relative_path)
            for relative_path in CANONICAL_FILES
        },
    }


def main() -> int:
    output_path = REPOSITORY_ROOT / "data" / "eval" / "dataset_freeze_manifest.json"
    output_path.write_text(
        json.dumps(build_freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote deterministic dataset freeze manifest to {output_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
