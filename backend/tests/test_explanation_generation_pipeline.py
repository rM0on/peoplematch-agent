from __future__ import annotations

import asyncio
import json
from copy import deepcopy

import pytest

from app.schemas.explanations import ExplanationOutputV1
from app.services.explanation.contracts import project_provider_evidence
from app.services.explanation.generation.mock_provider import (
    DeterministicExplanationProvider,
)
from test_explanation_evidence_engine import _run


def _pipeline():
    from app.services.explanation.generation.pipeline import ExplanationGenerationPipeline

    return ExplanationGenerationPipeline(max_output_tokens=512, protocol_version="v3")


def _historical_run():
    run = _run()
    for index, result in enumerate(run.results, start=41):
        result.id = index
    return run


def test_pipeline_prepares_only_historical_topk_and_keeps_internal_ids_off_wire() -> None:
    run = _historical_run()
    original = deepcopy(run.__dict__)

    prepared = _pipeline().prepare(run, requested_top_k=1)

    assert len(prepared.evidence_bundle.candidates) == 1
    assert len(prepared.evidence_facts.candidates) == 1
    assert prepared.provider_evidence == project_provider_evidence(
        prepared.evidence_bundle
    )
    assert prepared.effective_top_k == 1
    assert run.__dict__ == original
    wire = prepared.initial_request.system_instruction + prepared.initial_request.user_instruction
    for forbidden in (
        "candidate:1:",
        "job_requirement:",
        "workflow_fingerprint",
        "ranking_input_fingerprint",
        "result_fingerprint",
        "runtime_provenance",
        "run_001",
    ):
        assert forbidden not in wire


def test_pipeline_parses_grounds_and_renders_mock_plan_without_provider_prose() -> None:
    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=2)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )

    output = pipeline.validate_and_render(response.content, prepared)

    assert isinstance(output, ExplanationOutputV1)
    assert [item.result_rank for item in output.candidates] == [1, 2]
    assert "ref_" not in output.model_dump_json()
    assert "candidate_0001" not in output.model_dump_json()
    assert response.content not in output.model_dump_json()


def test_provider_summary_reason_selector_binds_existing_canonical_refs() -> None:
    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    summary = payload["candidates"][0]["summary"]
    summary.pop("evidence_refs", None)
    summary["match_reason_index"] = 0

    output = pipeline.validate_and_render(json.dumps(payload), prepared)

    selected = payload["candidates"][0]["match_reasons"][0]["evidence_refs"]
    assert output.candidates[0].summary.evidence_refs == sorted(
        prepared.projected.reference_map.provider_to_internal[ref]
        for ref in selected
    )


def test_provider_summary_rejects_direct_reference_copy_even_if_valid() -> None:
    from app.services.explanation.generation.errors import ExplanationPlanParseError

    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    payload["candidates"][0]["summary"]["match_reason_index"] = 0
    payload["candidates"][0]["summary"]["evidence_refs"] = (
        payload["candidates"][0]["match_reasons"][0]["evidence_refs"]
    )

    with pytest.raises(ExplanationPlanParseError):
        pipeline.validate_and_render(json.dumps(payload), prepared)


@pytest.mark.parametrize(
    ("refs", "reason_code"),
    [
        (["ref_0001", "ref_0001"], "value_error"),
        (["ref_0002", "ref_0001"], "value_error"),
        ([f"ref_{number:04d}" for number in range(1, 8)], "too_long"),
        (["claim:invalid"], "string_pattern_mismatch"),
    ],
    ids=["duplicate", "noncanonical", "more_than_six", "invalid_syntax"],
)
def test_provider_reason_refs_still_fail_closed_before_summary_binding(
    refs: list[str], reason_code: str,
) -> None:
    from app.services.explanation.generation.errors import ExplanationPlanParseError

    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    payload["candidates"][0]["match_reasons"][0]["evidence_refs"] = refs

    with pytest.raises(ExplanationPlanParseError) as rejected:
        pipeline.validate_and_render(json.dumps(payload), prepared)
    assert rejected.value.reason_code == reason_code


def test_provider_summary_reason_index_must_exist_in_selected_reasons() -> None:
    from app.services.explanation.generation.errors import ExplanationPlanParseError

    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    payload["candidates"][0]["match_reasons"] = payload["candidates"][0]["match_reasons"][:1]
    payload["candidates"][0]["summary"]["match_reason_index"] = 3

    with pytest.raises(ExplanationPlanParseError):
        pipeline.validate_and_render(json.dumps(payload), prepared)


