from __future__ import annotations

from copy import deepcopy

from app.services.features.contract import (
    FEATURE_FINGERPRINT,
    FEATURE_VERSION,
    MODEL_FEATURE_ORDER,
)


RANKER_VERSION = "ltr_ranker_v1"
LIGHTGBM_VERSION = "4.6.0"
OBJECTIVE = "lambdarank"
METRIC = "ndcg"
LABEL_GAIN = (0, 1, 3, 7)
NUM_BOOST_ROUND = 100

TRAINING_PARAMETERS = {
    "boosting_type": "gbdt",
    "objective": OBJECTIVE,
    "metric": METRIC,
    "label_gain": list(LABEL_GAIN),
    "learning_rate": 0.05,
    "num_leaves": 7,
    "max_depth": 3,
    "min_data_in_leaf": 5,
    "feature_fraction": 1.0,
    "bagging_fraction": 1.0,
    "bagging_freq": 0,
    "lambda_l2": 1.0,
    "lambdarank_truncation_level": 12,
    "device_type": "cpu",
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
    "seed": 42,
    "bagging_seed": 42,
    "feature_fraction_seed": 42,
    "data_random_seed": 42,
    "verbosity": -1,
}


def build_ranker_contract(ltr_dataset_fingerprint: str) -> dict[str, object]:
    return {
        "ranker_version": RANKER_VERSION,
        "lightgbm_version": LIGHTGBM_VERSION,
        "objective": OBJECTIVE,
        "metric": METRIC,
        "label_gain": list(LABEL_GAIN),
        "num_boost_round": NUM_BOOST_ROUND,
        "feature_version": FEATURE_VERSION,
        "feature_fingerprint": FEATURE_FINGERPRINT,
        "model_feature_order": list(MODEL_FEATURE_ORDER),
        "training_parameters": deepcopy(TRAINING_PARAMETERS),
        "ltr_dataset_fingerprint": ltr_dataset_fingerprint,
    }
