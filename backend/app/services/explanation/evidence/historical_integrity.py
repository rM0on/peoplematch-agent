from __future__ import annotations

import math
from typing import Any, Iterable

from app.schemas.match_runs import RankingVariant
from app.services.match_runs.contracts import (
    DIAGNOSTICS_CONTRACT_VERSION,
    STEP_REFS_CONTRACT_VERSION,
    WORKFLOW_FINGERPRINT,
    WORKFLOW_VERSION,
    canonical_fingerprint,
    workflow_steps,
)


_RESULT_FINGERPRINT_FIELDS = (
    "candidate_id",
    "result_rank",
    "candidate_input_contract_version",
    "candidate_input_fingerprint",
    "retrieval_rank",
    "matched_channels",
    "dense_rank",
    "dense_score",
    "sparse_rank",
    "sparse_score",
    "fusion_score",
    "semantic_score",
    "skill_fit_score",
    "project_evidence_score",
    "role_direction_score",
    "ai_tool_score",
    "location_score",
    "seniority_score",
    "missing_penalty",
    "overclaim_penalty",
    "feature_diagnostics_contract_version",
    "feature_diagnostics",
    "ltr_rank",
    "ltr_score_raw",
    "cross_encoder_rank",
    "cross_encoder_score_raw",
)

_DIAGNOSTICS_FIELDS = {
    "contract_version",
    "availability",
    "matched_must_have_requirement_ids",
    "weak_matched_must_have_requirement_ids",
    "missing_must_have_requirement_ids",
    "matched_nice_to_have_requirement_ids",
    "evidence_supported_requirement_ids",
    "matched_capabilities",
    "matched_evidence_skills",
    "matched_ai_tools",
    "location_relation",
    "seniority_relation",
    "overclaim_level",
    "overclaim_reason_count",
    "retrieval_rank",
    "dense_rank",
    "sparse_rank",
    "fusion_score",
}
_AVAILABILITY_FIELDS = {
    "semantic_score",
    "sparse_score",
    "skill_fit_score",
    "project_evidence_score",
    "role_direction_score",
    "ai_tool_score",
    "location_score",
    "seniority_score",
    "missing_penalty",
    "overclaim_penalty",
}
_REQUIREMENT_STATUS_FIELDS = (
    "matched_must_have_requirement_ids",
    "weak_matched_must_have_requirement_ids",
    "missing_must_have_requirement_ids",
    "matched_nice_to_have_requirement_ids",
)
_REQUIREMENT_LIST_FIELDS = _REQUIREMENT_STATUS_FIELDS + (
    "evidence_supported_requirement_ids",
)
_LABEL_LIST_FIELDS = (
    "matched_capabilities",
    "matched_evidence_skills",
    "matched_ai_tools",
)


def _result_row(result: Any) -> dict[str, Any]:
    return {name: getattr(result, name) for name in _RESULT_FINGERPRINT_FIELDS}


def validate_historical_workflow(run: Any, steps: Iterable[Any]) -> list[Any]:
    """Validate the exact frozen Phase 8 workflow commitment and step sequence."""

    if getattr(run, "workflow_version", None) != WORKFLOW_VERSION:
        raise ValueError("unsupported historical workflow version")
    if getattr(run, "workflow_fingerprint", None) != WORKFLOW_FINGERPRINT:
        raise ValueError("historical workflow fingerprint does not match frozen contract")
    try:
        ranking_variant = RankingVariant(getattr(run, "ranking_variant", None))
    except ValueError as error:
        raise ValueError("unsupported historical ranking variant") from error

    persisted_steps = list(steps)
    expected_names = workflow_steps(ranking_variant)
    if len(persisted_steps) != len(expected_names):
        raise ValueError("historical workflow step coverage does not match frozen contract")
    for expected_sequence, (step, expected_name) in enumerate(
        zip(persisted_steps, expected_names),
        start=1,
    ):
        sequence = getattr(step, "sequence", None)
        if type(sequence) is not int or sequence != expected_sequence:
            raise ValueError("historical workflow sequence ordering is invalid")
        if getattr(step, "step_name", None) != expected_name:
            raise ValueError("historical workflow step name does not match frozen contract")
        if getattr(step, "status", None) != "COMPLETED":
            raise ValueError("historical workflow contains an incomplete RunStep")
        if getattr(step, "contract_version", None) != STEP_REFS_CONTRACT_VERSION:
            raise ValueError("historical workflow RunStep contract version is unsupported")
        if getattr(step, "run_id", None) != getattr(run, "run_id", None):
            raise ValueError("historical RunStep belongs to another MatchRun")
    return persisted_steps