@pytest.mark.parametrize(
    ("violation", "expected_code"),
    [
        ("missing_comparison", "candidate_comparison_required"),
        ("reason_order", "candidate_reason_order_invalid"),
        ("risk_order", "candidate_risk_order_invalid"),
        ("interview_order", "candidate_interview_order_invalid"),
        ("rewrite_order", "candidate_rewrite_order_invalid"),
        ("summary_reason", "candidate_summary_reason_index_invalid"),
    ],
)
def test_candidate_level_failures_have_distinct_safe_diagnostic_codes(
    violation: str, expected_code: str,
) -> None:
    from app.services.explanation.generation.errors import ExplanationPlanParseError

    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=2)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    candidate = payload["candidates"][1]
    assert candidate["result_rank"] == 2
    valid_ref = candidate["match_reasons"][0]["evidence_refs"][0]
    if violation == "missing_comparison":
        candidate["why_not_top1"] = None
    elif violation == "reason_order":
        reason = deepcopy(candidate["match_reasons"][0])
        candidate["match_reasons"] = [reason, deepcopy(reason)]
    elif violation == "risk_order":
        item = {
            "category": "missing_requirement",
            "template_key": "missing_requirement",
            "evidence_refs": [valid_ref],
        }
        candidate["risk_points"] = [item, deepcopy(item)]
    elif violation == "interview_order":
        item = {
            "operation": "ask_evidence_clarification",
            "evidence_refs": [valid_ref],
        }
        candidate["interview_question_operations"] = [item, deepcopy(item)]
    elif violation == "rewrite_order":
        item = {"operation": "surface_existing_skill", "evidence_refs": [valid_ref]}
        candidate["rewrite_operations"] = [item, deepcopy(item)]
    else:
        candidate["match_reasons"] = candidate["match_reasons"][:1]
        candidate["summary"]["match_reason_index"] = 3

    with pytest.raises(ExplanationPlanParseError) as rejected:
        pipeline.validate_and_render(json.dumps(payload), prepared)
    assert rejected.value.stage == "schema_validation"
    assert rejected.value.field_path == "candidates.1"
    assert rejected.value.reason_code == expected_code
    assert "ref_" not in repr(rejected.value.__dict__)


@pytest.mark.parametrize("cross_candidate", [False, True])
def test_bound_summary_does_not_rescue_unknown_or_cross_candidate_reason_refs(
    cross_candidate: bool,
) -> None:
    from app.services.explanation.generation.errors import ExplanationGroundingError

    pipeline = _pipeline()
    prepared = pipeline.prepare(
        _historical_run(), requested_top_k=2 if cross_candidate else 1,
    )
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    if cross_candidate:
        owner_id = prepared.evidence_bundle.candidates[1].candidate_id
        reference_map = prepared.projected.reference_map.provider_to_internal
        ref = next(
            provider_ref for provider_ref, internal_id in reference_map.items()
            if internal_id.startswith("candidate:") and internal_id in {
                item.evidence_id
                for item in prepared.evidence_bundle.candidates[1].skills
            }
        )
        assert owner_id != prepared.evidence_bundle.candidates[0].candidate_id
    else:
        ref = "ref_9999"
    payload["candidates"][0]["match_reasons"][0]["evidence_refs"] = [ref]

    with pytest.raises(ExplanationGroundingError):
        pipeline.validate_and_render(json.dumps(payload), prepared)


def test_pipeline_rejects_invalid_json_and_semantically_forged_plan() -> None:
    from app.services.explanation.generation.errors import (
        ExplanationGroundingError,
        ExplanationPlanParseError,
    )

    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    with pytest.raises(ExplanationPlanParseError):
        pipeline.validate_and_render("not-json RAW PRIVATE", prepared)

    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    ranking_ref = prepared.projected.payload.candidates[0].facts.ranking_context[0].evidence_refs
    payload["candidates"][0]["match_reasons"][0] = {
        "category": "skill_fit",
        "template_key": "skill_fit_recorded",
        "evidence_refs": ranking_ref,
    }
    with pytest.raises(ExplanationGroundingError):
        pipeline.validate_and_render(json.dumps(payload), prepared)


