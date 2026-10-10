from __future__ import annotations

from copy import deepcopy
import json

import pytest

from app.services.explanation.evidence import build_evidence_facts
from app.services.explanation.evidence import EvidenceBundleBuilder
from app.services.explanation.generation.grounding import ground_explanation_plan
from app.services.explanation.generation.reference_projection import ProviderReferenceProjector
from app.services.explanation.generation.rendering import render_explanation_output
from test_explanation_generation_contracts import _bundle
from test_explanation_generation_pipeline import _historical_run


def _selection_modules():
    from app.services.explanation.generation.semantic_selection import (
        ProviderExplanationSelectionV1,
        bind_semantic_selection,
        build_semantic_option_catalog,
    )

    return ProviderExplanationSelectionV1, bind_semantic_selection, build_semantic_option_catalog


def _prepared(two_candidates: bool = False):
    _, _, build_catalog = _selection_modules()
    bundle = EvidenceBundleBuilder().build(_historical_run()) if two_candidates else _bundle()
    facts = build_evidence_facts(bundle)
    projected = ProviderReferenceProjector().project(bundle=bundle, evidence_facts=facts)
    catalog = build_catalog(bundle=bundle, evidence_facts=facts, projected=projected)
    return bundle, facts, projected, catalog


def _option(candidate, kind: str):
    return next(option for option in candidate.options if option.kind == kind)


def _valid_payload(catalog):
    return {
        "contract_version": "provider_explanation_selection_v1",
        "candidates": [
            {
                "candidate_ref": candidate.candidate_ref,
                "match_reason_handles": [_option(candidate, "reason").handle],
                "risk_handles": [],
                "interview_handles": [],
                "rewrite_handles": [],
                "summary_primary_reason_handle": _option(candidate, "reason").handle,
            }
            for candidate in catalog.candidates
        ],
    }


@pytest.mark.parametrize("two_candidates", [False, True])
def test_valid_selection_binds_to_canonical_plan_and_grounds(two_candidates: bool) -> None:
    dto, bind, _ = _selection_modules()
    bundle, facts, projected, catalog = _prepared(two_candidates)
    payload = _valid_payload(catalog)

    plan = bind(dto.model_validate(payload), catalog=catalog)
    grounded = ground_explanation_plan(
        plan, reference_map=projected.reference_map, bundle=bundle, evidence_facts=facts,
    )
    rendered = render_explanation_output(grounded, bundle=bundle, evidence_facts=facts)

    assert plan.contract_version == "explanation_plan_v1"
    assert [item.result_rank for item in plan.candidates] == list(
        range(1, len(catalog.candidates) + 1)
    )
    assert len(rendered.candidates) == len(catalog.candidates)
    for item, candidate in zip(plan.candidates, catalog.candidates):
        selected = _option(candidate, "reason")
        assert item.candidate_ref == candidate.candidate_ref
        assert item.match_reasons[0].evidence_refs == selected.value.evidence_refs
        assert item.summary.evidence_refs == selected.value.evidence_refs
        assert item.result_rank == candidate.result_rank


def test_catalog_is_deterministic_candidate_scoped_and_preserves_provenance() -> None:
    bundle, facts, projected, catalog = _prepared(two_candidates=True)
    _, _, build_catalog = _selection_modules()
    rebuilt = build_catalog(bundle=bundle, evidence_facts=facts, projected=projected)
    assert catalog == rebuilt
    all_handles = [option.handle for candidate in catalog.candidates for option in candidate.options]
    assert len(all_handles) == len(set(all_handles))
    for candidate in catalog.candidates:
        for option in candidate.options:
            assert option.candidate_ref == candidate.candidate_ref
            for ref in option.value.evidence_refs:
                assert ref in projected.reference_map.provider_to_internal
    serialized = json.dumps(catalog.provider_payload(), sort_keys=True)
    assert "candidate:1:" not in serialized
    assert "job_requirement:" not in serialized
    assert "workflow_fingerprint" not in serialized


