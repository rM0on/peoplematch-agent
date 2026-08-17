from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dataset_validation import load_phase6_bundle  # noqa: E402
from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION, MODEL_FEATURE_ORDER  # noqa: E402
from app.services.ranking.contract import (  # noqa: E402
    LIGHTGBM_VERSION,
    LABEL_GAIN,
    METRIC,
    NUM_BOOST_ROUND,
    OBJECTIVE,
    RANKER_VERSION,
    TRAINING_PARAMETERS,
    build_ranker_contract,
)
from app.services.ranking.dataset import matrix_for_split  # noqa: E402
from app.services.ranking.evaluation import build_dev_report  # noqa: E402
from app.services.ranking.trainer import train_ranker  # noqa: E402


DATASET = ROOT / "data/eval/phase6/ltr_dataset_v1.json"
MODEL = ROOT / "artifacts/phase6/ltr_ranker_v1.txt"
METADATA = ROOT / "data/eval/phase6/ltr_model_metadata_v1.json"
DEV_REPORT = ROOT / "data/eval/phase6/ltr_dev_report_v1.json"


def _metadata(artifact: dict, result) -> dict:
    train = matrix_for_split(artifact, "train")
    dev = matrix_for_split(artifact, "dev")
    contract = build_ranker_contract(artifact["ltr_dataset_fingerprint"])
    return {
        **contract,
        "model_format": "lightgbm_native_text",
        "metric": METRIC,
        "label_gain": list(LABEL_GAIN),
        "training_parameters": dict(TRAINING_PARAMETERS),
        "python_version": platform.python_version(),
        "train_job_ids": list(train.query_ids),
        "dev_job_ids": list(dev.query_ids),
        "train_rows": len(train.pair_ids),
        "dev_rows": len(dev.pair_ids),
        "train_group_sizes": list(train.groups),
        "dev_group_sizes": list(dev.groups),
        "train_label_distribution": artifact["splits"]["train"]["label_distribution"],
        "dev_label_distribution": artifact["splits"]["dev"]["label_distribution"],
        "retrieval_configuration_fingerprint": artifact["source_fingerprints"][
            "retrieval_configuration_fingerprint"
        ],
        "dataset_freeze_manifest_sha256": artifact["source_fingerprints"][
            "dataset_freeze_manifest_sha256"
        ],
        "model_tree_count": result.booster.num_trees(),
        "best_iteration": (
            result.booster.best_iteration if result.booster.best_iteration > 0 else None
        ),
        "num_boost_round": NUM_BOOST_ROUND,
        "model_sha256": result.model_sha256,
        "repeat_model_sha256": result.repeat_model_sha256,
        "repeat_predictions_identical": result.predictions_identical,
        "test_used": False,
        "test_metrics": None,
        "known_limitations": [
            "judged-set evaluation excludes unjudged pairs rather than treating them as negatives",
            "synthetic sandbox labels are not evidence of production hiring accuracy",
            "Phase 6 v1 supports Job-to-Candidates only",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train/check the Phase 6 LambdaMART ranker")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not DATASET.is_file():
        print(f"Missing dataset artifact: {DATASET}")
        return 1
    artifact = json.loads(DATASET.read_text(encoding="utf-8"))
    result = train_ranker(artifact)
    bundle = load_phase6_bundle(
        ROOT,
        allowed_splits=("dev",),
        pairwise_splits=("dev",),
    )
    dev_preferences = [
        preference
        for preference in bundle.pairwise_preferences
        if preference.split.value == "dev"
    ]
    report = build_dev_report(
        artifact=artifact,
        dev_scores=result.dev_predictions.tolist(),
        pairwise_preferences=dev_preferences,
    )
    metadata = _metadata(artifact, result)
    if not args.write:
        print(
            json.dumps(
                {
                    "ranker_version": RANKER_VERSION,
                    "lightgbm_version": LIGHTGBM_VERSION,
                    "objective": OBJECTIVE,
                    "model_sha256": result.model_sha256,
                    "dev_report": report["metrics"],
                },
                sort_keys=True,
            )
        )
        return 0
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    MODEL.write_bytes(result.model_text.encode("utf-8"))
    METADATA.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    DEV_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {MODEL}")
    print(f"Wrote {METADATA}")
    print(f"Wrote {DEV_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
