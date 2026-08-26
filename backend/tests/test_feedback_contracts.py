from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError


ROOT = Path(__file__).resolve().parents[2]


def _schemas():
    return importlib.import_module("app.schemas.feedback")


def _valid_ranking_payload() -> dict:
    return {
        "feedback_type": "ranking",
        "match_run_id": "00000000-0000-0000-0000-000000000010",
        "target_type": "candidate_result",
        "subject_match_result_id": 10,
        "value": "wrong",
        "reason_code": "false_positive",
        "comment": "The recorded result needs review.",
    }


def test_feedback_create_contract_is_discriminated_and_closed() -> None:
    schemas = _schemas()
    adapter = TypeAdapter(schemas.FeedbackCreateRequest)

    parsed = adapter.validate_python(_valid_ranking_payload())

    assert type(parsed).__name__ == "RankingFeedbackCreate"
    assert parsed.feedback_type == "ranking"
    with pytest.raises(ValidationError):
        adapter.validate_python({**_valid_ranking_payload(), "metadata": {"raw_resume": "private"}})
    with pytest.raises(ValidationError):
        adapter.validate_python({**_valid_ranking_payload(), "feedback_type": "metric"})


def test_feedback_contract_module_does_not_duplicate_bad_case_taxonomy() -> None:
    contracts = importlib.import_module("app.services.feedback.contracts")

    assert contracts.FEEDBACK_CONTRACT_VERSION == "feedback_record_v1"
    assert not hasattr(contracts, "category_allowed_for_feedback")


def test_ranking_target_contract_rejects_incompatible_result_selectors() -> None:
    schemas = _schemas()
    adapter = TypeAdapter(schemas.FeedbackCreateRequest)

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                **_valid_ranking_payload(),
                "target_type": "overall_ranking",
                "subject_match_result_id": 10,
            }
        )
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                **_valid_ranking_payload(),
                "target_type": "pairwise",
                "comparison_match_result_id": 10,
            }
        )
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                **_valid_ranking_payload(),
                "target_type": "top1",
                "reason_code": "ranking_inversion",
            }
        )


def test_ranking_verdict_and_reason_are_semantically_bound() -> None:
    schemas = _schemas()
    adapter = TypeAdapter(schemas.FeedbackCreateRequest)

    correct = {
        key: value
        for key, value in _valid_ranking_payload().items()
        if key != "reason_code"
    }
    correct["value"] = "correct"
    assert adapter.validate_python(correct).value == "correct"
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {**_valid_ranking_payload(), "value": "correct"}
        )
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                **correct,
                "value": "wrong",
            }
        )


def test_false_negative_uses_bounded_expected_candidate_reference() -> None:
    schemas = _schemas()
    adapter = TypeAdapter(schemas.FeedbackCreateRequest)
    valid = {
        "feedback_type": "ranking",
        "match_run_id": "00000000-0000-0000-0000-000000000010",
        "target_type": "expected_candidate",
        "expected_candidate_reference": "expected_candidate:cand_099",
        "value": "wrong",
        "reason_code": "false_negative",
    }

    parsed = adapter.validate_python(valid)
    assert parsed.expected_candidate_reference == "expected_candidate:cand_099"
    assert parsed.subject_match_result_id is None
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {key: value for key, value in valid.items() if key != "expected_candidate_reference"}
        )
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                **_valid_ranking_payload(),
                "reason_code": "false_negative",
            }
        )
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                **valid,
                "expected_candidate_reference": "candidate:current_row",
            }
        )


def test_feedback_text_is_bounded_and_cannot_carry_arbitrary_payloads() -> None:
    schemas = _schemas()
    adapter = TypeAdapter(schemas.FeedbackCreateRequest)

    with pytest.raises(ValidationError):
        adapter.validate_python({**_valid_ranking_payload(), "comment": "x" * 501})
    with pytest.raises(ValidationError):
        adapter.validate_python({**_valid_ranking_payload(), "comment": ["RAW RESUME"]})
    with pytest.raises(ValidationError):
        adapter.validate_python({**_valid_ranking_payload(), "value": {"score": 1}})


def test_explanation_feedback_has_closed_sections_and_values() -> None:
    schemas = _schemas()
    adapter = TypeAdapter(schemas.FeedbackCreateRequest)
    valid = {
        "feedback_type": "explanation",
        "match_run_id": "00000000-0000-0000-0000-000000000010",
        "explanation_run_id": "10000000-0000-0000-0000-000000000010",
        "match_explanation_id": 11,
        "target_type": "match_reason",
        "value": "unsupported",
        "evidence_reference": "candidate:1:skill:0123456789abcdef0123456789abcdef",
    }

    assert adapter.validate_python(valid).target_type == "match_reason"
    with pytest.raises(ValidationError):
        adapter.validate_python({**valid, "target_type": "personality"})
    with pytest.raises(ValidationError):
        adapter.validate_python({**valid, "value": "hiring_probability"})


def test_profile_feedback_target_and_issue_are_semantically_bound() -> None:
    schemas = _schemas()
    adapter = TypeAdapter(schemas.FeedbackCreateRequest)
    candidate = {
        "feedback_type": "profile_data",
        "match_run_id": "00000000-0000-0000-0000-000000000010",
        "target_type": "candidate_profile",
        "subject_match_result_id": 10,
        "value": "missing_skill",
        "field_locator": "candidate.skills",
    }
    job = {
        "feedback_type": "profile_data",
        "match_run_id": "00000000-0000-0000-0000-000000000010",
        "target_type": "job_profile",
        "value": "unclear_requirement",
        "field_locator": "job.requirements",
    }

    assert adapter.validate_python(candidate).value == "missing_skill"
    assert adapter.validate_python(job).value == "unclear_requirement"
    with pytest.raises(ValidationError):
        adapter.validate_python({**candidate, "value": "unclear_requirement"})
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {**candidate, "field_locator": "candidate.seniority"}
        )
    with pytest.raises(ValidationError):
        adapter.validate_python({**job, "field_locator": "job.location"})
    with pytest.raises(ValidationError):
        adapter.validate_python({**job, "subject_match_result_id": 10})


def test_feedback_record_artifact_has_exact_runtime_parity() -> None:
    schemas = _schemas()
    expected = TypeAdapter(schemas.FeedbackRecordV1).json_schema()
    actual = json.loads(
        (ROOT / "data" / "contracts" / "feedback_record_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert actual == expected
    object_schemas = [actual, *actual.get("$defs", {}).values()]
    for schema in object_schemas:
        if schema.get("type") == "object":
            assert schema.get("additionalProperties") is False
