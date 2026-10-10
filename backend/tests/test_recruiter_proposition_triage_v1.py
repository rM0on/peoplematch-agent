"""RED/GREEN for the final, opt-in short recruiter-triage task."""

import json

import pytest

from app.services.explanation.presentation.generation_proposition_v1 import (
    build_proposition_binding_v1,
    parse_proposition_provider_output_v1,
)
from app.services.explanation.presentation.propositions_v1 import build_recruiter_propositions_v1
from app.services.explanation.presentation.triage_generation_proposition_v1 import (
    build_triage_generation_request_v1,
    build_triage_intent_plan_v1,
    resolve_triage_output_v1,
)
from narrative_v2_comparison_fixture import build_comparison_group
from narrative_triage_holdout_fixture import build_triage_holdout


def _case(group=1, index=0):
    projection = build_comparison_group(group)["projections"][index]
    return projection, build_recruiter_propositions_v1(projection)


@pytest.mark.parametrize("group,index", [(1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1)])
def test_triage_selects_one_canonical_commitment_per_field(group, index):
    projection, propositions = _case(group, index)
    plan = build_triage_intent_plan_v1(projection, propositions)
    assert plan == build_triage_intent_plan_v1(projection, propositions)
    assert plan.candidate_id == projection.candidate_id
    assert len(plan.fields) == 5
    lookup = {item.proposition_id: item for item in propositions.propositions}
    assert all(len(field.proposition_ids) == 1 for field in plan.fields)
    assert all(field.proposition_ids[0] in lookup for field in plan.fields)
    assert all(field.name in lookup[field.proposition_ids[0]].allowed_fields for field in plan.fields)
    assert plan.field("interview_focus").question_intent is None
    assert lookup[plan.field("interview_focus").proposition_ids[0]].predicate == "verify_project_scope"
    assert plan.field("decision_summary").recommendation_strength == (
        "priority_human_review"
        if lookup[plan.field("decision_summary").proposition_ids[0]].predicate == "prioritize_technical_review"
        else "conditional_targeted_screen"
    )


def test_weak_overlap_stays_conditional_and_chooses_job_related_first_check():
    for group, index in ((1, 1), (2, 1)):
        projection, propositions = _case(group, index)
        plan = build_triage_intent_plan_v1(projection, propositions)
        assert plan.field("decision_summary").recommendation_strength == "conditional_targeted_screen"
        request = build_triage_generation_request_v1(
            projection, propositions, plan, max_output_tokens=2048)
        payload = json.loads(request.user_instruction)
        focus = payload["first_check"]
        assert focus["topic"] in {
            term.casefold() for ref in projection.positive_refs
            if ref.startswith("job_requirement:") for term in projection.facts[ref]
        }
        assert focus["level"] == "participation_or_scope_only"
        assert payload["review_action"] == "conditional_targeted_screen"
        assert "question_intent" not in request.user_instruction
        assert "decision_rationale" not in request.user_instruction


def test_candidate_isolation_and_provenance_fail_closed():
    projection, propositions = _case(1, 0)
    other_projection, other_propositions = _case(1, 1)
    plan = build_triage_intent_plan_v1(projection, propositions)
    with pytest.raises(ValueError):
        build_triage_intent_plan_v1(other_projection, propositions)
    with pytest.raises(ValueError, match="noncanonical_triage_intent_plan"):
        build_triage_generation_request_v1(
            projection, propositions, plan.model_copy(update={"candidate_id": "other"}),
            max_output_tokens=2048)
    assert build_triage_intent_plan_v1(other_projection, other_propositions).candidate_id != plan.candidate_id
    for field in plan.fields:
        source = next(item for item in propositions.propositions
                      if item.proposition_id == field.proposition_ids[0])
        assert source.source_fact_ids
        assert source.evidence_refs
        assert set(source.evidence_refs) <= projection.facts.keys()


