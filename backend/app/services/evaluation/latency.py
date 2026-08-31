from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Sequence


@dataclass(frozen=True)
class LatencySummary:
    count: int
    p50_ms: float
    p95_ms: float
    scope: str = "local_environment_observation_only"


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    position = (len(sorted_values) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def summarize_latency(values_ms: Sequence[float]) -> LatencySummary:
    values = sorted(float(value) for value in values_ms)
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("latency observations must be non-empty, finite, and non-negative")
    return LatencySummary(count=len(values), p50_ms=_percentile(values, 0.50), p95_ms=_percentile(values, 0.95))