def _validate_string_list(diagnostics: dict[str, Any], field: str) -> list[str]:
    values = diagnostics[field]
    if not isinstance(values, list) or any(
        not isinstance(value, str) for value in values
    ):
        raise ValueError("historical diagnostics payload does not match frozen contract")
    if field in _REQUIREMENT_LIST_FIELDS and len(values) != len(set(values)):
        raise ValueError(f"{field} contains a duplicate requirement reference")
    return values


def _validate_historical_diagnostics(result: Any) -> None:
    diagnostics = getattr(result, "feature_diagnostics", None)
    if not isinstance(diagnostics, dict) or set(diagnostics) != _DIAGNOSTICS_FIELDS:
        raise ValueError("historical diagnostics payload does not match frozen contract")
    outer_version = getattr(result, "feature_diagnostics_contract_version", None)
    embedded_version = diagnostics["contract_version"]
    if (
        outer_version != DIAGNOSTICS_CONTRACT_VERSION
        or embedded_version != DIAGNOSTICS_CONTRACT_VERSION
        or outer_version != embedded_version
    ):
        raise ValueError("unsupported historical diagnostics contract version")

    availability = diagnostics["availability"]
    if (
        not isinstance(availability, dict)
        or set(availability) != _AVAILABILITY_FIELDS
        or any(type(value) is not bool for value in availability.values())
    ):
        raise ValueError("historical diagnostics payload does not match frozen contract")

    requirement_statuses = {
        field: set(_validate_string_list(diagnostics, field))
        for field in _REQUIREMENT_STATUS_FIELDS
    }
    _validate_string_list(diagnostics, "evidence_supported_requirement_ids")
    for index, field in enumerate(_REQUIREMENT_STATUS_FIELDS):
        for other in _REQUIREMENT_STATUS_FIELDS[index + 1 :]:
            if requirement_statuses[field] & requirement_statuses[other]:
                raise ValueError(
                    "historical diagnostics contain contradictory requirement statuses"
                )
    for field in _LABEL_LIST_FIELDS:
        _validate_string_list(diagnostics, field)

    if not isinstance(diagnostics["location_relation"], str) or not isinstance(
        diagnostics["seniority_relation"], str
    ):
        raise ValueError("historical diagnostics payload does not match frozen contract")
    if diagnostics["overclaim_level"] is not None and not isinstance(
        diagnostics["overclaim_level"], str
    ):
        raise ValueError("historical diagnostics payload does not match frozen contract")
    reason_count = diagnostics["overclaim_reason_count"]
    if type(reason_count) is not int or reason_count < 0:
        raise ValueError("historical diagnostics payload does not match frozen contract")
    for field in ("retrieval_rank", "dense_rank", "sparse_rank"):
        value = diagnostics[field]
        if value is not None and (type(value) is not int or value < 1):
            raise ValueError("historical diagnostics payload does not match frozen contract")
    fusion_score = diagnostics["fusion_score"]
    if fusion_score is not None and (
        isinstance(fusion_score, bool)
        or not isinstance(fusion_score, (int, float))
        or not math.isfinite(fusion_score)
    ):
        raise ValueError("historical diagnostics payload does not match frozen contract")


def validate_historical_results(run: Any, results: Iterable[Any]) -> None:
    """Verify MatchResult history against the exact frozen Phase 8 commitment."""

    ordered = sorted(results, key=lambda item: item.result_rank)
    for result in ordered:
        _validate_historical_diagnostics(result)

    expected = canonical_fingerprint(
        {
            "ranking_variant": run.ranking_variant,
            "provenance": {
                "workflow_fingerprint": run.workflow_fingerprint,
                "feature_fingerprint": run.feature_fingerprint,
                "ranker_model_sha256": run.ranker_model_sha256,
                "ce": run.ce_provenance,
                "retrieval": run.retrieval_provenance,
            },
            "results": [_result_row(result) for result in ordered],
        }
    )
    if expected != run.result_fingerprint:
        raise ValueError("MatchRun result fingerprint does not match persisted history")


__all__ = ["validate_historical_results", "validate_historical_workflow"]
