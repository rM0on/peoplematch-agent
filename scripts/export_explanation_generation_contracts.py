from __future__ import annotations

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.explanation.generation.contracts import (  # noqa: E402
    ExplanationPlanV1,
    ProviderPromptEvidenceV1,
)


def export_explanation_generation_contracts() -> list[Path]:
    contracts = (
        ("explanation_plan_v1", ExplanationPlanV1),
        ("provider_prompt_evidence_v1", ProviderPromptEvidenceV1),
    )
    written = []
    for version, model in contracts:
        destination = REPOSITORY_ROOT / "data" / "contracts" / f"{version}.json"
        schema = model.model_json_schema()
        schema["x-contract-version"] = version
        destination.write_text(
            json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(destination)
    return written


def main() -> int:
    written = export_explanation_generation_contracts()
    print(f"Exported {len(written)} explanation generation contract artifact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
