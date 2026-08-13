from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Dict


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dataset_validation import load_dataset, validate_bundle  # noqa: E402


def _ordered(counter: Counter[str]) -> Dict[str, int]:
    return dict(sorted(counter.items()))


def build_statistics() -> Dict[str, Any]:
    bundle = load_dataset(REPOSITORY_ROOT)
    report = validate_bundle(bundle)
    candidate_archetypes = Counter(
        candidate.archetype.value for candidate in bundle.candidates
    )
    job_archetypes = Counter(job.archetype.value for job in bundle.jobs)
    relevance_grades = Counter(
        str(int(label.relevance_grade)) for label in bundle.labels
    )
    mismatch_reasons = Counter(
        reason.value for label in bundle.labels for reason in label.mismatch_reasons
    )
    missing_fields = Counter(
        field for candidate in bundle.candidates for field in candidate.missing_fields
    )
    overclaim_risk = Counter(
        candidate.overclaim_risk.level.value for candidate in bundle.candidates
    )
    return {
        "dataset_version": "1.0.0",
        "schema_version": "1.0",
        "data_origin": "synthetic_sandbox",
        "candidate_count": report.candidate_count,
        "job_count": report.job_count,
        "label_count": report.label_count,
        "pairwise_count": report.pairwise_count,
        "candidate_archetype_distribution": _ordered(candidate_archetypes),
        "job_archetype_distribution": _ordered(job_archetypes),
        "relevance_grade_distribution": _ordered(relevance_grades),
        "hard_negative_count": report.hard_negative_count,
        "mismatch_reason_distribution": _ordered(mismatch_reasons),
        "split_job_counts": dict(sorted(report.split_job_counts.items())),
        "missing_field_distribution": _ordered(missing_fields),
        "overclaim_risk_distribution": _ordered(overclaim_risk),
    }


def main() -> int:
    output_path = REPOSITORY_ROOT / "data" / "eval" / "dataset_stats.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_statistics(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote descriptive dataset statistics to {output_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
