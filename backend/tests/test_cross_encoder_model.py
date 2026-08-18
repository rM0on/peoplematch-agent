from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "artifacts/phase7/cross_encoder_ms_marco_minilm_l6_v2"
MANIFEST = ROOT / "data/eval/phase7/cross_encoder_model_manifest_v1.json"
TEXT_CONTRACT = ROOT / "data/eval/phase7/cross_encoder_text_contract_v1.json"


def test_dependency_contract_accepts_only_torch_local_build_suffix() -> None:
    from app.services.cross_encoder.model import dependency_version_matches

    assert dependency_version_matches("torch", expected="2.8.0", actual="2.8.0")
    assert dependency_version_matches("torch", expected="2.8.0", actual="2.8.0+cpu")
    assert not dependency_version_matches(
        "torch", expected="2.8.0", actual="2.8.1+cpu"
    )
    assert not dependency_version_matches(
        "transformers", expected="4.57.6", actual="4.57.6+local"
    )


def test_missing_snapshot_fails_with_typed_unavailable_error(tmp_path: Path) -> None:
    from app.exceptions import CrossEncoderModelUnavailableError
    from app.services.cross_encoder.model import load_cross_encoder_model

    with pytest.raises(CrossEncoderModelUnavailableError):
        load_cross_encoder_model(
            model_path=tmp_path / "missing",
            manifest_path=MANIFEST,
            text_contract_path=TEXT_CONTRACT,
        )


def test_manifest_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    from app.exceptions import CrossEncoderContractMismatchError
    from app.services.cross_encoder.model import load_cross_encoder_model

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["required_files"][0]["sha256"] = "0" * 64
    bad_manifest = tmp_path / "manifest.json"
    bad_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(CrossEncoderContractMismatchError):
        load_cross_encoder_model(
            model_path=SNAPSHOT,
            manifest_path=bad_manifest,
            text_contract_path=TEXT_CONTRACT,
        )


def test_runtime_uses_local_only_identity_raw_logits_and_exact_contract() -> None:
    from app.services.cross_encoder.model import load_cross_encoder_model

    runtime = load_cross_encoder_model(
        model_path=SNAPSHOT,
        manifest_path=MANIFEST,
        text_contract_path=TEXT_CONTRACT,
    )
    assert runtime.local_files_only is True
    assert runtime.trust_remote_code is False
    assert runtime.score_type == "raw_logit"
    assert runtime.max_length == 512


def test_wrapper_score_matches_underlying_sequence_classifier_logit() -> None:
    from app.services.cross_encoder.model import load_cross_encoder_model
    from app.services.cross_encoder.text import build_pair_text
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobProfile

    job = JobProfile.model_validate(
        json.loads((ROOT / "data/samples/jobs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    )
    candidate = CandidateProfile.model_validate(
        json.loads((ROOT / "data/samples/candidates.jsonl").read_text(encoding="utf-8").splitlines()[0])
    )
    runtime = load_cross_encoder_model(
        model_path=SNAPSHOT,
        manifest_path=MANIFEST,
        text_contract_path=TEXT_CONTRACT,
    )
    pair = build_pair_text(job, candidate)
    wrapped = runtime.predict_pairs([(pair.text_a, pair.text_b)], batch_size=1)
    encoded = runtime.tokenizer(
        [pair.text_a],
        [pair.text_b],
        padding=True,
        truncation=True,
        max_length=runtime.max_length,
        return_tensors="pt",
    )
    encoded = {key: value.to(runtime.model.device) for key, value in encoded.items()}
    runtime.model.eval()
    import torch

    with torch.inference_mode():
        underlying = runtime.model(**encoded, return_dict=True).logits.detach().cpu().numpy().reshape(-1)
    np.testing.assert_allclose(wrapped, underlying, rtol=0.0, atol=1e-6)


def test_repeated_scores_are_finite_nonconstant_and_deterministic() -> None:
    from app.services.cross_encoder.model import load_cross_encoder_model

    runtime = load_cross_encoder_model(
        model_path=SNAPSHOT,
        manifest_path=MANIFEST,
        text_contract_path=TEXT_CONTRACT,
    )
    pairs = [(f"ROLE {index}", f"SKILL {index}") for index in range(3)]
    first = runtime.predict_pairs(pairs, batch_size=3)
    second = runtime.predict_pairs(pairs, batch_size=3)
    assert np.isfinite(first).all()
    assert len(set(first.tolist())) > 1
    np.testing.assert_allclose(first, second, rtol=0.0, atol=1e-6)
