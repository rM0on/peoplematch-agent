from __future__ import annotations

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.schemas.explanations import ExplanationOutputV1
from app.services.explanation.contracts import (
    explanation_result_fingerprint,
    validate_explanation_output_references,
)
from app.services.explanation.evidence import build_evidence_facts
from app.services.explanation.generation.contracts import (
    ExplanationPlanV1,
    PlanInterviewQuestionOperation,
    PlanRewriteOperation,
    PlanRiskPoint,
)
from app.services.explanation.generation.reference_projection import (
    ProviderReferenceProjector,
)
from test_explanation_generation_contracts import (
    _bundle,
    _two_candidate_bundle,
    _valid_plan_payload,
)


def _grounding_modules():
    from app.services.explanation.generation.grounding import ground_explanation_plan
    from app.services.explanation.generation.rendering import render_explanation_output

    return ground_explanation_plan, render_explanation_output


def _prepared(bundle=None):
    bundle = bundle or _bundle()
    facts = build_evidence_facts(bundle)
    projected = ProviderReferenceProjector().project(
        bundle=bundle,
        evidence_facts=facts,
    )
    plan = ExplanationPlanV1.model_validate(_valid_plan_payload(projected))
    return bundle, facts, projected, plan


def _missing_requirement_bundle():
    payload = _bundle().model_dump(mode="json")
    for fact in payload["candidates"][0]["facts"]:
        if fact["name"] == "matched_must_have_requirement_ids":
            fact["value"] = []
    payload["candidates"][0]["facts"].append(
        {
            "evidence_id": "diagnostic:1:missing_must_have_requirement_ids",
            "kind": "diagnostic",
            "candidate_id": "candidate_001",
            "name": "missing_must_have_requirement_ids",
            "value": ["job_requirement:req_python"],
        }
    )
    return type(_bundle()).model_validate(payload)


def _unrelated_skill_project_bundle():
    payload = _bundle().model_dump(mode="json")
    payload["candidates"][0]["skills"].append(
        {
            "evidence_id": "candidate:1:skill:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "name": "rust",
            "category": "backend",
        }
    )
    for fact in payload["candidates"][0]["facts"]:
        if fact["name"] in {"matched_capabilities", "matched_evidence_skills"}:
            fact["value"] = ["python", "rust"]
    return type(_bundle()).model_validate(payload)


def _many_comparison_bundle():
    payload = _two_candidate_bundle().model_dump(mode="json")
    existing = {
        fact["name"]
        for fact in payload["candidates"][1]["facts"]
        if fact["kind"] == "comparison"
    }
    for name, value in (
        ("project_evidence_score", 0.4),
        ("role_direction_score", 0.3),
        ("ai_tool_score", 0.2),
        ("location_score", 0.1),
        ("seniority_score", 0.6),
        ("ltr_rank", 2),
    ):
        if name in existing:
            continue
        payload["candidates"][1]["facts"].append(
            {
                "evidence_id": f"comparison:2:top1:{name}",
                "kind": "comparison",
                "candidate_id": "candidate_002",
                "name": name,
                "value": value,
                "comparison_candidate_id": "candidate_001",
            }
        )
    return type(_bundle()).model_validate(payload)


def _maximum_cardinality_bundle():
    payload = _bundle().model_dump(mode="json")
    requirements = payload["job"]["requirements"]
    for index in range(1, 4):
        requirements.append(
            {
                "evidence_id": f"job_requirement:req_gap_{index}",
                "requirement_id": f"req_gap_{index}",
                "priority": "must_have",
                "category": "skill",
                "text": f"Private historical gap requirement {index}",
                "evidence_expectation": "Private historical evidence expectation",
            }
        )
    requirements.sort(key=lambda item: item["requirement_id"])

    candidate = payload["candidates"][0]
    candidate["overclaim_risk"] = {"level": "high", "reason_count": 1}
    candidate["facts"].extend(
        [
            {
                "evidence_id": "diagnostic:1:location_relation",
                "kind": "diagnostic",
                "candidate_id": "candidate_001",
                "name": "location_relation",
                "value": "exact_match",
            },
            {
                "evidence_id": "diagnostic:1:seniority_relation",
                "kind": "diagnostic",
                "candidate_id": "candidate_001",
                "name": "seniority_relation",
                "value": "exact_match",
            },
            {
                "evidence_id": "diagnostic:1:missing_must_have_requirement_ids",
                "kind": "diagnostic",
                "candidate_id": "candidate_001",
                "name": "missing_must_have_requirement_ids",
                "value": [
                    "job_requirement:req_gap_1",
                    "job_requirement:req_gap_2",
                    "job_requirement:req_gap_3",
                ],
            },
            {
                "evidence_id": "diagnostic:1:overclaim_level",
                "kind": "diagnostic",
                "candidate_id": "candidate_001",
                "name": "overclaim_level",
                "value": "high",
            },
        ]
    )
    candidate["facts"].sort(key=lambda item: item["evidence_id"])
    return type(_bundle()).model_validate(payload)


