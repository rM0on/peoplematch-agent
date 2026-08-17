from __future__ import annotations

from dataclasses import dataclass
import hashlib

import lightgbm as lgb
import numpy as np

from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION, MODEL_FEATURE_ORDER
from app.services.ranking.contract import (
    LIGHTGBM_VERSION,
    NUM_BOOST_ROUND,
    TRAINING_PARAMETERS,
)
from app.services.ranking.dataset import RankingMatrix, matrix_for_split


class TrainingDegeneracyError(RuntimeError):
    """Raised when LightGBM produces no useful ranking variation."""


@dataclass(frozen=True)
class TrainingResult:
    booster: lgb.Booster
    train_predictions: np.ndarray
    dev_predictions: np.ndarray
    train_groups: list[int]
    dev_groups: list[int]
    model_text: str
    model_sha256: str
    repeat_model_sha256: str
    predictions_identical: bool


def _dataset(matrix: RankingMatrix, *, reference: lgb.Dataset | None = None) -> lgb.Dataset:
    return lgb.Dataset(
        matrix.features,
        label=matrix.labels,
        group=matrix.groups,
        feature_name=list(MODEL_FEATURE_ORDER),
        reference=reference,
        free_raw_data=False,
    )


def _train_once(train: RankingMatrix, dev: RankingMatrix) -> lgb.Booster:
    train_set = _dataset(train)
    dev_set = _dataset(dev, reference=train_set)
    return lgb.train(
        dict(TRAINING_PARAMETERS),
        train_set,
        num_boost_round=NUM_BOOST_ROUND,
        valid_sets=[dev_set],
        valid_names=["dev"],
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_non_degenerate(
    booster: lgb.Booster,
    train_predictions: np.ndarray,
    dev_predictions: np.ndarray,
) -> None:
    if booster.num_trees() <= 0:
        raise TrainingDegeneracyError("LightGBM produced no trained trees")
    if not np.isfinite(train_predictions).all() or not np.isfinite(dev_predictions).all():
        raise TrainingDegeneracyError("LightGBM produced non-finite predictions")
    if np.unique(train_predictions).size <= 1:
        raise TrainingDegeneracyError("LightGBM Train predictions are globally constant")
    if np.unique(dev_predictions).size <= 1:
        raise TrainingDegeneracyError("LightGBM Dev predictions are globally constant")


def train_ranker(artifact: dict[str, object]) -> TrainingResult:
    if lgb.__version__ != LIGHTGBM_VERSION:
        raise RuntimeError(
            f"LightGBM version {lgb.__version__} does not match {LIGHTGBM_VERSION}"
        )
    if artifact.get("feature_version") != FEATURE_VERSION:
        raise RuntimeError("LTR dataset feature version mismatch")
    if artifact.get("feature_fingerprint") != FEATURE_FINGERPRINT:
        raise RuntimeError("LTR dataset feature fingerprint mismatch")
    train = matrix_for_split(artifact, "train")
    dev = matrix_for_split(artifact, "dev")

    first = _train_once(train, dev)
    first_train = np.asarray(first.predict(train.features), dtype=float)
    first_dev = np.asarray(first.predict(dev.features), dtype=float)
    _validate_non_degenerate(first, first_train, first_dev)
    first_text = first.model_to_string()
    first_sha = _sha256_text(first_text)

    second = _train_once(train, dev)
    second_train = np.asarray(second.predict(train.features), dtype=float)
    second_dev = np.asarray(second.predict(dev.features), dtype=float)
    _validate_non_degenerate(second, second_train, second_dev)
    second_text = second.model_to_string()
    second_sha = _sha256_text(second_text)
    if first_sha != second_sha:
        raise RuntimeError("Repeat native model SHA mismatch in one environment")
    predictions_identical = bool(
        np.array_equal(first_train, second_train)
        and np.array_equal(first_dev, second_dev)
    )
    if not predictions_identical:
        raise RuntimeError("Repeat LightGBM predictions differ in one environment")

    return TrainingResult(
        booster=first,
        train_predictions=first_train,
        dev_predictions=first_dev,
        train_groups=list(train.groups),
        dev_groups=list(dev.groups),
        model_text=first_text,
        model_sha256=first_sha,
        repeat_model_sha256=second_sha,
        predictions_identical=predictions_identical,
    )
