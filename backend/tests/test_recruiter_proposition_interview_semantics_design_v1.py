"""Offline design gold for the archived eight-question failure; no provider calls."""

from hashlib import sha256
import json
from pathlib import Path
from dataclasses import replace

import pytest
from pydantic import ValidationError

from narrative_v2_comparison_fixture import build_comparison_group
from app.services.explanation.presentation.facts_v2 import (
    build_atomic_facts, build_selected_requirement_verification_facts,
)
from app.services.explanation.presentation.interview_semantics_proposition_v1 import (
    InterviewQuestionIntentV1, build_interview_question_intent_v1,
)
from app.services.explanation.presentation.propositions_v1 import (
    build_recruiter_propositions_for_interview_v1 as build_interview_propositions,
    validate_interview_recruiter_propositions_v1 as validate_interview_propositions,
)
from app.services.explanation.presentation.semantic_intent_proposition_v1 import (
    build_semantic_intent_generation_request_v1,
    build_semantic_intent_plan_v1,
)


FIXTURES = Path(__file__).parent / "fixtures"
DESIGN = FIXTURES / "recruiter_proposition_interview_semantics_design_gold_v1.json"
GROUP = {
    "ai_agent_a": (1, 0), "ai_agent_b": (1, 1),
    "recommendation_a": (2, 0), "recommendation_b": (2, 1),
    "backend_a": (3, 0), "backend_b": (3, 1),
    "data_search_holdout": (6, 0), "vision_api_holdout": (7, 0),
}


def _load():
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    run_file = FIXTURES / design["source_run"]
    gold_file = FIXTURES / design["source_gold"]
    assert sha256(run_file.read_bytes()).hexdigest().upper() == design["source_run_sha256"]
    assert sha256(gold_file.read_bytes()).hexdigest().upper() == design["source_gold_sha256"]
    rows = [json.loads(line) for line in run_file.read_text(encoding="utf-8").splitlines()]
    run = {row["scenario_id"]: row for row in rows if row.get("record_type") == "case"}
    gold = {row["scenario_id"]: row for row in json.loads(gold_file.read_text(encoding="utf-8"))["cases"]}
    return design, run, gold


def test_design_cases_pin_all_eight_archived_question_failures():
    design, run, gold = _load()
    assert set(GROUP) == set(run) == set(gold) == {case["scenario_id"] for case in design["cases"]}
    assert len(design["cases"]) == 8
    unsupported_fragments = 0
    for case in design["cases"]:
        source = run[case["scenario_id"]]
        question = source["narrative"]["interview_focus"][0]["text"]
        rejected = [item for item in gold[case["scenario_id"]]["items"]
                    if item["field"] == "interview_focus" and item["adjudication"] == "unsupported"]
        assert rejected
        assert {item["category"] for item in rejected} == set(case["invalid_gold_categories"])
        assert all(item["quote"] in question for item in rejected)
        unsupported_fragments += len(rejected)
        selected = next(field for field in source["intent_plan"]["fields"]
                        if field["name"] == "interview_focus")
        propositions = {item["proposition_id"]: item for item in source["propositions"]}
        assert {propositions[pid]["predicate"] for pid in selected["proposition_ids"]} == {
            "verify_project_scope"}
        assert not case["decision_responsibility_established"]
    assert unsupported_fragments == 10


def test_design_targets_are_source_backed_and_respect_candidate_isolation():
    design, run, _ = _load()
    for case in design["cases"]:
        group_number, index = GROUP[case["scenario_id"]]
        projection = build_comparison_group(group_number)["projections"][index]
        source = run[case["scenario_id"]]
        assert projection.candidate_id == source["candidate_id"]
        assert projection.facts[case["target_job_requirement_ref"]] == (case["target_topic"],)
        assert case["target_job_requirement_ref"] in projection.positive_refs
        alignments = [item for item in source["propositions"]
                      if item["kind"] == "technical_alignment"
                      and case["target_job_requirement_ref"] in item["job_requirement_refs"]]
        if case["source_relation"] == "project_backed_alignment":
            assert alignments
        else:
            assert case["source_relation"] == "job_requirement_without_candidate_alignment"
            assert not alignments
            assert case["review_strength"] == "conditional_targeted_screen"