def test_grounding_requires_exact_phase92_skill_fit_fact() -> None:
    ground, _ = _grounding_modules()
    bundle, facts, projected, _ = _prepared()
    payload = _valid_plan_payload(projected)
    payload["candidates"][0]["match_reasons"][0]["evidence_refs"] = (
        projected.payload.candidates[0].facts.ranking_context[0].evidence_refs
    )
    plan = ExplanationPlanV1.model_validate(payload)

    with pytest.raises(ValueError, match="skill_fit|semantic|exact"):
        ground(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_grounding_permits_feature_refs_only_for_selected_ranking_context() -> None:
    ground, _ = _grounding_modules()
    bundle, facts, projected, plan = _prepared()

    grounded = ground(
        plan,
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    )

    assert any(
        reason.category == "ranking_context"
        for reason in grounded.candidates[0].match_reasons
    )


def test_grounding_requires_exact_risk_fact_selection() -> None:
    ground, _ = _grounding_modules()
    bundle = _missing_requirement_bundle()
    facts = build_evidence_facts(bundle)
    projected = ProviderReferenceProjector().project(
        bundle=bundle,
        evidence_facts=facts,
    )
    payload = _valid_plan_payload(projected)
    risk = projected.payload.candidates[0].facts.risks[0]
    payload["candidates"][0]["risk_points"] = [
        {
            "category": risk.category,
            "template_key": risk.statement_key,
            "evidence_refs": projected.payload.candidates[0]
            .facts.ranking_context[0]
            .evidence_refs,
        }
    ]
    plan = ExplanationPlanV1.model_validate(payload)

    with pytest.raises(ValueError, match="risk|semantic|exact"):
        ground(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_missing_requirements_are_rendered_from_facts_not_provider_plan() -> None:
    ground, render = _grounding_modules()
    bundle, facts, projected, plan = _prepared(_missing_requirement_bundle())

    grounded = ground(
        plan,
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    )
    output = render(grounded, bundle=bundle, evidence_facts=facts)

    assert [item.requirement_id for item in output.candidates[0].missing_skills] == [
        "req_python"
    ]
    assert output.candidates[0].missing_skills[0].status == "missing"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("text", "Strong Rust experience"),
        ("metadata", {"raw_resume": "private"}),
    ],
)
def test_provider_plan_cannot_supply_prose(field: str, value) -> None:
    _, _, projected, _ = _prepared()
    payload = _valid_plan_payload(projected)
    if field == "text":
        payload["candidates"][0]["summary"][field] = value
    else:
        payload[field] = value

    with pytest.raises(ValidationError):
        ExplanationPlanV1.model_validate(payload)


