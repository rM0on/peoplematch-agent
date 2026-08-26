from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[2]


def _schemas():
    return importlib.import_module("app.schemas.bad_cases")


def _taxonomy():
    return importlib.import_module("app.services.bad_cases.taxonomy")


def test_bad_case_create_requires_exactly_one_typed_source() -> None:
    schemas = _schemas()
    valid = {
        "feedback_id": "20000000-0000-0000-0000-000000000010",
        "symptom_code": "wrong_top1",
        "severity": "HIGH",
    }

    assert schemas.BadCaseCreateRequest.model_validate(valid).symptom_code == "wrong_top1"
    with pytest.raises(ValidationError):
        schemas.BadCaseCreateRequest.model_validate(
            {**valid, "system_signal_id": "30000000-0000-0000-0000-000000000010"}
        )
    with pytest.raises(ValidationError):
        schemas.BadCaseCreateRequest.model_validate(
            {"symptom_code": "wrong_top1", "severity": "HIGH"}
        )
    with pytest.raises(ValidationError):
        schemas.BadCaseCreateRequest.model_validate(
            {**valid, "symptom_code": "culture_fit"}
        )


def test_observed_symptom_taxonomy_matches_frozen_phase10a() -> None:
    schemas = _schemas()
    taxonomy = _taxonomy()
    base = {
        "feedback_id": "20000000-0000-0000-0000-000000000010",
        "severity": "HIGH",
    }

    assert (
        schemas.BadCaseCreateRequest.model_validate(
            {**base, "symptom_code": "expected_candidate_not_recalled"}
        ).symptom_code
        == "expected_candidate_not_recalled"
    )
    assert taxonomy.category_family("history_integrity_failure") == "INTEGRITY_OPERATIONS"
    with pytest.raises(ValidationError):
        schemas.BadCaseCreateRequest.model_validate(
            {**base, "symptom_code": "skill_fit_error"}
        )


def test_system_signal_source_cannot_assert_human_quality_judgment() -> None:
    schemas = _schemas()
    system = {
        "system_signal_id": "30000000-0000-0000-0000-000000000010",
        "severity": "CRITICAL",
    }

    assert (
        schemas.BadCaseCreateRequest.model_validate(
            {**system, "symptom_code": "history_integrity_failure"}
        ).symptom_code
        == "history_integrity_failure"
    )
    with pytest.raises(ValidationError):
        schemas.BadCaseCreateRequest.model_validate(
            {**system, "symptom_code": "wrong_top1"}
        )


@pytest.mark.parametrize("invalid_revision", [True, 1.0, "1", -1])
def test_bad_case_update_revision_is_strict_non_negative_integer(invalid_revision) -> None:
    schemas = _schemas()

    with pytest.raises(ValidationError):
        schemas.BadCaseUpdateRequest.model_validate(
            {
                "expected_status": "CREATED",
                "expected_revision": invalid_revision,
                "status": "REVIEWED",
                "transition_reason": "review_completed",
            }
        )


def test_bad_case_update_rejects_immutable_and_arbitrary_fields() -> None:
    schemas = _schemas()
    base = {
        "expected_status": "CREATED",
        "expected_revision": 0,
        "status": "REVIEWED",
        "transition_reason": "review_completed",
    }

    assert schemas.BadCaseUpdateRequest.model_validate(base).status == "REVIEWED"
    with pytest.raises(ValidationError):
        schemas.BadCaseUpdateRequest.model_validate({**base, "match_run_id": "forged"})
    with pytest.raises(ValidationError):
        schemas.BadCaseUpdateRequest.model_validate({**base, "metadata": {"labels": [1]}})
    with pytest.raises(ValidationError):
        schemas.BadCaseUpdateRequest.model_validate(
            {**base, "analysis": {"root_cause_type": "personality", "description": "x"}}
        )
    with pytest.raises(ValidationError):
        schemas.BadCaseUpdateRequest.model_validate(
            {**base, "verification_reference": "run:unrelated"}
        )


def test_frozen_lifecycle_rejects_reviewing_alias_and_wrong_reason() -> None:
    schemas = _schemas()

    with pytest.raises(ValidationError):
        schemas.BadCaseUpdateRequest.model_validate(
            {
                "expected_status": "CREATED",
                "expected_revision": 0,
                "status": "REVIEWING",
                "transition_reason": "review_completed",
            }
        )
    with pytest.raises(ValidationError):
        schemas.BadCaseUpdateRequest.model_validate(
            {
                "expected_status": "CREATED",
                "expected_revision": 0,
                "status": "REVIEWED",
                "transition_reason": "actions_completed",
            }
        )


def test_analysis_and_resolution_text_and_enums_are_closed() -> None:
    schemas = _schemas()

    analysis = schemas.BadCaseAnalysisCreate.model_validate(
        {
            "assessment": "supported",
            "root_cause_type": "ranking",
            "root_cause_code": "ranking_wrong_top1",
            "description": "The persisted ordering conflicts with reviewed evidence.",
            "supporting_evidence_link_id": 7,
        }
    )
    resolution = schemas.ResolutionActionCreate.model_validate(
        {
            "action_type": "ranking_change_hypothesis",
            "description": "Review the bounded ranking contract in a future change.",
            "status": "planned",
        }
    )

    assert analysis.root_cause_code == "ranking_wrong_top1"
    assert resolution.status == "planned"
    with pytest.raises(ValidationError):
        schemas.BadCaseAnalysisCreate.model_validate(
            {
                "assessment": "confirmed",
                "root_cause_type": "ranking",
                "root_cause_code": "personality_verified",
                "description": "x",
            }
        )
    with pytest.raises(ValidationError):
        schemas.ResolutionActionCreate.model_validate(
            {
                "action_type": "retrain_now",
                "description": "x",
                "status": "planned",
            }
        )
    with pytest.raises(ValidationError):
        schemas.BadCaseAnalysisCreate.model_validate(
            {
                "assessment": "supported",
                "root_cause_type": "ranking",
                "root_cause_code": "ranking_wrong_top1",
                "description": "x" * 1001,
                "supporting_evidence_link_id": 7,
            }
        )


