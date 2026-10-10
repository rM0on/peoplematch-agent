"""RED/GREEN tests for the opt-in field-level communication plan."""

import json

import pytest

from app.services.explanation.presentation.generation_proposition_v1 import (
    build_proposition_generation_request_v1,
    build_proposition_binding_v1,
    PropositionProviderOutputV1, resolve_proposition_output_v1,
)
from app.services.explanation.presentation.propositions_v1 import build_recruiter_propositions_for_interview_v1
from app.services.explanation.presentation.semantic_intent_proposition_v1 import (
    build_semantic_intent_plan_v1,
    build_semantic_intent_generation_request_v1,
)
from app.services.explanation.presentation import semantic_intent_proposition_v1 as intent_module
from narrative_v2_comparison_fixture import build_comparison_group


def _case(group=1, index=0):
    projection = build_comparison_group(group)["projections"][index]
    return projection, build_recruiter_propositions_for_interview_v1(projection)


def test_plan_is_deterministic_canonical_and_candidate_scoped():
    projection, propositions = _case()
    first = build_semantic_intent_plan_v1(projection, propositions)
    assert first == build_semantic_intent_plan_v1(projection, propositions)
    assert first.candidate_id == projection.candidate_id
    ids = {p.proposition_id for p in propositions.propositions}
    assert all(set(field.proposition_ids) <= ids for field in first.fields)
    assert len({field.name for field in first.fields}) == 5
    other_projection, other_propositions = _case(1, 1)
    with pytest.raises(ValueError, match="noncanonical_interview_recruiter_propositions"):
        build_semantic_intent_plan_v1(other_projection, propositions)
    assert build_semantic_intent_plan_v1(other_projection, other_propositions).candidate_id != first.candidate_id


def test_plan_preserves_epistemic_subject_and_recommendation_strength():
    strong_projection, strong_props = _case(1, 0)
    weak_projection, weak_props = _case(1, 1)
    strong = build_semantic_intent_plan_v1(strong_projection, strong_props)
    weak = build_semantic_intent_plan_v1(weak_projection, weak_props)
    assert strong.field("decision_summary").recommendation_strength == "priority_human_review"
    assert weak.field("decision_summary").recommendation_strength == "conditional_targeted_screen"
    for plan, props in ((strong, strong_props), (weak, weak_props)):
        lookup = {p.proposition_id: p for p in props.propositions}
        for field in plan.fields:
            assert field.proposition_ids
            assert all(field.name in lookup[pid].allowed_fields for pid in field.proposition_ids)
        assert all(lookup[pid].modality == "alignment"
                   for pid in plan.field("why_consider").proposition_ids
                   if lookup[pid].kind == "technical_alignment")
        assert all(lookup[pid].subject in {"project_material", "candidate_material"}
                   for pid in plan.field("technical_signal").proposition_ids)
        assert all(lookup[pid].modality == "hypothesis"
                   for pid in plan.field("interview_focus").proposition_ids)
        assert all(lookup[pid].modality == "unknown"
                   for pid in plan.field("uncertainty").proposition_ids)


def test_plan_rejects_tampered_provenance_and_does_not_render_prose():
    projection, propositions = _case()
    changed = propositions.model_copy(update={"candidate_id": "other"})
    with pytest.raises(ValueError, match="noncanonical_interview_recruiter_propositions"):
        build_semantic_intent_plan_v1(projection, changed)
    plan = build_semantic_intent_plan_v1(projection, propositions)
    assert not hasattr(plan, "decision_summary")
    assert not any("候选" in str(field.model_dump()) for field in plan.fields)


def test_intent_request_scopes_native_schema_to_field_focus_without_changing_handles():
    projection, propositions = _case()
    old = build_proposition_generation_request_v1(projection, propositions, max_output_tokens=4096)
    plan = build_semantic_intent_plan_v1(projection, propositions)
    new = build_semantic_intent_generation_request_v1(
        projection, propositions, plan, max_output_tokens=4096)
    assert new.response_schema != old.response_schema
    assert new.output_contract_version == old.output_contract_version
    payload = json.loads(new.user_instruction)
    assert "semantic_intent_plan" in payload
    binding = build_proposition_binding_v1(propositions)
    scoped = intent_module.build_semantic_intent_binding_v1(propositions, plan)
    assert [(entry.handle, entry.proposition_id) for entry in scoped.entries] == [
        (entry.handle, entry.proposition_id) for entry in binding.entries]
    for field in payload["semantic_intent_plan"]:
        name = field["name"]
        expected = set(field["focus_handles"])
        assert expected == set(scoped.allowed_handles(name))
        schema_field = new.response_schema["properties"][name]
        if name != "decision_summary":
            schema_field = schema_field["items"]
        assert set(schema_field["properties"]["proposition_handles"]["properties"]) == expected
    assert "proposition:" not in new.user_instruction
    assert "claim:" not in new.user_instruction
    assert "candidate_id" in payload