def test_catalog_is_closed_over_only_projected_optional_rewrite_sources() -> None:
    _, _, build_catalog = _selection_modules()
    payload = _bundle().model_dump(mode="json")
    candidate = payload["candidates"][0]
    unprojected = (
        "candidate:1:skill:fedcba9876543210fedcba9876543210",
        "candidate:1:project:unrelated_project",
        "candidate:1:project_evidence:unrelated_record",
    )
    candidate["skills"].append({
        "evidence_id": unprojected[0], "name": "unrelatedstack", "category": "backend",
    })
    candidate["projects"].append({
        "evidence_id": unprojected[1], "project_id": "unrelated_project",
        "technologies": ["unrelatedstack"], "skills_demonstrated": [],
    })
    candidate["project_evidence"].append({
        "evidence_id": unprojected[2], "source_evidence_id": "unrelated_record",
        "project_id": "unrelated_project", "supports_skills": ["unrelatedstack"],
        "verification_status": "described", "evidence_type": "readme",
    })
    bundle = type(_bundle()).model_validate(payload)
    facts = build_evidence_facts(bundle)
    projected = ProviderReferenceProjector().project(bundle=bundle, evidence_facts=facts)
    assert all(ref not in projected.reference_map.internal_to_provider for ref in unprojected[:2])
    assert unprojected[2] in projected.reference_map.internal_to_provider

    catalog = build_catalog(bundle=bundle, evidence_facts=facts, projected=projected)

    assert catalog.candidates[0].options
    assert all(
        ref in projected.reference_map.provider_to_internal
        for option in catalog.candidates[0].options for ref in option.value.evidence_refs
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_handle",
        "duplicate_handle",
        "wrong_type",
        "missing_required_reason",
        "summary_not_selected",
        "duplicate_candidate",
        "missing_candidate",
        "unknown_candidate",
        "cross_candidate",
    ],
)
def test_selection_protocol_fails_closed(mutation: str) -> None:
    dto, bind, _ = _selection_modules()
    _, _, _, catalog = _prepared(two_candidates=True)
    payload = _valid_payload(catalog)
    first, second = payload["candidates"]
    if mutation == "unknown_handle":
        first["match_reason_handles"] = ["opt_9999"]
        first["summary_primary_reason_handle"] = "opt_9999"
    elif mutation == "duplicate_handle":
        first["match_reason_handles"] *= 2
    elif mutation == "wrong_type":
        first["risk_handles"] = first["match_reason_handles"][:]
    elif mutation == "missing_required_reason":
        first["match_reason_handles"] = []
    elif mutation == "summary_not_selected":
        other = next(
            option.handle for option in catalog.candidates[0].options
            if option.kind != "reason"
        )
        first["summary_primary_reason_handle"] = other
    elif mutation == "duplicate_candidate":
        second["candidate_ref"] = first["candidate_ref"]
    elif mutation == "missing_candidate":
        payload["candidates"] = [first]
    elif mutation == "unknown_candidate":
        first["candidate_ref"] = "candidate_9999"
    else:
        first["match_reason_handles"] = second["match_reason_handles"][:]
        first["summary_primary_reason_handle"] = second["summary_primary_reason_handle"]
    with pytest.raises((ValueError, TypeError)):
        bind(dto.model_validate(payload), catalog=catalog)


def test_summary_must_name_a_selected_reason_even_if_it_is_a_valid_reason() -> None:
    dto, bind, _ = _selection_modules()
    _, _, _, catalog = _prepared()
    candidate = catalog.candidates[0]
    reasons = [option for option in candidate.options if option.kind == "reason"]
    assert len(reasons) >= 2
    payload = _valid_payload(catalog)
    payload["candidates"][0]["summary_primary_reason_handle"] = reasons[1].handle
    with pytest.raises(ValueError):
        bind(dto.model_validate(payload), catalog=catalog)


@pytest.mark.parametrize("field", ["candidate_ref", "match_reason_handles"])
def test_selection_transport_does_not_trim_identity_or_handles(field: str) -> None:
    dto, _, _ = _selection_modules()
    _, _, _, catalog = _prepared()
    payload = _valid_payload(catalog)
    if field == "candidate_ref":
        payload["candidates"][0][field] += " "
    else:
        payload["candidates"][0][field][0] += " "
    with pytest.raises(ValueError):
        dto.model_validate(payload)


def test_comparison_is_fully_deterministic_and_output_order_is_canonical() -> None:
    dto, bind, _ = _selection_modules()
    _, _, projected, catalog = _prepared(two_candidates=True)
    payload = _valid_payload(catalog)
    payload["candidates"].reverse()
    plan = bind(dto.model_validate(payload), catalog=catalog)
    assert [item.candidate_ref for item in plan.candidates] == [
        candidate.candidate_ref for candidate in catalog.candidates
    ]
    assert plan.candidates[0].why_not_top1 is None
    assert plan.candidates[1].why_not_top1.evidence_refs == (
        projected.payload.candidates[1].facts.comparison.evidence_refs
    )


