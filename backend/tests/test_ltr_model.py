from __future__ import annotations

import hashlib
import json

import pytest

from test_ltr_training import _training_artifact


def _write_model_bundle(tmp_path):
    from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION, MODEL_FEATURE_ORDER
    from app.services.ranking.contract import RANKER_VERSION
    from app.services.ranking.trainer import train_ranker

    result = train_ranker(_training_artifact())
    model_path = tmp_path / "ltr_ranker_v1.txt"
    model_path.write_bytes(result.model_text.encode("utf-8"))
    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    metadata = {
        "ranker_version": RANKER_VERSION,
        "model_format": "lightgbm_native_text",
        "lightgbm_version": "4.6.0",
        "objective": "lambdarank",
        "feature_version": FEATURE_VERSION,
        "feature_fingerprint": FEATURE_FINGERPRINT,
        "model_feature_order": list(MODEL_FEATURE_ORDER),
        "model_sha256": model_sha,
        "ltr_dataset_fingerprint": _training_artifact()["ltr_dataset_fingerprint"],
    }
    metadata_path = tmp_path / "ltr_model_metadata_v1.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return model_path, metadata_path, metadata


def test_native_model_loader_validates_contract_and_predicts(tmp_path) -> None:
    import numpy as np

    from app.schemas.features import FeatureVector
    from app.services.ranking.model import load_ranking_model

    model_path, metadata_path, metadata = _write_model_bundle(tmp_path)
    model = load_ranking_model(model_path=model_path, metadata_path=metadata_path)
    vector = FeatureVector(
        semantic_score=0.5,
        sparse_score=10.0,
        skill_fit_score=1.0,
        project_evidence_score=1.0,
        role_direction_score=0.5,
        ai_tool_score=0.0,
        location_score=1.0,
        seniority_score=1.0,
        missing_penalty=0.0,
        overclaim_penalty=None,
    )

    scores = model.predict([vector])
    assert scores.shape == (1,)
    assert np.isfinite(scores).all()
    assert model.model_sha256 == metadata["model_sha256"]
    assert model.ranker_version == "ltr_ranker_v1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("ranker_version", "stale_ranker"),
        ("feature_version", "stale_features"),
        ("feature_fingerprint", "0" * 64),
        ("model_feature_order", ["sparse_score", "semantic_score"]),
        ("model_sha256", "f" * 64),
    ],
)
def test_model_loader_rejects_stale_metadata(tmp_path, field, value) -> None:
    from app.exceptions import RankingContractMismatchError
    from app.services.ranking.model import load_ranking_model

    model_path, metadata_path, metadata = _write_model_bundle(tmp_path)
    metadata[field] = value
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(RankingContractMismatchError):
        load_ranking_model(model_path=model_path, metadata_path=metadata_path)


def test_model_loader_reports_missing_artifacts_with_typed_error(tmp_path) -> None:
    from app.exceptions import RankingModelUnavailableError
    from app.services.ranking.model import load_ranking_model

    with pytest.raises(RankingModelUnavailableError):
        load_ranking_model(
            model_path=tmp_path / "missing.txt",
            metadata_path=tmp_path / "missing.json",
        )


def test_runtime_model_settings_accept_explicit_container_paths() -> None:
    from app.core.config import Settings

    settings = Settings(
        ranking_model_path="/app/artifacts/phase6/ltr_ranker_v1.txt",
        ranking_model_metadata_path="/app/data/eval/phase6/ltr_model_metadata_v1.json",
    )

    assert settings.ranking_model_path == "/app/artifacts/phase6/ltr_ranker_v1.txt"
    assert settings.ranking_model_metadata_path == "/app/data/eval/phase6/ltr_model_metadata_v1.json"
