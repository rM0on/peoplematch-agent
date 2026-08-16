from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.features.contract import build_feature_contract  # noqa: E402


ARTIFACT = ROOT / "data" / "eval" / "phase5" / "feature_contract_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate/check the Phase 5 contract")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    generated = build_feature_contract()
    if args.write:
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {ARTIFACT}")
        return 0
    current = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if current != generated:
        print("Feature contract artifact is stale")
        return 1
    print(f"Feature contract is current: {generated['feature_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
