from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.candidate import CandidateProfile  # noqa: E402
from app.schemas.job import JobProfile  # noqa: E402
from app.services.features.audit import build_feature_audit  # noqa: E402


ARTIFACT = ROOT / "data" / "eval" / "phase5" / "feature_audit_v1.json"


def _records(path: Path, model):
    return [
        model.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def generated_audit():
    candidates = _records(ROOT / "data/samples/candidates.jsonl", CandidateProfile)
    jobs = _records(ROOT / "data/samples/jobs.jsonl", JobProfile)
    splits = json.loads(
        (ROOT / "data/eval/query_splits.json").read_text(encoding="utf-8")
    )["splits"]
    return build_feature_audit(
        candidates,
        jobs,
        scope_job_ids=[*splits["train"], *splits["dev"]],
        test_job_ids=splits["test"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate/check the Phase 5 audit")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    generated = generated_audit()
    if args.write:
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {ARTIFACT}")
        return 0
    current = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if current != generated:
        print("Feature audit artifact is stale")
        return 1
    print(
        f"Feature audit is current: {generated['pair_count']} pairs, "
        f"{generated['feature_fingerprint']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