def test_question_precondition_graph_does_not_collapse_participation_into_decision():
    design, _, _ = _load()
    graph = design["question_preconditions"]
    assert "confirmed_personal_participation_or_explicit_if_participated_condition" in graph["participation_scope"]
    assert "confirmed_personal_participation_or_explicit_if_participated_condition" in graph["decision_responsibility"]
    assert "confirmed_personal_decision_responsibility_or_explicit_if_personally_decided_condition" in graph["decision_rationale"]
    assert graph["requirement_verification"] == [
        "validated_job_requirement_ref", "no_candidate_deficiency_assertion"]


@pytest.mark.parametrize("scenario_id", ["ai_agent_b", "recommendation_b", "vision_api_holdout"])
def test_red_archived_weak_overlap_focus_should_be_job_requirement(scenario_id):
    design, run, _ = _load()
    case = next(item for item in design["cases"] if item["scenario_id"] == scenario_id)
    group_number, index = GROUP[scenario_id]
    projection = build_comparison_group(group_number)["projections"][index]
    propositions = build_interview_propositions(projection)
    selected = build_semantic_intent_plan_v1(projection, propositions).field("interview_focus")
    assert selected.focus_topic.casefold() == case["target_topic"].casefold()
    assert selected.question_intent.question_kind == "requirement_verification"
    assert selected.question_intent.target_requirement_ref == case["target_job_requirement_ref"]
    assert selected.question_intent.direct_question_level == "requirement_verification"
    assert selected.question_intent.decision_rationale_gate == "personal_decision_confirmation_required"
    assert any(p.predicate == "verify_open_requirement"
               and case["target_job_requirement_ref"] in p.job_requirement_refs
               for p in propositions.propositions)
    assert run[scenario_id]["intent_plan"]["fields"][-2]["focus_topic"] == case["old_focus_topic"]


@pytest.mark.parametrize("scenario_id", list(GROUP))
def test_all_eight_current_question_intents_match_source_backed_gold(scenario_id):
    design, run, _ = _load()
    case = next(item for item in design["cases"] if item["scenario_id"] == scenario_id)
    group_number, index = GROUP[scenario_id]
    projection = build_comparison_group(group_number)["projections"][index]
    propositions = build_interview_propositions(projection)
    plan = build_semantic_intent_plan_v1(projection, propositions)
    interview = plan.field("interview_focus")
    question = interview.question_intent
    assert question is not None
    assert question.candidate_id == projection.candidate_id == run[scenario_id]["candidate_id"]
    assert question.result_rank == projection.result_rank
    assert question.question_kind == case["desired_question_kind"]
    assert question.review_action == case["review_strength"]
    assert question.target_requirement_ref == case["target_job_requirement_ref"]
    assert question.target_topic.casefold() == case["target_topic"].casefold()
    assert question.supporting_proposition_ids == interview.proposition_ids
    assert question.direct_question_level in {"participation_existence", "requirement_verification"}
    assert question.decision_rationale_gate == "personal_decision_confirmation_required"
    assert all(next(p for p in propositions.propositions if p.proposition_id == pid).candidate_id
               == projection.candidate_id for pid in question.supporting_proposition_ids)
    old_ids = {p["proposition_id"] for p in run[scenario_id]["propositions"]}
    assert old_ids <= {p.proposition_id for p in propositions.propositions}


def test_request_exposes_content_intent_but_never_unconditional_decision_rationale():
    import json

    projection = build_comparison_group(2)["projections"][1]
    propositions = build_interview_propositions(projection)
    plan = build_semantic_intent_plan_v1(projection, propositions)
    request = build_semantic_intent_generation_request_v1(
        projection, propositions, plan, max_output_tokens=4096)
    field = next(item for item in json.loads(request.user_instruction)["semantic_intent_plan"]
                 if item["name"] == "interview_focus")
    assert field["question_intent"]["target_topic"] == "Retrieval"
    assert field["question_intent"]["question_kind"] == "requirement_verification"
    assert "proposition:" not in request.user_instruction
    assert "job_requirement:" not in request.user_instruction
    assert "先确认是否参与，再视回答追问选择或评估依据" not in request.system_instruction


