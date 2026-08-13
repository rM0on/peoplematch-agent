from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Dict, Type

from pydantic import BaseModel


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.candidate import CandidateProfile  # noqa: E402
from app.schemas.job import JobProfile  # noqa: E402
from app.schemas.labels import PairwisePreference, RelevanceLabel  # noqa: E402


SCHEMA_MODELS: Dict[str, Type[BaseModel]] = {
    "candidate_profile.schema.json": CandidateProfile,
    "job_profile.schema.json": JobProfile,
    "relevance_label.schema.json": RelevanceLabel,
    "pairwise_preference.schema.json": PairwisePreference,
}


def export_schemas(output_directory: Path) -> list[Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, model in SCHEMA_MODELS.items():
        destination = output_directory / filename
        destination.write_text(
            json.dumps(
                model.model_json_schema(),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        written.append(destination)
    return written


def main() -> int:
    destinations = export_schemas(REPOSITORY_ROOT / "data" / "schemas")
    print(f"Exported {len(destinations)} deterministic JSON schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
