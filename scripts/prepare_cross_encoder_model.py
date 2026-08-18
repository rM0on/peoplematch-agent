from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.cross_encoder.contract import (  # noqa: E402
    MODEL_CONTRACT_VERSION,
    MODEL_ID,
    MODEL_LICENSE,
    MODEL_REVISION,
    MAX_LENGTH,
    PAIR_ORDER,
    SCORE_DIRECTION,
    SCORE_TYPE,
    TEXT_CONTRACT_FINGERPRINT,
    TEXT_SCHEMA_VERSION,
    text_contract_payload,
)


REQUIRED_FILES = (
    "config.json",
    "model.safetensors",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_fingerprint(files: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        [{"path": item["path"], "sha256": item["sha256"]} for item in files],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _version(package: str) -> str:
    return importlib.metadata.version(package)


def _existing_snapshot_matches_manifest(
    snapshot_path: Path, manifest_path: Path
) -> bool:
    """Verify an explicitly reused snapshot against tracked expected hashes."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(manifest, dict):
        return False
    if manifest.get("model_id") != MODEL_ID or manifest.get("revision") != MODEL_REVISION:
        return False
    required_files = manifest.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        return False
    actual_files: list[dict[str, str]] = []
    for item in required_files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            return False
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            return False
        path = snapshot_path / relative
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            return False
        if item.get("size_bytes") is not None and path.stat().st_size != item["size_bytes"]:
            return False
        actual_files.append({"path": item["path"], "sha256": item["sha256"]})
    return manifest.get("snapshot_fingerprint") == _snapshot_fingerprint(actual_files)


def prepare_snapshot(
    *,
    output_path: Path,
    manifest_path: Path,
    text_contract_path: Path,
    reuse_existing: bool = False,
) -> dict[str, Any]:
    existing_complete = output_path.is_dir() and all(
        (output_path / name).is_file() for name in REQUIRED_FILES
    )
    if existing_complete and reuse_existing:
        if not _existing_snapshot_matches_manifest(output_path, manifest_path):
            raise RuntimeError(
                "Existing Cross-Encoder snapshot does not match the tracked manifest; "
                "refusing offline reuse"
            )
        if not text_contract_path.is_file():
            raise RuntimeError(
                "Existing Cross-Encoder reuse requires the tracked text contract"
            )
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=MODEL_ID,
            revision=MODEL_REVISION,
            local_dir=str(output_path),
            local_dir_use_symlinks=False,
            allow_patterns=list(REQUIRED_FILES),
        )
    except Exception as error:
        raise RuntimeError(
            "Unable to prepare the pinned Cross-Encoder snapshot; network/download is required on a fresh setup"
        ) from error
    snapshot_path = output_path

    config = json.loads((snapshot_path / "config.json").read_text(encoding="utf-8"))
    tokenizer_config = json.loads((snapshot_path / "tokenizer_config.json").read_text(encoding="utf-8"))
    files = []
    for relative in REQUIRED_FILES:
        path = snapshot_path / relative
        if not path.is_file():
            raise RuntimeError(f"Required Cross-Encoder file is missing: {relative}")
        files.append({"path": relative, "sha256": _sha256(path), "size_bytes": path.stat().st_size})
    manifest = {
        "model_contract_version": MODEL_CONTRACT_VERSION,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "license": MODEL_LICENSE,
        "model_type": config.get("model_type"),
        "architecture": "MiniLM-L6-H384-BERT-sequence-classification",
        "model_class": config["architectures"][0],
        "tokenizer_class": "BertTokenizerFast",
        "tokenizer_config_class": tokenizer_config.get("tokenizer_class"),
        "required_files": files,
        "snapshot_fingerprint": _snapshot_fingerprint(files),
        "dependencies": {name: _version(name) for name in ("sentence-transformers", "transformers", "torch", "huggingface-hub", "tokenizers")},
        "max_length": MAX_LENGTH,
        "pair_order": PAIR_ORDER,
        "score_type": SCORE_TYPE,
        "score_direction": SCORE_DIRECTION,
        "trust_remote_code": False,
        "local_files_only": True,
        "text_schema_version": TEXT_SCHEMA_VERSION,
        "text_contract_fingerprint": TEXT_CONTRACT_FINGERPRINT,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text_contract_path.parent.mkdir(parents=True, exist_ok=True)
    text_contract_path.write_text(json.dumps(text_contract_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare the pinned Phase 7 Cross-Encoder snapshot")
    parser.add_argument("--output-path", type=Path, default=ROOT / "artifacts/phase7/cross_encoder_ms_marco_minilm_l6_v2")
    parser.add_argument("--manifest-path", type=Path, default=ROOT / "data/eval/phase7/cross_encoder_model_manifest_v1.json")
    parser.add_argument("--text-contract-path", type=Path, default=ROOT / "data/eval/phase7/cross_encoder_text_contract_v1.json")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="reuse an existing snapshot only after tracked-manifest hash verification",
    )
    args = parser.parse_args(argv)
    manifest = prepare_snapshot(
        output_path=args.output_path,
        manifest_path=args.manifest_path,
        text_contract_path=args.text_contract_path,
        reuse_existing=args.reuse_existing,
    )
    print(json.dumps({"model_id": manifest["model_id"], "revision": manifest["revision"], "snapshot_fingerprint": manifest["snapshot_fingerprint"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
