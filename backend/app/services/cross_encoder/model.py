from __future__ import annotations

import hashlib
import importlib.metadata
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch

from app.exceptions import (
    CrossEncoderContractMismatchError,
    CrossEncoderModelUnavailableError,
)
from app.services.cross_encoder.contract import (
    DEFAULT_BATCH_SIZE,
    MODEL_CONTRACT_VERSION,
    MODEL_ID,
    MODEL_LICENSE,
    MODEL_REVISION,
    MODEL_TYPE,
    PAIR_ORDER,
    SCORE_DIRECTION,
    SCORE_TYPE,
    TEXT_CONTRACT_FINGERPRINT,
    TEXT_SCHEMA_VERSION,
)


REQUIRED_RUNTIME_PACKAGES = (
    "sentence-transformers",
    "transformers",
    "torch",
    "huggingface-hub",
    "tokenizers",
)


def _read_json(path: Path, *, unavailable_message: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CrossEncoderModelUnavailableError(unavailable_message) from error
    if not isinstance(payload, dict):
        raise CrossEncoderContractMismatchError("Cross-Encoder metadata must be an object")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_fingerprint(required_files: Sequence[dict[str, Any]]) -> str:
    canonical = json.dumps(
        [
            {"path": item["path"], "sha256": item["sha256"]}
            for item in required_files
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def installed_dependency_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in REQUIRED_RUNTIME_PACKAGES:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as error:
            raise CrossEncoderModelUnavailableError(
                f"Cross-Encoder dependency is unavailable: {package}"
            ) from error
    return result


def dependency_version_matches(
    package: str, *, expected: str, actual: str
) -> bool:
    if package != "torch":
        return actual == expected
    return actual.split("+", maxsplit=1)[0] == expected


def validate_static_contract(
    *, manifest: dict[str, Any], text_contract: dict[str, Any]
) -> None:
    expected = {
        "model_contract_version": MODEL_CONTRACT_VERSION,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "pair_order": PAIR_ORDER,
        "score_type": SCORE_TYPE,
        "score_direction": SCORE_DIRECTION,
        "text_schema_version": TEXT_SCHEMA_VERSION,
        "text_contract_fingerprint": TEXT_CONTRACT_FINGERPRINT,
        "trust_remote_code": False,
        "local_files_only": True,
    }
    mismatches = [
        key for key, value in expected.items() if manifest.get(key) != value
    ]
    if manifest.get("license") != MODEL_LICENSE:
        mismatches.append("license")
    if manifest.get("model_type") != MODEL_TYPE:
        mismatches.append("model_type")
    if mismatches:
        raise CrossEncoderContractMismatchError(
            "Cross-Encoder manifest contract mismatch: " + ", ".join(mismatches)
        )
    if text_contract.get("text_schema_version") != TEXT_SCHEMA_VERSION:
        raise CrossEncoderContractMismatchError("Cross-Encoder text schema mismatch")
    if text_contract.get("text_contract_fingerprint") != TEXT_CONTRACT_FINGERPRINT:
        raise CrossEncoderContractMismatchError("Cross-Encoder text fingerprint mismatch")
    if text_contract.get("pair_order") != PAIR_ORDER:
        raise CrossEncoderContractMismatchError("Cross-Encoder pair order mismatch")


def _validate_contract(
    *,
    snapshot_dir: Path,
    manifest: dict[str, Any],
    text_contract: dict[str, Any],
) -> None:
    validate_static_contract(manifest=manifest, text_contract=text_contract)

    required_files = manifest.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        raise CrossEncoderContractMismatchError("Cross-Encoder required files are missing")
    actual_entries: list[dict[str, Any]] = []
    for item in required_files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise CrossEncoderContractMismatchError("Invalid Cross-Encoder file manifest entry")
        path = snapshot_dir / item["path"]
        if not path.is_file():
            raise CrossEncoderModelUnavailableError(
                f"Cross-Encoder runtime file is unavailable: {item['path']}"
            )
        actual = file_sha256(path)
        if actual != item.get("sha256"):
            raise CrossEncoderContractMismatchError(
                f"Cross-Encoder file SHA-256 mismatch: {item['path']}"
            )
        expected_size = item.get("size_bytes")
        if expected_size is not None and path.stat().st_size != expected_size:
            raise CrossEncoderContractMismatchError(
                f"Cross-Encoder file size mismatch: {item['path']}"
            )
        actual_entries.append({"path": item["path"], "sha256": actual})
    if manifest.get("snapshot_fingerprint") != snapshot_fingerprint(actual_entries):
        raise CrossEncoderContractMismatchError("Cross-Encoder snapshot fingerprint mismatch")

    dependencies = manifest.get("dependencies")
    actual_dependencies = installed_dependency_versions()
    if not isinstance(dependencies, dict):
        raise CrossEncoderContractMismatchError("Cross-Encoder dependency metadata is missing")
    dependency_mismatches = [
        package
        for package, version in actual_dependencies.items()
        if not isinstance(dependencies.get(package), str)
        or not dependency_version_matches(
            package,
            expected=dependencies[package],
            actual=version,
        )
    ]
    if dependency_mismatches:
        raise CrossEncoderContractMismatchError(
            "Cross-Encoder dependency mismatch: " + ", ".join(dependency_mismatches)
        )

    max_length = manifest.get("max_length")
    if not isinstance(max_length, int) or max_length <= 0:
        raise CrossEncoderContractMismatchError("Cross-Encoder max_length metadata is invalid")
    config = _read_json(
        snapshot_dir / "config.json",
        unavailable_message="Cross-Encoder config is unavailable",
    )
    tokenizer_config = _read_json(
        snapshot_dir / "tokenizer_config.json",
        unavailable_message="Cross-Encoder tokenizer config is unavailable",
    )
    if config.get("architectures", [None])[0] != manifest.get("model_class"):
        raise CrossEncoderContractMismatchError("Cross-Encoder model class mismatch")
    if config.get("model_type") != manifest.get("model_type"):
        raise CrossEncoderContractMismatchError("Cross-Encoder model type mismatch")
    if tokenizer_config.get("tokenizer_class") != manifest.get("tokenizer_config_class", manifest.get("tokenizer_class")):
        raise CrossEncoderContractMismatchError("Cross-Encoder tokenizer class mismatch")
    if config.get("max_position_embeddings") != max_length:
        raise CrossEncoderContractMismatchError("Cross-Encoder model maximum length mismatch")
    if tokenizer_config.get("model_max_length") != max_length:
        raise CrossEncoderContractMismatchError("Cross-Encoder tokenizer maximum length mismatch")


@dataclass
class CrossEncoderRuntime:
    encoder: Any
    manifest: dict[str, Any]
    snapshot_path: Path
    local_files_only: bool = True
    trust_remote_code: bool = False

    @property
    def model(self) -> Any:
        return self.encoder.model

    @property
    def tokenizer(self) -> Any:
        return self.encoder.tokenizer

    @property
    def max_length(self) -> int:
        return int(self.manifest["max_length"])

    @property
    def score_type(self) -> str:
        return str(self.manifest["score_type"])

    @property
    def model_id(self) -> str:
        return str(self.manifest["model_id"])

    @property
    def revision(self) -> str:
        return str(self.manifest["revision"])

    @property
    def snapshot_fingerprint(self) -> str:
        return str(self.manifest["snapshot_fingerprint"])

    def predict_pairs(
        self, pairs: Sequence[tuple[str, str]], *, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> np.ndarray:
        if not pairs:
            return np.asarray([], dtype=float)
        try:
            values = self.encoder.predict(
                [list(pair) for pair in pairs],
                batch_size=batch_size,
                show_progress_bar=False,
                activation_fct=torch.nn.Identity(),
                apply_softmax=False,
                convert_to_numpy=True,
            )
        except Exception as error:
            raise CrossEncoderModelUnavailableError(
                "Cross-Encoder inference failed"
            ) from error
        scores = np.asarray(values, dtype=float).reshape(-1)
        if scores.shape != (len(pairs),) or not np.isfinite(scores).all():
            raise CrossEncoderContractMismatchError("Cross-Encoder returned invalid raw logits")
        return scores


def load_cross_encoder_model(
    *, model_path: Path, manifest_path: Path, text_contract_path: Path
) -> CrossEncoderRuntime:
    if not model_path.is_dir():
        raise CrossEncoderModelUnavailableError("Cross-Encoder snapshot is unavailable")
    if not manifest_path.is_file() or not text_contract_path.is_file():
        raise CrossEncoderModelUnavailableError("Cross-Encoder contract artifacts are unavailable")
    manifest = _read_json(
        manifest_path,
        unavailable_message="Cross-Encoder model manifest is unavailable",
    )
    text_contract = _read_json(
        text_contract_path,
        unavailable_message="Cross-Encoder text contract is unavailable",
    )
    _validate_contract(
        snapshot_dir=model_path,
        manifest=manifest,
        text_contract=text_contract,
    )
    try:
        from sentence_transformers import CrossEncoder

        encoder = CrossEncoder(
            str(model_path),
            max_length=int(manifest["max_length"]),
            device="cpu",
            trust_remote_code=False,
            revision=str(manifest["revision"]),
            local_files_only=True,
            default_activation_function=torch.nn.Identity(),
        )
        if encoder.model.__class__.__name__ != str(manifest.get("model_class")):
            raise CrossEncoderContractMismatchError("Cross-Encoder runtime model class mismatch")
        if encoder.tokenizer.__class__.__name__ != str(manifest.get("tokenizer_class")):
            raise CrossEncoderContractMismatchError("Cross-Encoder runtime tokenizer class mismatch")
        encoder.model.eval()
    except CrossEncoderContractMismatchError:
        raise
    except Exception as error:
        raise CrossEncoderModelUnavailableError(
            "Cross-Encoder snapshot could not be loaded"
        ) from error
    return CrossEncoderRuntime(
        encoder=encoder,
        manifest=manifest,
        snapshot_path=model_path,
    )