def test_pipeline_parse_failure_records_only_safe_stage_code_and_contract_path() -> None:
    from app.services.explanation.generation.errors import ExplanationPlanParseError

    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    with pytest.raises(ExplanationPlanParseError) as malformed:
        pipeline.validate_and_render("not-json PRIVATE_PROVIDER_OUTPUT", prepared)
    assert malformed.value.stage == "json_decode"
    assert malformed.value.reason_code == "json_invalid"
    assert malformed.value.field_path == "root"

    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    del payload["candidates"][0]["summary"]
    payload["PRIVATE_CANDIDATE_TEXT"] = "PRIVATE_PROVIDER_OUTPUT"
    with pytest.raises(ExplanationPlanParseError) as missing:
        pipeline.validate_and_render(json.dumps(payload), prepared)
    assert missing.value.stage == "schema_validation"
    assert missing.value.reason_code == "missing"
    assert missing.value.field_path == "candidates.0.summary"
    assert "PRIVATE" not in repr((
        missing.value.stage, missing.value.reason_code, missing.value.field_path
    ))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload, prepared: payload["candidates"][0].update(
            {
                "interview_question_operations": [
                    {
                        "operation": "ask_evidence_clarification",
                        "evidence_refs": prepared.projected.payload.candidates[0]
                        .facts.ranking_context[0]
                        .evidence_refs,
                    }
                ]
            }
        ),
        lambda payload, prepared: payload["candidates"][0].update(
            {
                "rewrite_operations": [
                    {
                        "operation": "surface_existing_skill",
                        "evidence_refs": prepared.projected.payload.candidates[0]
                        .facts.ranking_context[0]
                        .evidence_refs,
                    }
                ]
            }
        ),
        lambda payload, _prepared: payload["candidates"][0]["match_reasons"][0].update(
            {"evidence_refs": ["ref_9999"]}
        ),
        lambda payload, _prepared: payload["candidates"][0].update(
            {
                "interview_question_operations": [
                    {
                        "operation": "ask_evidence_clarification",
                        "evidence_refs": ["ref_9999"],
                    }
                ]
            }
        ),
    ],
    ids=[
        "interview_without_missing_requirement",
        "unsupported_rewrite_operation",
        "unsupported_evidence_reference",
        "hallucinated_requirement_reference",
    ],
)
def test_pipeline_rejects_schema_valid_but_ungrounded_qwen_selections(mutate) -> None:
    from app.services.explanation.generation.contracts import ProviderExplanationPlanV1
    from app.services.explanation.generation.errors import ExplanationGroundingError

    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    mutate(payload, prepared)

    ProviderExplanationPlanV1.model_validate(payload)
    with pytest.raises(ExplanationGroundingError):
        pipeline.validate_and_render(json.dumps(payload), prepared)


def test_pipeline_repair_request_is_bounded_and_never_echoes_invalid_output() -> None:
    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    private_invalid = "RAW PROVIDER OUTPUT Bearer secret"

    repair = pipeline.repair_request(
        prepared,
        error_category="invalid_output",
        prior_provider_output=private_invalid,
    )

    assert private_invalid not in repair.system_instruction
    assert private_invalid not in repair.user_instruction
    assert json.loads(repair.user_instruction)["repair"] == {
        "attempt": 2,
        "category": "schema_invalid",
        "validation_error_summary": "response_did_not_match_closed_output_contract",
        "constraints": [
            "conform_to_the_supplied_output_contract",
            "preserve_candidate_coverage_order_and_ranks",
            "do_not_add_candidate_facts",
        ],
    }


def test_pipeline_builds_only_frozen_match_explanation_models() -> None:
    from app.models.explanation_run import MatchExplanationModel

    run = _historical_run()
    pipeline = _pipeline()
    prepared = pipeline.prepare(run, requested_top_k=1)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    output = pipeline.validate_and_render(response.content, prepared)

    models = pipeline.persistence_models(
        output,
        explanation_run_id="00000000-0000-0000-0000-000000000931",
        match_run=run,
    )

    assert len(models) == 1
    assert isinstance(models[0], MatchExplanationModel)
    assert models[0].match_result_id == 41
    assert models[0].candidate_id == "candidate_001"
    serialized = json.dumps(models[0].validated_output_json, sort_keys=True)
    assert "ref_" not in serialized
    assert "provider" not in serialized
