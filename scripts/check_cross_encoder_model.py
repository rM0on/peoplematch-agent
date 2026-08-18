from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.cross_encoder.model import (  # noqa: E402
    _read_json,
    _validate_contract,
    validate_static_contract,
)
from app.exceptions import (  # noqa: E402
    CrossEncoderContractMismatchError,
    CrossEncoderModelUnavailableError,
)


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    runtime_ready: bool
    message: str


def check_artifacts(
    *,
    model_path: Path,
    manifest_path: Path,
    text_contract_path: Path,
    metadata_only: bool = False,
) -> CheckResult:
    try:
        manifest = _read_json(
            manifest_path,
            unavailable_message="Cross-Encoder model manifest is unavailable",
        )
        text_contract = _read_json(
            text_contract_path,
            unavailable_message="Cross-Encoder text contract is unavailable",
        )
        if metadata_only:
            validate_static_contract(manifest=manifest, text_contract=text_contract)
            return CheckResult(
                ok=True,
                runtime_ready=False,
                message="metadata valid; runtime snapshot was not required",
            )
        if not model_path.is_dir():
            return CheckResult(False, False, "Cross-Encoder snapshot is unavailable")
        _validate_contract(
            snapshot_dir=model_path,
            manifest=manifest,
            text_contract=text_contract,
        )
        return CheckResult(True, True, "strict Cross-Encoder runtime artifacts verified")
    except (CrossEncoderModelUnavailableError, CrossEncoderContractMismatchError) as error:
        return CheckResult(False, False, str(error))


def _defaults() -> tuple[Path, Path, Path]:
    return (
        ROOT / "artifacts/phase7/cross_encoder_ms_marco_minilm_l6_v2",
        ROOT / "data/eval/phase7/cross_encoder_model_manifest_v1.json",
        ROOT / "data/eval/phase7/cross_encoder_text_contract_v1.json",
    )


def main(argv: list[str] | None = None) -> int:
    default_model, default_manifest, default_text = _defaults()
    parser = argparse.ArgumentParser(description="Verify Phase 7 Cross-Encoder artifacts")
    parser.add_argument("--model-path", type=Path, default=default_model)
    parser.add_argument("--manifest-path", type=Path, default=default_manifest)
    parser.add_argument("--text-contract-path", type=Path, default=default_text)
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="verify metadata without claiming runtime readiness",
    )
    args = parser.parse_args(argv)
    result = check_artifacts(
        model_path=args.model_path,
        manifest_path=args.manifest_path,
        text_contract_path=args.text_contract_path,
        metadata_only=args.metadata_only,
    )
    print(result.message)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