def test_nonfocus_but_field_role_valid_handle_fails_exact_resolution():
    projection, props = _case(1, 0)
    plan = build_semantic_intent_plan_v1(projection, props)
    original = build_proposition_binding_v1(props)
    scoped = intent_module.build_semantic_intent_binding_v1(props, plan)
    extra = next(handle for handle in original.allowed_handles("why_consider")
                 if handle not in scoped.allowed_handles("why_consider"))
    payload = {
        "contract_version": "recruiter_proposition_generation_v1",
        "candidate_id": props.candidate_id, "result_rank": props.result_rank,
        "decision_summary": {"text": "建议安排下一步人工技术复核。",
                             "proposition_handles": {scoped.allowed_handles("decision_summary")[0]: True}},
        **{field: [{"text": "请继续核对这一条合成候选材料。",
                    "proposition_handles": {scoped.allowed_handles(field)[0]: True}}]
           for field in ("why_consider", "technical_signal", "interview_focus", "uncertainty")},
    }
    payload["why_consider"][0]["proposition_handles"] = {extra: True}
    output = PropositionProviderOutputV1.model_validate(payload)
    assert resolve_proposition_output_v1(output, original).candidate_id == props.candidate_id
    with pytest.raises(ValueError, match="unknown_or_wrong_role_proposition_handle_key"):
        resolve_proposition_output_v1(output, scoped)


def test_interview_topic_is_source_derived_and_weak_review_is_screen_only():
    for group, index in ((1, 0), (1, 1), (2, 1), (3, 0)):
        projection, props = _case(group, index)
        plan = build_semantic_intent_plan_v1(projection, props)
        interview = plan.field("interview_focus")
        assert interview.question_intent is not None
        assert interview.focus_topic in projection.facts[interview.question_intent.target_requirement_ref]
        targets = {p.proposition_id: p for p in props.propositions}
        assert all(targets[pid].kind == "interview_target" for pid in interview.proposition_ids)
        request = build_semantic_intent_generation_request_v1(
            projection, props, plan, max_output_tokens=4096)
        payload = json.loads(request.user_instruction)
        question = next(row for row in payload["semantic_intent_plan"]
                        if row["name"] == "interview_focus")
        assert question["focus_topic"] == interview.focus_topic
        summary = next(row for row in payload["semantic_intent_plan"]
                       if row["name"] == "decision_summary")
        if group == 2 and index == 1:
            assert summary["recommendation_strength"] == "conditional_targeted_screen"
            assert "面试邀请" in request.system_instruction


def test_intent_request_rejects_foreign_or_tampered_plan():
    projection, props = _case()
    plan = build_semantic_intent_plan_v1(projection, props)
    with pytest.raises(ValueError, match="noncanonical_semantic_intent_plan"):
        build_semantic_intent_generation_request_v1(
            projection, props, plan.model_copy(update={"candidate_id": "other"}),
            max_output_tokens=4096)


@pytest.mark.parametrize("group,role", [
    (4, "LLM Application Engineer"), (5, "Search Ranking Engineer"),
    (6, "Data Search Infrastructure Engineer"), (7, "Vision API Engineer"),
])
def test_preregistered_holdout_is_synthetic_and_not_baseline(group, role):
    candidate = build_comparison_group(group)
    assert candidate["role"] == role
    assert candidate["run"].run_id == f"synthetic_phase3_group_{group}"
    projection = candidate["projections"][0]
    plan = build_semantic_intent_plan_v1(projection, build_recruiter_propositions_for_interview_v1(projection))
    assert len(plan.fields) == 5
    assert candidate["run"].result_fingerprint == candidate["ranking_before"]["fingerprint"]


def test_new_holdouts_span_strong_and_conditional_review_without_ranking_mutation():
    expected = ((6, "priority_human_review"), (7, "conditional_targeted_screen"))
    for group_number, strength in expected:
        group = build_comparison_group(group_number)
        projection = group["projections"][0]
        plan = build_semantic_intent_plan_v1(
            projection, build_recruiter_propositions_for_interview_v1(projection))
        assert plan.field("decision_summary").recommendation_strength == strength
        run = group["run"]
        assert [result.candidate_id for result in run.results] == group["ranking_before"]["order"]
        assert [result.ltr_score_raw for result in run.results] == group["ranking_before"]["ltr_scores"]
