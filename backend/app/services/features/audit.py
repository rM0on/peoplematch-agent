from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobProfile
from app.services.features.contract import (
    FEATURE_FINGERPRINT,
    FEATURE_VERSION,
    MODEL_FEATURE_ORDER,
    build_feature_contract,
)
from app.services.features.extractor import extract_pair_features


def build_feature_audit(
    candidates: Sequence[CandidateProfile],
    jobs: Sequence[JobProfile],
    *,
    scope_job_ids: Sequence[str],
    test_job_ids: Sequence[str],
) -> dict[str, Any]:
    candidate_records = sorted(candidates, key=lambda item: item.candidate_id)
    jobs_by_id = {item.job_id: item for item in jobs}
    exposed_test_jobs = sorted(set(scope_job_ids) & set(test_job_ids))
    if exposed_test_jobs:
        raise ValueError(
            f"Feature audit train/dev scope includes test Jobs: {exposed_test_jobs}"
        )
    missing_jobs = sorted(set(scope_job_ids) - set(jobs_by_id))
    if missing_jobs:
        raise ValueError(f"Audit scope references missing Jobs: {missing_jobs}")
    scope_jobs = [jobs_by_id[job_id] for job_id in sorted(set(scope_job_ids))]
    pair_count = len(candidate_records) * len(scope_jobs)
    values: dict[str, list[float]] = {name: [] for name in MODEL_FEATURE_ORDER}
    deterministic = True

    for job in scope_jobs:
        for candidate in candidate_records:
            extraction = extract_pair_features(candidate, job)
            deterministic = deterministic and extraction == extract_pair_features(
                candidate, job
            )
            for name in MODEL_FEATURE_ORDER:
                value = getattr(extraction.vector, name)
                if value is not None:
                    values[name].append(value)

    contract = build_feature_contract()
    definitions = {item["name"]: item for item in contract["features"]}
    summaries: dict[str, dict[str, Any]] = {}
    bounds_valid = True
    for name in MODEL_FEATURE_ORDER:
        available = values[name]
        definition = definitions[name]
        minimum_bound = definition["valid_range"]["minimum"]
        maximum_bound = definition["valid_range"]["maximum"]
        bounds_valid = bounds_valid and all(
            (minimum_bound is None or value >= minimum_bound)
            and (maximum_bound is None or value <= maximum_bound)
            for value in available
        )
        missing_count = pair_count - len(available)
        summaries[name] = {
            "minimum": min(available) if available else None,
            "maximum": max(available) if available else None,
            "available_count": len(available),
            "missing_count": missing_count,
            "missing_rate": round(missing_count / pair_count, 6) if pair_count else 0.0,
            "distinct_value_count": len(set(available)),
        }

    forbidden_source_terms = {
        "label",
        "relevance",
        "hard_negative",
        "pairwise",
        "split",
        "benchmark",
        "project.name",
        "project.summary",
        "evidence.statement",
        "raw_text",
        "raw_jd",
        "archetype",
    }
    source_values = {
        value.casefold()
        for source_group in contract["source_policy"].values()
        for value in source_group
    }
    source_allowlist_only = not any(
        forbidden in source for forbidden in forbidden_source_terms for source in source_values
    )
    constant_features = [
        name
        for name in MODEL_FEATURE_ORDER
        if summaries[name]["available_count"] > 0
        and summaries[name]["distinct_value_count"] <= 1
    ]
    fully_unavailable_features = [
        name for name in MODEL_FEATURE_ORDER if summaries[name]["available_count"] == 0
    ]
    return {
        "scope": "train_dev_profile_pairs_only",
        "feature_version": FEATURE_VERSION,
        "feature_fingerprint": FEATURE_FINGERPRINT,
        "candidate_count": len(candidate_records),
        "job_count": len(scope_jobs),
        "pair_count": pair_count,
        "job_ids": [item.job_id for item in scope_jobs],
        "features": summaries,
        "constant_features": constant_features,
        "fully_unavailable_features": fully_unavailable_features,
        "invariant_checks": {
            "bounds_valid": bounds_valid,
            "deterministic": deterministic,
            "json_values_finite": all(
                value == value and value not in {float("inf"), float("-inf")}
                for feature_values in values.values()
                for value in feature_values
            ),
            "model_feature_order_matches_contract": tuple(summaries)
            == MODEL_FEATURE_ORDER,
            "source_allowlist_only": source_allowlist_only,
        },
    }
