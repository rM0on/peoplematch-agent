from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Sequence

import lightgbm as lgb
import numpy as np

from app.exceptions import RankingContractMismatchError, RankingModelUnavailableError
from app.schemas.features import FeatureVector
from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION, MODEL_FEATURE_ORDER
from app.services.ranking.contract import LIGHTGBM_VERSION, OBJECTIVE, RANKER_VERSION


def feature_vectors_to_matrix(vectors: Sequence[FeatureVector]) -> np.ndarray:
    return np.asarray(
        [
            [
                np.nan if getattr(vector, name) is None else float(getattr(vector, name))
                for name in MODEL_FEATURE_ORDER
            ]
            for vector in vectors
        ],
        dtype=float,
    ).reshape((len(vectors), len(MODEL_FEATURE_ORDER)))


@dataclass(frozen=True)
class RankingModel:
    booster: lgb.Booster
    metadata: dict[str, object]
    model_sha256: str
    ranker_version: str

    def predict(self, vectors: Sequence[FeatureVector]) -> np.ndarray:
        matrix = feature_vectors_to_matrix(vectors)
        predictions = np.asarray(self.booster.predict(matrix), dtype=float)
        if predictions.shape != (len(vectors),) or not np.isfinite(predictions).all():
            raise RankingContractMismatchError(
                "Ranking model produced invalid raw scores"
            )
        return predictions


def _metadata(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RankingModelUnavailableError(
            "Ranking model metadata is unavailable"
        ) from error
    if not isinstance(payload, dict):
        raise RankingContractMismatchError("Ranking metadata must be an object")
    return payload


def load_ranking_model(*, model_path: Path, metadata_path: Path) -> RankingModel:
    if not model_path.is_file() or not metadata_path.is_file():
        raise RankingModelUnavailableError("Ranking model artifacts are unavailable")
    metadata = _metadata(metadata_path)
    expected = {
        "ranker_version": RANKER_VERSION,
        "lightgbm_version": LIGHTGBM_VERSION,
        "objective": OBJECTIVE,
        "feature_version": FEATURE_VERSION,
        "feature_fingerprint": FEATURE_FINGERPRINT,
        "model_feature_order": list(MODEL_FEATURE_ORDER),
    }
    mismatches = [key for key, value in expected.items() if metadata.get(key) != value]
    if mismatches:
        raise RankingContractMismatchError(
            "Ranking metadata contract mismatch: " + ", ".join(mismatches)
        )
    if lgb.__version__ != LIGHTGBM_VERSION:
        raise RankingContractMismatchError("Runtime LightGBM version mismatch")
    actual_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if metadata.get("model_sha256") != actual_sha:
        raise RankingContractMismatchError("Ranking model SHA-256 mismatch")
    try:
        booster = lgb.Booster(model_file=str(model_path))
    except Exception as error:
        raise RankingModelUnavailableError("Ranking model cannot be loaded") from error
    if tuple(booster.feature_name()) != MODEL_FEATURE_ORDER:
        raise RankingContractMismatchError("Native model feature order mismatch")
    return RankingModel(
        booster=booster,
        metadata=metadata,
        model_sha256=actual_sha,
        ranker_version=RANKER_VERSION,
    )
