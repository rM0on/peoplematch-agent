from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data/eval/phase7/cross_encoder_model_manifest_v1.json"
TEXT = ROOT / "data/eval/phase7/cross_encoder_text_contract_v1.json"


def test_strict_checker_requires_snapshot(tmp_path: Path) -> None:
    from scripts.check_cross_encoder_model import check_artifacts

    result = check_artifacts(
        model_path=tmp_path / "missing",
        manifest_path=MANIFEST,
        text_contract_path=TEXT,
        metadata_only=False,
    )
    assert result.ok is False
    assert "snapshot" in result.message.lower()


def test_metadata_only_mode_is_explicit_and_never_runtime_ready(tmp_path: Path) -> None:
    from scripts.check_cross_encoder_model import check_artifacts

    result = check_artifacts(
        model_path=tmp_path / "missing",
        manifest_path=MANIFEST,
        text_contract_path=TEXT,
        metadata_only=True,
    )
    assert result.ok is True
    assert result.runtime_ready is False


def test_checker_rejects_text_contract_mismatch(tmp_path: Path) -> None:
    from scripts.check_cross_encoder_model import check_artifacts

    payload = json.loads(TEXT.read_text(encoding="utf-8"))
    payload["text_contract_fingerprint"] = "0" * 64
    bad_text = tmp_path / "bad_text.json"
    bad_text.write_text(json.dumps(payload), encoding="utf-8")
    result = check_artifacts(
        model_path=ROOT / "artifacts/phase7/cross_encoder_ms_marco_minilm_l6_v2",
        manifest_path=MANIFEST,
        text_contract_path=bad_text,
        metadata_only=True,
    )
    assert result.ok is False
    assert "text" in result.message.lower()


def test_checker_rejects_unexpected_license_and_model_type(tmp_path: Path) -> None:
    from scripts.check_cross_encoder_model import check_artifacts

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["license"] = "proprietary"
    manifest["model_type"] = "not-bert"
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    result = check_artifacts(
        model_path=ROOT / "artifacts/phase7/cross_encoder_ms_marco_minilm_l6_v2",
        manifest_path=bad_manifest,
        text_contract_path=TEXT,
        metadata_only=True,
    )
    assert result.ok is False
    assert "license" in result.message.lower()


def test_existing_snapshot_reuse_requires_expected_manifest_hashes(tmp_path: Path) -> None:
    from scripts.prepare_cross_encoder_model import _existing_snapshot_matches_manifest

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "config.json").write_text("actual", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "required_files": [
                    {"path": "config.json", "sha256": "0" * 64}
                ],
                "snapshot_fingerprint": "0" * 64,
            }
        ),
        encoding="utf-8",
    )

    assert _existing_snapshot_matches_manifest(snapshot, manifest) is False
