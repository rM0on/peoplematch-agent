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

    return ExplanationGenerationPipeline(max_output_tokens=512)


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
        lambda payload, _prepared: payload["candidates"][0]["summary"].update(
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
    from app.services.explanation.generation.contracts import ExplanationPlanV1
    from app.services.explanation.generation.errors import ExplanationGroundingError

    pipeline = _pipeline()
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    payload = json.loads(response.content)
    mutate(payload, prepared)

    ExplanationPlanV1.model_validate(payload)
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
