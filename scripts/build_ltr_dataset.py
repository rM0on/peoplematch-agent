from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

import httpx


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dataset_validation import load_phase6_bundle  # noqa: E402
from app.schemas.features import FeatureResponseData  # noqa: E402
from app.schemas.retrieval import RetrievalRequest  # noqa: E402
from app.services.ranking.dataset import build_ltr_dataset  # noqa: E402


ARTIFACT = ROOT / "data/eval/phase6/ltr_dataset_v1.json"


class HttpFeatureService:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def features_for_job_candidates(
        self, job_id: str, request: RetrievalRequest
    ) -> FeatureResponseData:
        response = await self.client.post(
            f"/api/v1/features/jobs/{job_id}/candidates",
            json=request.model_dump(mode="json"),
        )
        response.raise_for_status()
        payload = response.json()
        return FeatureResponseData.model_validate(payload["data"])


async def generated_dataset(api_url: str) -> dict:
    async with httpx.AsyncClient(base_url=api_url, timeout=180.0) as client:
        return await build_ltr_dataset(
            feature_service=HttpFeatureService(client),
            bundle=load_phase6_bundle(
                ROOT,
                allowed_splits=("train", "dev"),
            ),
            repository_root=ROOT,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/check the Phase 6 Train/Dev LTR dataset")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    generated = asyncio.run(generated_dataset(args.api_url))
    if args.write:
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {ARTIFACT} ({generated['ltr_dataset_fingerprint']})")
        return 0
    if not ARTIFACT.is_file():
        print(f"Missing artifact: {ARTIFACT}")
        return 1
    current = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if current != generated:
        print("LTR dataset artifact is stale")
        return 1
    print(f"LTR dataset is current: {generated['ltr_dataset_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
