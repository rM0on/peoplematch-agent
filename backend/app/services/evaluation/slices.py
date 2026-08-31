from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SLICE_REASON_CODES = {
    "direction_mismatch_v1": "DIRECTION_MISMATCH",
    "evidence_insufficient_v1": "EVIDENCE_INSUFFICIENT",
    "must_have_missing_v1": "MUST_HAVE_MISSING",
    "location_mismatch_v1": "LOCATION_MISMATCH",
    "seniority_mismatch_v1": "SENIORITY_MISMATCH",
    "project_depth_gap_v1": "PROJECT_DEPTH_GAP",
    "overclaim_label_v1": "OVERCLAIM_RISK",
}


def evaluate_predeclared_slices(
    *,
    labels: Sequence[Any],
    query_ids: Sequence[str],
    orders_by_strategy: Mapping[str, Mapping[str, Sequence[str]]],
    high_overclaim_candidate_ids: set[str],
) -> dict[str, Any]:
    query_set = set(query_ids)
    selected = [label for label in labels if label.job_id in query_set]
    members: dict[str, list[Any]] = {
        "hard_negative_v1": [label for label in selected if label.hard_negative],
        "profile_high_overclaim_v1": [label for label in selected if label.candidate_id in high_overclaim_candidate_ids],
    }
    for slice_id, code in SLICE_REASON_CODES.items():
        members[slice_id] = [
            label for label in selected
            if code in {reason.value for reason in label.mismatch_reasons}
        ]
    result: dict[str, Any] = {}
    for slice_id, items in sorted(members.items()):
        jobs = {item.job_id for item in items}
        member_pairs = {(item.job_id, item.candidate_id) for item in items}
        strategy_exposure = {}
        for strategy, orders in sorted(orders_by_strategy.items()):
            exposed = sum(
                (job_id, candidate_id) in member_pairs
                for job_id, order in orders.items()
                for candidate_id in list(order)[:5]
            )
            strategy_exposure[strategy] = {"member_top5_exposure_count": exposed}
        aggregate_allowed = len(items) >= 5 and len(jobs) >= 2
        warnings = []
        if not aggregate_allowed:
            warnings.append("SMALL_N")
        if len(jobs) < 5:
            warnings.append("DESCRIPTIVE_FEWER_THAN_5_JOBS")
        result[slice_id] = {
            "membership_rule": "frozen_phase11_registry_v1",
            "member_count": len(items),
            "job_count": len(jobs),
            "member_label_ids": sorted(item.label_id for item in items),
            "aggregate_status": "ELIGIBLE_DIAGNOSTIC" if aggregate_allowed else "SMALL_N",
            "strategy_exposure": strategy_exposure,
            "warnings": warnings,
            "metric_scope": "top_k_exposure_diagnostic_only",
        }
    return result