def test_catalog_selection_orders_reason_categories_and_rejects_incompatible_choices() -> None:
    dto, bind, _ = _selection_modules()
    _, _, _, catalog = _prepared()
    candidate = catalog.candidates[0]
    reasons = [option for option in candidate.options if option.kind == "reason"]
    assert len(reasons) >= 2
    payload = _valid_payload(catalog)
    payload["candidates"][0]["match_reason_handles"] = [
        reasons[1].handle, reasons[0].handle,
    ]
    plan = bind(dto.model_validate(payload), catalog=catalog)
    assert [item.category for item in plan.candidates[0].match_reasons] == sorted(
        [reasons[0].value.category, reasons[1].value.category],
        key=lambda value: {"skill_fit": 0, "project_evidence": 1,
                           "location": 2, "seniority": 3, "ranking_context": 4}[value],
    )
    same_category = [
        option for option in reasons if option.value.category == reasons[0].value.category
    ]
    if len(same_category) > 1:
        payload["candidates"][0]["match_reason_handles"] = [
            same_category[0].handle, same_category[1].handle,
        ]
        with pytest.raises(ValueError):
            bind(dto.model_validate(payload), catalog=catalog)


def test_provider_selection_count_limits_are_enforced_without_truncation() -> None:
    dto, _, _ = _selection_modules()
    _, _, _, catalog = _prepared()
    payload = _valid_payload(catalog)
    payload["candidates"][0]["match_reason_handles"] = ["opt_0001"] * 5
    with pytest.raises(ValueError):
        dto.model_validate(payload)


def test_selected_rewrite_option_keeps_original_grounding_policy() -> None:
    dto, bind, _ = _selection_modules()
    bundle, facts, projected, catalog = _prepared()
    candidate = catalog.candidates[0]
    rewrite = next(option for option in candidate.options if option.kind == "rewrite")
    payload = _valid_payload(catalog)
    payload["candidates"][0]["rewrite_handles"] = [rewrite.handle]
    plan = bind(dto.model_validate(payload), catalog=catalog)
    assert plan.candidates[0].rewrite_operations[0] == rewrite.value
    ground_explanation_plan(
        plan, reference_map=projected.reference_map, bundle=bundle, evidence_facts=facts,
    )


def test_active_pipeline_uses_selection_protocol_through_render_and_persistence() -> None:
    import asyncio

    from app.services.explanation.generation.mock_provider import DeterministicExplanationProvider
    from app.services.explanation.generation.pipeline import ExplanationGenerationPipeline

    historical = _historical_run()
    pipeline = ExplanationGenerationPipeline(max_output_tokens=512)
    prepared = pipeline.prepare(historical, requested_top_k=2)
    assert prepared.initial_request.output_contract_version == "provider_explanation_selection_v1"
    assert prepared.initial_request.response_schema is None
    request_payload = json.loads(prepared.initial_request.user_instruction)
    assert request_payload["option_catalog"] == prepared.catalog.provider_payload()
    assert request_payload["output_contract"]["x-contract-version"] == (
        "provider_explanation_selection_v1"
    )

    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    selection = json.loads(response.content)
    assert "result_rank" not in json.dumps(selection)
    assert "evidence_refs" not in json.dumps(selection)
    assert "why_not_top1" not in json.dumps(selection)
    rendered = pipeline.validate_and_render(response.content, prepared)
    models = pipeline.persistence_models(
        rendered, explanation_run_id="00000000-0000-0000-0000-000000000931",
        match_run=historical,
    )
    assert len(models) == 2
    assert [model.candidate_id for model in models] == [
        item.candidate_id for item in prepared.evidence_bundle.candidates
    ]


def test_active_pipeline_rejects_old_full_object_provider_output() -> None:
    from app.services.explanation.generation.errors import ExplanationPlanParseError
    from app.services.explanation.generation.pipeline import ExplanationGenerationPipeline

    pipeline = ExplanationGenerationPipeline(max_output_tokens=512)
    prepared = pipeline.prepare(_historical_run(), requested_top_k=1)
    old_payload = {
        "contract_version": "provider_explanation_plan_v1",
        "candidates": [],
    }
    with pytest.raises(ExplanationPlanParseError):
        pipeline.validate_and_render(json.dumps(old_payload), prepared)
