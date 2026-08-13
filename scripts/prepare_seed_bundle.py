from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dataset_validation import validate_dataset  # noqa: E402
from export_json_schemas import export_schemas  # noqa: E402


SEED_INPUTS = [
    "data/samples/candidates.jsonl",
    "data/samples/jobs.jsonl",
    "data/samples/labels.jsonl",
    "data/eval/pairwise_preferences.jsonl",
    "data/eval/query_splits.json",
    "data/schemas/candidate_profile.schema.json",
    "data/schemas/job_profile.schema.json",
    "data/schemas/relevance_label.schema.json",
    "data/schemas/pairwise_preference.schema.json",
]


def _file_entry(relative_path: str) -> Dict[str, Any]:
    path = REPOSITORY_ROOT / relative_path
    content = path.read_bytes()
    entry: Dict[str, Any] = {
        "path": relative_path,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }
    if path.suffix == ".jsonl":
        entry["record_count"] = sum(
            1 for line in content.decode("utf-8").splitlines() if line.strip()
        )
    return entry


def build_seed_manifest() -> Dict[str, Any]:
    report = validate_dataset(REPOSITORY_ROOT)
    export_schemas(REPOSITORY_ROOT / "data" / "schemas")
    files: List[Dict[str, Any]] = [_file_entry(path) for path in SEED_INPUTS]
    return {
        "dataset_version": "1.0.0",
        "schema_version": "1.0",
        "data_origin": "synthetic_sandbox",
        "annotation_source": "synthetic_curated",
        "database_insertion": "deferred_to_phase_2",
        "split_policy": "job_query_grouped",
        "validated_counts": {
            "candidates": report.candidate_count,
            "jobs": report.job_count,
            "labels": report.label_count,
            "pairwise_preferences": report.pairwise_count,
        },
        "files": files,
    }


def main() -> int:
    output_path = REPOSITORY_ROOT / "data" / "seed" / "manifest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_seed_manifest(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Prepared deterministic seed manifest at {output_path}. "
        "Database insertion is deferred to Phase 2."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