@pytest.mark.parametrize("scenario_id", ["ai_agent_b", "recommendation_b", "vision_api_holdout"])
def test_weak_requirement_target_reuses_atomic_fact_identity_and_exact_jd_lineage(scenario_id):
    design, _, _ = _load()
    case = next(item for item in design["cases"] if item["scenario_id"] == scenario_id)
    group_number, index = GROUP[scenario_id]
    projection = build_comparison_group(group_number)["projections"][index]
    existing = {fact.fact_id for fact in build_atomic_facts(projection)}
    sources = [fact for fact in build_selected_requirement_verification_facts(projection)
               if fact.evidence_refs == (case["target_job_requirement_ref"],)]
    assert len(sources) == 1
    assert sources[0].kind == "open_requirement"
    assert sources[0].term == case["target_topic"]
    assert sources[0].fact_id not in existing
    propositions = build_interview_propositions(projection)
    target = next(item for item in propositions.propositions
                  if item.predicate == "verify_open_requirement"
                  and case["target_job_requirement_ref"] in item.job_requirement_refs)
    assert target.source_fact_ids == (sources[0].fact_id,)
    assert target.evidence_refs == (case["target_job_requirement_ref"],)
    assert target.source_claim_ids == ()
    assert target.candidate_id == projection.candidate_id
    assert target.modality == "hypothesis"
    assert target.polarity == "undetermined"
    validate_interview_propositions(propositions, projection=projection)


def test_interview_question_rejects_missing_source_foreign_candidate_and_wrong_review():
    group = build_comparison_group(2)
    projection = group["projections"][1]
    propositions = build_interview_propositions(projection)
    review_id = next(item.proposition_id for item in propositions.propositions
                     if item.kind == "human_review_recommendation")
    with pytest.raises(ValueError, match="interview_review_action_missing_or_ambiguous"):
        build_interview_question_intent_v1(
            projection, propositions, review_proposition_id="proposition:unknown")
    target_ref = "job_requirement:req_domain_1"
    missing = replace(projection, facts={ref: terms for ref, terms in projection.facts.items()
                                         if ref != target_ref})
    with pytest.raises(ValueError, match="selected_evidence_missing_from_projection"):
        build_interview_question_intent_v1(missing, propositions, review_proposition_id=review_id)
    foreign = build_interview_propositions(group["projections"][0])
    with pytest.raises(ValueError, match="noncanonical_interview_recruiter_propositions"):
        build_interview_question_intent_v1(projection, foreign, review_proposition_id=review_id)
    target = next(item for item in propositions.propositions
                  if item.predicate == "verify_open_requirement"
                  and target_ref in item.job_requirement_refs)
    corrupted = target.model_copy(update={"candidate_id": foreign.candidate_id})
    altered = propositions.model_copy(update={
        "propositions": tuple(corrupted if item.proposition_id == target.proposition_id else item
                              for item in propositions.propositions)})
    with pytest.raises(ValueError, match="noncanonical_interview_recruiter_propositions"):
        validate_interview_propositions(altered, projection=projection)


def test_question_contract_does_not_promote_participation_to_decision_or_screen_to_interview():
    projection = build_comparison_group(2)["projections"][1]
    propositions = build_interview_propositions(projection)
    question = build_semantic_intent_plan_v1(projection, propositions).field("interview_focus").question_intent
    assert question is not None
    assert question.review_action == "conditional_targeted_screen"
    assert question.follow_up_gate == "requirement_practice_confirmation_required"
    with pytest.raises(ValidationError):
        InterviewQuestionIntentV1.model_validate({
            **question.model_dump(), "direct_question_level": "decision_rationale"})
    with pytest.raises(ValidationError):
        InterviewQuestionIntentV1.model_validate({
            **question.model_dump(), "follow_up_gate": "personal_participation_confirmation_required"})
    with pytest.raises(ValidationError):
        InterviewQuestionIntentV1.model_validate({
            **question.model_dump(), "question_kind": "participation_existence",
            "direct_question_level": "participation_existence",
            "follow_up_gate": "personal_participation_confirmation_required"})


def test_generation_request_rebuild_rejects_tampered_question_source_or_gate():
    projection = build_comparison_group(2)["projections"][1]
    propositions = build_interview_propositions(projection)
    plan = build_semantic_intent_plan_v1(projection, propositions)
    changed_fields = tuple(
        field.model_copy(update={"question_intent": field.question_intent.model_copy(update={
            "target_requirement_ref": "job_requirement:invented"})})
        if field.name == "interview_focus" else field for field in plan.fields
    )
    with pytest.raises(ValueError, match="noncanonical_semantic_intent_plan"):
        build_semantic_intent_generation_request_v1(
            projection, propositions, plan.model_copy(update={"fields": changed_fields}),
            max_output_tokens=4096)
