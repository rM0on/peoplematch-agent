from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict


class TestSeal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol: str
    metrics: str
    strategies: str
    slices: str
    report: str


def validate_split_request(
    split: str,
    query_ids: Sequence[str],
    *,
    allow_test: bool,
    expected: TestSeal,
    actual: TestSeal,
    split_by_query: dict[str, str],
    source_dirty: bool = False,
) -> None:
    if not query_ids:
        raise ValueError("evaluation query set is empty")
    observed = {split_by_query.get(query_id) for query_id in query_ids}
    if None in observed or observed != {split}:
        raise ValueError("mixed or unknown split query IDs")
    if split == "test":
        if not allow_test:
            raise ValueError("Test evaluation requires explicit --allow-test")
        if expected != actual:
            raise ValueError("Test seal fingerprint mismatch")
        if source_dirty:
            raise ValueError("Test evaluation requires a clean frozen source state")