def test_summary_refs_must_be_selected_grounded_facts() -> None:
    ground, _ = _grounding_modules()
    bundle, facts, projected, _ = _prepared()
    payload = _valid_plan_payload(projected)
    ranking_ref = projected.payload.candidates[0].facts.ranking_context[-1].evidence_refs[0]
    payload["candidates"][0]["summary"]["evidence_refs"] = sorted(
        [
            *payload["candidates"][0]["summary"]["evidence_refs"],
            ranking_ref,
        ]
    )
    plan = ExplanationPlanV1.model_validate(payload)

    with pytest.raises(ValueError, match="summary|selected|grounded"):
        ground(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


@pytest.mark.parametrize(
    ("section", "operation"),
    [
        ("interview_question_operations", "ask_evidence_clarification"),
        ("rewrite_operations", "surface_existing_skill"),
    ],
)
def test_operation_refs_reject_ranking_context(section: str, operation: str) -> None:
    ground, _ = _grounding_modules()
    bundle, facts, projected, _ = _prepared()
    payload = _valid_plan_payload(projected)
    ranking_refs = projected.payload.candidates[0].facts.ranking_context[0].evidence_refs
    payload["candidates"][0][section] = [
        {"operation": operation, "evidence_refs": ranking_refs}
    ]
    plan = ExplanationPlanV1.model_validate(payload)

    with pytest.raises(ValueError, match="operation|interview|rewrite|semantic"):
        ground(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_interview_operation_requires_a_deterministic_missing_or_partial_requirement() -> None:
    ground, render = _grounding_modules()
    bundle, facts, projected, _ = _prepared(_missing_requirement_bundle())
    payload = _valid_plan_payload(projected)
    ranking_ref = projected.payload.candidates[0].facts.ranking_context[0].evidence_refs[0]
    payload["candidates"][0]["interview_question_operations"] = [
        {
            "operation": "ask_evidence_clarification",
            "evidence_refs": [ranking_ref],
        }
    ]
    plan = ExplanationPlanV1.model_validate(payload)
    with pytest.raises(ValueError, match="interview|missing|partial|exact"):
        ground(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )

    missing = projected.payload.candidates[0].facts.missing_requirements[0]
    payload["candidates"][0]["interview_question_operations"] = [
        {
            "operation": "ask_evidence_clarification",
            "evidence_refs": missing.evidence_refs,
        }
    ]
    grounded = ground(
        ExplanationPlanV1.model_validate(payload),
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    )
    output = render(grounded, bundle=bundle, evidence_facts=facts)

    assert output.candidates[0].interview_questions[0].evidence_refs == [
        "job_requirement:req_python"
    ]


def test_state_gap_rejects_requirement_recorded_as_matched() -> None:
    ground, _ = _grounding_modules()
    bundle, facts, projected, _ = _prepared()
    payload = _valid_plan_payload(projected)
    requirement_ref = projected.reference_map.internal_to_provider[
        "job_requirement:req_python"
    ]
    payload["candidates"][0]["rewrite_operations"] = [
        {
            "operation": "state_gap_explicitly",
            "evidence_refs": [requirement_ref],
        }
    ]

    with pytest.raises(ValueError, match="gap|missing|partial|rewrite"):
        ground(
            ExplanationPlanV1.model_validate(payload),
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_state_gap_accepts_exact_deterministic_missing_requirement() -> None:
    ground, render = _grounding_modules()
    bundle, facts, projected, _ = _prepared(_missing_requirement_bundle())
    payload = _valid_plan_payload(projected)
    requirement_ref = projected.reference_map.internal_to_provider[
        "job_requirement:req_python"
    ]
    payload["candidates"][0]["rewrite_operations"] = [
        {
            "operation": "state_gap_explicitly",
            "evidence_refs": [requirement_ref],
        }
    ]

    grounded = ground(
        ExplanationPlanV1.model_validate(payload),
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    )
    output = render(grounded, bundle=bundle, evidence_facts=facts)

    assert output.candidates[0].profile_rewrite_suggestion.operations[
        0
    ].requirement_evidence_id == "job_requirement:req_python"


def test_link_skill_to_project_rejects_unrelated_historical_pair() -> None:
    ground, _ = _grounding_modules()
    bundle, facts, projected, _ = _prepared(_unrelated_skill_project_bundle())
    payload = _valid_plan_payload(projected)
    refs = sorted(
        [
            projected.reference_map.internal_to_provider[
                "candidate:1:skill:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ],
            projected.reference_map.internal_to_provider[
                "candidate:1:project:project_001"
            ],
        ]
    )
    payload["candidates"][0]["rewrite_operations"] = [
        {"operation": "link_skill_to_project", "evidence_refs": refs}
    ]

    with pytest.raises(ValueError, match="relationship|project|skill|rewrite"):
        ground(
            ExplanationPlanV1.model_validate(payload),
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_link_skill_to_project_accepts_recorded_historical_relationship() -> None:
    ground, render = _grounding_modules()
    bundle, facts, projected, _ = _prepared()
    payload = _valid_plan_payload(projected)
    refs = sorted(
        [
            projected.reference_map.internal_to_provider[
                bundle.candidates[0].skills[0].evidence_id
            ],
            projected.reference_map.internal_to_provider[
                bundle.candidates[0].projects[0].evidence_id
            ],
        ]
    )
    payload["candidates"][0]["rewrite_operations"] = [
        {"operation": "link_skill_to_project", "evidence_refs": refs}
    ]

    grounded = ground(
        ExplanationPlanV1.model_validate(payload),
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    )
    output = render(grounded, bundle=bundle, evidence_facts=facts)

    assert output.candidates[0].profile_rewrite_suggestion.operations[
        0
    ].operation == "link_skill_to_project"


def test_hidden_opaque_reference_cannot_be_guessed_for_rewrite_support() -> None:
    ground, _ = _grounding_modules()
    bundle, facts, projected, _ = _prepared()
    serialized = projected.payload.model_dump_json()
    hidden_internal = "diagnostic:1:matched_must_have_requirement_ids"
    hidden_ref = projected.reference_map.internal_to_provider.get(
        hidden_internal,
        "ref_9999",
    )
    assert hidden_ref not in serialized
    visible_project_ref = projected.reference_map.internal_to_provider[
        bundle.candidates[0].project_evidence[0].evidence_id
    ]
    payload = _valid_plan_payload(projected)
    payload["candidates"][0]["rewrite_operations"] = [
        {
            "operation": "clarify_evidence_status",
            "evidence_refs": sorted([hidden_ref, visible_project_ref]),
        }
    ]

    with pytest.raises(ValueError, match="unknown|provider reference|projection"):
        ground(
            ExplanationPlanV1.model_validate(payload),
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_top_one_and_non_top_one_comparison_rules_are_exact() -> None:
    ground, _ = _grounding_modules()
    bundle, facts, projected, _ = _prepared(_two_candidate_bundle())
    payload = _valid_plan_payload(projected)
    rank_one = payload["candidates"][0]
    rank_one["why_not_top1"] = {
        "template_key": "why_not_top1_recorded",
        "evidence_refs": payload["candidates"][1]["why_not_top1"]["evidence_refs"],
    }
    with pytest.raises(ValidationError):
        ExplanationPlanV1.model_validate(payload)

    payload = _valid_plan_payload(projected)
    payload["candidates"][1]["why_not_top1"]["evidence_refs"] = (
        projected.payload.candidates[1].facts.ranking_context[0].evidence_refs
    )
    plan = ExplanationPlanV1.model_validate(payload)
    with pytest.raises(ValueError, match="top-1|comparison|exact"):
        ground(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_comparison_projection_and_grounding_use_one_canonical_bounded_subset() -> None:
    ground, render = _grounding_modules()
    bundle = _many_comparison_bundle()
    facts = build_evidence_facts(bundle)

    projected = ProviderReferenceProjector().project(
        bundle=bundle,
        evidence_facts=facts,
    )
    comparison = projected.payload.candidates[1].facts.comparison
    assert comparison is not None
    assert len(comparison.evidence_refs) == 6
    assert comparison.evidence_refs == sorted(set(comparison.evidence_refs))

    plan = ExplanationPlanV1.model_validate(_valid_plan_payload(projected))
    grounded = ground(
        plan,
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    )
    output = render(grounded, bundle=bundle, evidence_facts=facts)

    assert len(output.candidates[1].why_not_top1.evidence_refs) == 6
    validate_explanation_output_references(output.candidates[1], bundle)


def test_rendering_resolves_opaque_refs_and_validates_frozen_output_contract() -> None:
    ground, render = _grounding_modules()
    bundle, facts, projected, plan = _prepared()

    grounded = ground(
        plan,
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    )
    output = render(grounded, bundle=bundle, evidence_facts=facts)

    assert isinstance(output, ExplanationOutputV1)
    assert "ref_" not in output.model_dump_json()
    for candidate in output.candidates:
        validate_explanation_output_references(candidate, bundle)


def test_maximum_valid_plan_cardinalities_render_end_to_end() -> None:
    ground, render = _grounding_modules()
    bundle = _maximum_cardinality_bundle()
    facts = build_evidence_facts(bundle)
    projected = ProviderReferenceProjector().project(
        bundle=bundle,
        evidence_facts=facts,
    )
    candidate_facts = projected.payload.candidates[0].facts

    reason_selections = [
        {
            "category": reason.category,
            "template_key": reason.statement_key,
            "evidence_refs": reason.evidence_refs,
        }
        for reason in candidate_facts.match_reasons
    ]
    risk_selections = sorted(
        (
            {
                "category": risk.category,
                "template_key": risk.statement_key,
                "evidence_refs": risk.evidence_refs,
            }
            for risk in candidate_facts.risks
        ),
        key=lambda item: PlanRiskPoint.model_validate(item).model_dump_json(),
    )
    missing = [
        item
        for item in candidate_facts.missing_requirements
        if item.status in {"missing", "partial"}
    ]
    question_selections = sorted(
        (
            {
                "operation": "ask_evidence_clarification",
                "evidence_refs": item.evidence_refs,
            }
            for item in missing
        ),
        key=lambda item: PlanInterviewQuestionOperation.model_validate(
            item
        ).model_dump_json(),
    )
    skill_ref = projected.reference_map.internal_to_provider[
        bundle.candidates[0].skills[0].evidence_id
    ]
    project_ref = projected.reference_map.internal_to_provider[
        bundle.candidates[0].projects[0].evidence_id
    ]
    gap_ref = projected.reference_map.internal_to_provider[
        "job_requirement:req_gap_1"
    ]
    rewrite_selections = sorted(
        [
            {
                "operation": "surface_existing_skill",
                "evidence_refs": [skill_ref],
            },
            {
                "operation": "link_skill_to_project",
                "evidence_refs": sorted([skill_ref, project_ref]),
            },
            {
                "operation": "state_gap_explicitly",
                "evidence_refs": [gap_ref],
            },
        ],
        key=lambda item: PlanRewriteOperation.model_validate(item).model_dump_json(),
    )
    payload = {
        "contract_version": "explanation_plan_v1",
        "candidates": [
            {
                "candidate_ref": projected.payload.candidates[0].candidate_ref,
                "result_rank": 1,
                "summary": {
                    "template_key": "recorded_match_summary",
                    "evidence_refs": reason_selections[0]["evidence_refs"],
                },
                "match_reasons": reason_selections,
                "risk_points": risk_selections,
                "interview_question_operations": question_selections,
                "why_not_top1": None,
                "rewrite_operations": rewrite_selections,
            }
        ],
    }

    assert len(reason_selections) == 4
    assert len(risk_selections) == 4
    assert len(question_selections) == 3
    assert len(rewrite_selections) == 3

    grounded = ground(
        ExplanationPlanV1.model_validate(payload),
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    )
    output = render(grounded, bundle=bundle, evidence_facts=facts)
    candidate = output.candidates[0]

    assert len(candidate.match_reasons) == 4
    assert len(candidate.risk_points) == 4
    assert len(candidate.interview_questions) == 3
    assert candidate.profile_rewrite_suggestion is not None
    assert len(candidate.profile_rewrite_suggestion.operations) == 3
    validate_explanation_output_references(candidate, bundle)


def test_rendering_is_deterministic_with_a_stable_frozen_output_fingerprint() -> None:
    ground, render = _grounding_modules()
    bundle, facts, projected, plan = _prepared()

    first = render(
        ground(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        ),
        bundle=bundle,
        evidence_facts=facts,
    )
    second = render(
        ground(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        ),
        bundle=bundle,
        evidence_facts=facts,
    )

    assert first == second
    assert explanation_result_fingerprint(first.candidates) == (
        explanation_result_fingerprint(second.candidates)
    )
    assert json.dumps(first.model_dump(mode="json"), sort_keys=True) == json.dumps(
        second.model_dump(mode="json"), sort_keys=True
    )
