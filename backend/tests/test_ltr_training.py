from __future__ import annotations

import numpy as np


def _training_artifact() -> dict:
    from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION, MODEL_FEATURE_ORDER
    from app.services.ranking.dataset import attach_dataset_fingerprint

    def rows(split: str, jobs: list[str]) -> list[dict]:
        output = []
        for job_id in jobs:
            for index in range(12):
                grade = index // 3
                output.append(
                    {
                        "split": split,
                        "job_id": job_id,
                        "candidate_id": f"cand_{job_id[-3:]}_{index:02d}",
                        "relevance_grade": grade,
                        "feature_vector": [
                            grade / 3,
                            float(grade * 10 + index),
                            grade / 3,
                            grade / 3,
                            grade / 3,
                            0.0,
                            float(grade >= 2),
                            float(grade >= 1),
                            1 - grade / 3,
                            0.0,
                        ],
                    }
                )
        return output

    train_jobs = ["job_001", "job_002"]
    dev_jobs = ["job_015"]
    train_rows = rows("train", train_jobs)
    dev_rows = rows("dev", dev_jobs)
    return attach_dataset_fingerprint(
        {
            "schema_version": "1.0",
            "dataset_version": "1.0.0",
            "feature_version": FEATURE_VERSION,
            "feature_fingerprint": FEATURE_FINGERPRINT,
            "model_feature_order": list(MODEL_FEATURE_ORDER),
            "retrieval": {"strategy": "hybrid", "top_k": 48},
            "source_fingerprints": {"freeze": "a" * 64, "retrieval": "b" * 64},
            "splits": {
                "train": {
                    "query_ids": train_jobs,
                    "group_sizes": [12, 12],
                    "row_count": 24,
                    "label_distribution": {"0": 6, "1": 6, "2": 6, "3": 6},
                    "rows": train_rows,
                },
                "dev": {
                    "query_ids": dev_jobs,
                    "group_sizes": [12],
                    "row_count": 12,
                    "label_distribution": {"0": 3, "1": 3, "2": 3, "3": 3},
                    "rows": dev_rows,
                },
            },
        }
    )


def test_lambda_ranker_uses_frozen_objective_groups_and_parameters() -> None:
    import lightgbm

    from app.services.ranking.contract import NUM_BOOST_ROUND, TRAINING_PARAMETERS
    from app.services.ranking.trainer import train_ranker

    result = train_ranker(_training_artifact())

    assert lightgbm.__version__ == "4.6.0"
    assert TRAINING_PARAMETERS["objective"] == "lambdarank"
    assert TRAINING_PARAMETERS["label_gain"] == [0, 1, 3, 7]
    assert TRAINING_PARAMETERS["deterministic"] is True
    assert TRAINING_PARAMETERS["force_row_wise"] is True
    assert TRAINING_PARAMETERS["num_threads"] == 1
    assert result.booster.num_trees() == NUM_BOOST_ROUND
    assert result.train_groups == [12, 12]
    assert result.dev_groups == [12]


def test_training_is_finite_nonconstant_and_repeat_deterministic() -> None:
    from app.services.ranking.trainer import train_ranker

    result = train_ranker(_training_artifact())

    assert np.isfinite(result.train_predictions).all()
    assert np.isfinite(result.dev_predictions).all()
    assert np.unique(result.train_predictions).size > 1
    assert np.unique(result.dev_predictions).size > 1
    assert result.predictions_identical is True
    assert result.model_sha256 == result.repeat_model_sha256
    assert len(result.model_sha256) == 64
    assert result.model_text.startswith("tree\n")


def test_training_fails_closed_when_repeat_model_sha_differs(monkeypatch) -> None:
    import pytest

    import app.services.ranking.trainer as trainer

    class FakeBooster:
        def __init__(self, text: str) -> None:
            self.text = text

        def num_trees(self) -> int:
            return 1

        def predict(self, features):
            return np.arange(len(features), dtype=float) + 1.0

        def model_to_string(self) -> str:
            return self.text

    calls = iter((FakeBooster("tree\nfirst"), FakeBooster("tree\nsecond")))
    monkeypatch.setattr(trainer, "_train_once", lambda train, dev: next(calls))

    with pytest.raises(RuntimeError, match="native model SHA"):
        trainer.train_ranker(_training_artifact())