@pytest.mark.parametrize("assessment", ["supported", "confirmed"])
def test_supported_analysis_requires_scoped_evidence_link(assessment) -> None:
    schemas = _schemas()

    with pytest.raises(ValidationError):
        schemas.BadCaseAnalysisCreate.model_validate(
            {
                "assessment": assessment,
                "root_cause_type": "retrieval",
                "root_cause_code": "retrieval_recall_miss",
                "description": "This remains a reviewed hypothesis.",
            }
        )
    suspected = schemas.BadCaseAnalysisCreate.model_validate(
        {
            "assessment": "suspected",
            "root_cause_type": "retrieval",
            "root_cause_code": "retrieval_recall_miss",
            "description": "This remains a reviewed hypothesis.",
        }
    )
    assert suspected.supporting_evidence_link_id is None


def test_taxonomy_semantics_are_closed_and_actionable() -> None:
    taxonomy = _taxonomy()

    assert taxonomy.category_family("incorrect_gap_statement") == "EXPLANATION"
    assert taxonomy.root_cause_allowed("ranking", "ranking_wrong_top1") is True
    assert taxonomy.root_cause_allowed("retrieval", "retrieval_pool_truncation") is True
    assert taxonomy.root_cause_allowed("feature", "ranking_wrong_top1") is False
    assert (
        taxonomy.action_allowed("ranking", "ranking_change_hypothesis") is True
    )
    assert taxonomy.action_allowed("ranking", "template_change_hypothesis") is False
    assert (
        taxonomy.action_allowed_for_root_cause(
            "ranking_false_positive", "constraint_policy_hypothesis"
        )
        is True
    )
    assert (
        taxonomy.action_allowed_for_root_cause(
            "ranking_wrong_top1", "constraint_policy_hypothesis"
        )
        is False
    )


@pytest.mark.parametrize(
        ("current", "target", "allowed"),
    [
        ("CREATED", "REVIEWED", True),
        ("CREATED", "ACTION_PLANNED", False),
        ("REVIEWED", "ROOT_CAUSE_IDENTIFIED", True),
        ("ROOT_CAUSE_IDENTIFIED", "ACTION_PLANNED", True),
        ("ACTION_PLANNED", "RESOLVED", True),
        ("RESOLVED", "VERIFIED", True),
        ("VERIFIED", "REVIEWED", True),
    ],
)
def test_lifecycle_transition_matrix_is_explicit(current, target, allowed) -> None:
    taxonomy = _taxonomy()

    assert taxonomy.transition_allowed(current, target) is allowed


def test_bad_case_artifact_has_exact_runtime_parity() -> None:
    schemas = _schemas()
    expected = schemas.BadCaseDetailResponse.model_json_schema()
    actual = json.loads(
        (ROOT / "data" / "contracts" / "bad_case_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert actual == expected
    object_schemas = [actual, *actual.get("$defs", {}).values()]
    for schema in object_schemas:
        if schema.get("type") == "object":
            assert schema.get("additionalProperties") is False


def test_bad_case_response_versions_and_source_types_are_closed() -> None:
    schemas = _schemas()
    now = "2026-08-26T00:00:00Z"

    valid = {
        "bad_case_id": "40000000-0000-0000-0000-000000000010",
        "case_contract_version": "bad_case_v1",
        "taxonomy_version": "bad_case_taxonomy_v1",
        "primary_match_run_id": "00000000-0000-0000-0000-000000000010",
        "historical_job_id": "job_10",
        "symptom_code": "wrong_top1",
        "symptom_family": "RANKING",
        "severity": "HIGH",
        "status": "CREATED",
        "revision": 0,
        "created_at": now,
        "updated_at": now,
        "sources": [
            {
                "source_type": "feedback",
                "feedback_id": "20000000-0000-0000-0000-000000000010",
                "created_at": now,
            }
        ],
    }

    assert schemas.BadCaseDetailResponse.model_validate(valid).status == "CREATED"
    with pytest.raises(ValidationError):
        schemas.BadCaseDetailResponse.model_validate(
            {**valid, "case_contract_version": "future_contract"}
        )
    with pytest.raises(ValidationError):
        schemas.BadCaseDetailResponse.model_validate(
            {
                **valid,
                "sources": [
                    {
                        "source_type": "provider_payload",
                        "feedback_id": "20000000-0000-0000-0000-000000000010",
                        "created_at": now,
                    }
                ],
            }
        )
    with pytest.raises(ValidationError):
        schemas.BadCaseDetailResponse.model_validate(
            {**valid, "symptom_family": "RETRIEVAL"}
        )


def test_transition_response_requires_historical_from_status() -> None:
    schemas = _schemas()
    transition = {
        "transition_id": 1,
        "from_status": "CREATED",
        "to_status": "REVIEWED",
        "reason": "review_completed",
        "origin": "manual_review",
        "previous_revision": 0,
        "new_revision": 1,
        "created_at": "2026-08-26T00:00:00Z",
    }

    assert schemas.BadCaseTransitionResponse.model_validate(transition).from_status == "CREATED"
    with pytest.raises(ValidationError):
        schemas.BadCaseTransitionResponse.model_validate(
            {**transition, "from_status": None}
        )