def test_request_reuses_schema_and_handles_but_limits_each_field_to_one_item():
    projection, propositions = _case()
    plan = build_triage_intent_plan_v1(projection, propositions)
    request = build_triage_generation_request_v1(
        projection, propositions, plan, max_output_tokens=2048)
    payload = json.loads(request.user_instruction)
    assert request.response_schema is not None
    assert request.response_schema["properties"]["interview_focus"]["maxItems"] == 1
    assert request.response_schema["properties"]["why_consider"]["maxItems"] == 1
    assert request.output_contract_version == "recruiter_proposition_generation_v1"
    assert "proposition:" not in request.user_instruction
    assert "claim:" not in request.user_instruction
    assert len(payload["semantic_intent_plan"]) == 5
    assert all(len(field["focus_handles"]) == 1 for field in payload["semantic_intent_plan"])
    assert set(payload["proposition_catalog"]) == {
        "decision_summary", "why_consider", "technical_signal", "interview_focus", "uncertainty"}
    original = build_proposition_binding_v1(propositions)
    assert all(payload["proposition_catalog"][field]["handle"] in original.allowed_handles(field)
               for field in payload["proposition_catalog"])


def test_resolver_rejects_extra_item_and_foreign_handle_without_normalizing_text():
    projection, propositions = _case()
    plan = build_triage_intent_plan_v1(projection, propositions)
    request = build_triage_generation_request_v1(
        projection, propositions, plan, max_output_tokens=2048)
    payload = json.loads(request.user_instruction)
    item = lambda field: {
        "text": "请核对这一条合成候选人的来源事实。",
        "proposition_handles": {payload["proposition_catalog"][field]["handle"]: True},
    }
    body = {
        "contract_version": "recruiter_proposition_generation_v1",
        "candidate_id": propositions.candidate_id,
        "result_rank": propositions.result_rank,
        "decision_summary": item("decision_summary"),
        **{field: [item(field)] for field in
           ("why_consider", "technical_signal", "interview_focus", "uncertainty")},
    }
    output = parse_proposition_provider_output_v1(json.dumps(body, ensure_ascii=False))
    resolved = resolve_triage_output_v1(output, propositions, plan)
    assert resolved.interview_focus[0].text == body["interview_focus"][0]["text"]
    body["interview_focus"].append(item("interview_focus"))
    with pytest.raises(ValueError, match="triage_multiple_items"):
        resolve_triage_output_v1(parse_proposition_provider_output_v1(json.dumps(body)), propositions, plan)
    body["interview_focus"] = [item("interview_focus")]
    body["interview_focus"][0]["proposition_handles"] = {"P99": True}
    with pytest.raises(ValueError):
        resolve_triage_output_v1(parse_proposition_provider_output_v1(json.dumps(body)), propositions, plan)


@pytest.mark.parametrize("name,expected_strength", [
    ("workflow_automation_holdout", "priority_human_review"),
    ("geospatial_ml_holdout", "conditional_targeted_screen"),
])
def test_new_holdouts_are_synthetic_independent_and_ranking_immutable(name, expected_strength):
    group = build_triage_holdout(name)
    projection = group["projections"][0]
    propositions = build_recruiter_propositions_v1(projection)
    plan = build_triage_intent_plan_v1(projection, propositions)
    request = build_triage_generation_request_v1(
        projection, propositions, plan, max_output_tokens=2048)
    assert plan.field("decision_summary").recommendation_strength == expected_strength
    assert json.loads(request.user_instruction)["first_check"]["topic"] in {
        term.casefold() for ref in projection.positive_refs if ref.startswith("job_requirement:")
        for term in projection.facts[ref]
    }
    run = group["run"]
    assert run.result_fingerprint == group["ranking_before"]["fingerprint"]
    assert [item.candidate_id for item in run.results] == group["ranking_before"]["order"]
    assert [item.ltr_score_raw for item in run.results] == group["ranking_before"]["ltr_scores"]
