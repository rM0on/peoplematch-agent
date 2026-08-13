from __future__ import annotations

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dataset_validation import (  # noqa: E402
    DatasetValidationError,
    validate_dataset,
)


def main() -> int:
    try:
        report = validate_dataset(REPOSITORY_ROOT)
    except DatasetValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        "Dataset validation PASS: "
        f"{report.candidate_count} candidates, {report.job_count} jobs, "
        f"{report.label_count} relevance labels, "
        f"{report.pairwise_count} pairwise preferences, and "
        f"{report.hard_negative_count} hard negatives."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
