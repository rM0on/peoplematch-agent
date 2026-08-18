from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_text_contract_artifact_matches_runtime_fingerprint() -> None:
    from app.services.cross_encoder.contract import (
        PAIR_ORDER,
        TEXT_CONTRACT_FINGERPRINT,
        TEXT_SCHEMA_VERSION,
        text_contract_payload,
    )

    artifact = json.loads(
        (ROOT / "data/eval/phase7/cross_encoder_text_contract_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["text_schema_version"] == TEXT_SCHEMA_VERSION
    assert artifact["pair_order"] == PAIR_ORDER == "job_then_candidate"
    assert artifact["text_contract_fingerprint"] == TEXT_CONTRACT_FINGERPRINT
    assert artifact == text_contract_payload()


def test_model_contract_binds_immutable_revision_and_raw_score_policy() -> None:
    from app.services.cross_encoder.contract import (
        MODEL_CONTRACT_VERSION,
        MODEL_ID,
        MODEL_REVISION,
        SCORE_DIRECTION,
        SCORE_TYPE,
    )

    assert MODEL_CONTRACT_VERSION == "cross_encoder_model_manifest_v1"
    assert MODEL_ID == "cross-encoder/ms-marco-MiniLM-L6-v2"
    assert len(MODEL_REVISION) == 40
    assert SCORE_TYPE == "raw_logit"
    assert SCORE_DIRECTION == "higher_is_better"
