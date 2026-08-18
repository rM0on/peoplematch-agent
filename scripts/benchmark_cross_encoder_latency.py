from __future__ import annotations

import argparse
import json
import importlib.metadata
import platform
import time
from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402
from app.services.cross_encoder.model import load_cross_encoder_model  # noqa: E402


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _summary(values: list[float]) -> dict[str, float]:
    return {"p50_ms": _percentile(values, 50), "p95_ms": _percentile(values, 95)}


def run_benchmark(*, warmup_count: int = 5, measurement_count: int = 50, batch_size: int = 10) -> dict[str, object]:
    settings = Settings(_env_file=None)
    pair = ("ROLE TITLE: AI engineer", "SKILLS: retrieval | evaluation")
    cold = []
    for _ in range(measurement_count):
        start = time.perf_counter()
        runtime = load_cross_encoder_model(
            model_path=Path(settings.cross_encoder_model_path),
            manifest_path=Path(settings.cross_encoder_model_manifest_path),
            text_contract_path=Path(settings.cross_encoder_text_contract_path),
        )
        cold.append((time.perf_counter() - start) * 1000)
    runtime = load_cross_encoder_model(
        model_path=Path(settings.cross_encoder_model_path),
        manifest_path=Path(settings.cross_encoder_model_manifest_path),
        text_contract_path=Path(settings.cross_encoder_text_contract_path),
    )
    for _ in range(warmup_count):
        runtime.predict_pairs([pair], batch_size=1)
        runtime.predict_pairs([pair] * batch_size, batch_size=batch_size)
    single = []
    ten = []
    for _ in range(measurement_count):
        start = time.perf_counter()
        runtime.predict_pairs([pair], batch_size=1)
        single.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        runtime.predict_pairs([pair] * batch_size, batch_size=batch_size)
        ten.append((time.perf_counter() - start) * 1000)
    return {
        "title": "LOCAL SANDBOX CPU LATENCY",
        "measurement_policy": {"warmup_count": warmup_count, "measurement_count": measurement_count, "batch_size": batch_size, "max_length": runtime.max_length},
        "cold_model_load": _summary(cold),
        "warm_single_pair_scoring": _summary(single),
        "warm_ten_pair_shortlist_scoring": _summary(ten),
        "runtime": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "model_id": runtime.model_id,
            "revision": runtime.revision,
            "snapshot_fingerprint": runtime.snapshot_fingerprint,
            "dependencies": {
                package: importlib.metadata.version(package)
                for package in ("sentence-transformers", "transformers", "torch", "huggingface-hub", "tokenizers")
            },
            "torch_num_threads": torch.get_num_threads(),
        },
        "known_limitations": ["local sandbox CPU measurements only; not production latency, QPS, or capacity"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure local CPU latency for the pinned Phase 7 model")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--measurement-count", type=int, default=50)
    args = parser.parse_args(argv)
    report = run_benchmark(measurement_count=args.measurement_count)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.write:
        output = ROOT / "data/eval/phase7/cross_encoder_latency_report_v1.json"
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
