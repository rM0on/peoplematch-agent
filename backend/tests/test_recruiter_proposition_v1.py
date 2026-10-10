"""Gold semantic boundaries over existing synthetic explanation evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import ValidationError

from narrative_v2_comparison_fixture import build_comparison_group
from test_recruiter_narrative_v4 import _projection

from app.services.explanation.presentation.claims_v4 import build_recruiter_claim_graph_v4
from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3
from app.services.explanation.presentation.facts_v2 import build_atomic_facts
from app.services.explanation.presentation.propositions_v1 import (
    build_recruiter_propositions_from_evidence_v1,
    build_recruiter_propositions_v1,
    validate_recruiter_propositions_v1,
)
from app.services.explanation.presentation.contracts_proposition_v1 import RecruiterPropositionV1


@pytest.mark.parametrize(
    ("group", "candidate_index", "expected_topic"),
    ((1, 0, "rag"), (1, 1, "ranking"),
     (2, 0, "ranking"), (2, 1, "fastapi"),
     (3, 0, "fastapi"), (3, 1, "rag")),
)
def test_gold_synthetic_evidence_supports_all_five_recruiter_uses(group, candidate_index, expected_topic):
    projection = build_comparison_group(group)["projections"][candidate_index]
    bundle = build_recruiter_propositions_v1(projection)
    roles = {role for proposition in bundle.propositions for role in proposition.allowed_fields}
    assert {"why_consider", "technical_signal", "interview_focus",
            "uncertainty", "decision_summary"} <= roles
    assert any(expected_topic in item.topic_terms for item in bundle.propositions)
    assert any(item.kind == "human_review_recommendation" for item in bundle.propositions)
    validate_recruiter_propositions_v1(bundle, projection=projection)


@pytest.mark.parametrize("group", (1, 2, 3))
def test_gold_candidate_a_and_b_have_distinct_evidence_bound_propositions(group):
    first, second = build_comparison_group(group)["projections"]
    a = build_recruiter_propositions_v1(first)
    b = build_recruiter_propositions_v1(second)
    a_topics = {term for item in a.propositions for term in item.topic_terms}
    b_topics = {term for item in b.propositions for term in item.topic_terms}
    assert a_topics != b_topics
    assert {item.proposition_id for item in a.propositions}.isdisjoint(
        item.proposition_id for item in b.propositions
    )
    assert {item.candidate_id for item in a.propositions} == {first.candidate_id}
    assert {item.candidate_id for item in b.propositions} == {second.candidate_id}


def test_every_proposition_traces_exactly_to_selected_facts_claims_and_evidence():
    projection = build_comparison_group(1)["projections"][0]
    fact_graph = build_atomic_fact_graph_v3(projection)
    claim_graph = build_recruiter_claim_graph_v4(fact_graph)
    facts = {item.fact_id: item for item in (*build_atomic_facts(projection), *fact_graph.facts)}
    claims = {item.claim_id: item for item in claim_graph.claims}
    result = build_recruiter_propositions_v1(projection)
    assert result.propositions
    assert result == build_recruiter_propositions_v1(projection)
    for proposition in result.propositions:
        assert set(proposition.source_fact_ids) <= facts.keys()
        assert set(proposition.source_claim_ids) <= claims.keys()
        expected_refs = {ref for fact_id in proposition.source_fact_ids
                         for ref in facts[fact_id].evidence_refs}
        assert set(proposition.evidence_refs) == expected_refs
        assert expected_refs <= projection.facts.keys()
        assert set(proposition.job_requirement_refs) == {
            ref for ref in expected_refs if ref.startswith("job_requirement:")
        }
        assert all(ref.startswith(f"candidate:{projection.result_rank}:")
                   for ref in expected_refs if ref.startswith("candidate:"))


def test_human_review_uses_both_alignment_and_interview_lineage():
    projection = build_comparison_group(1)["projections"][0]
    graph = build_recruiter_claim_graph_v4(build_atomic_fact_graph_v3(projection))
    claims = {item.claim_id: item for item in graph.claims}
    result = build_recruiter_propositions_v1(projection)
    review = next(item for item in result.propositions
                  if item.kind == "human_review_recommendation")
    source_types = {claims[claim_id].claim_type for claim_id in review.source_claim_ids}
    assert {"technical_alignment", "interview_focus", "review_recommendation"} <= source_types
    assert any(ref.startswith(f"candidate:{projection.result_rank}:") for ref in review.evidence_refs)
    assert review.job_requirement_refs


@pytest.mark.parametrize(
    ("group", "candidate_index", "expected_predicate"),
    ((1, 0, "prioritize_technical_review"), (1, 1, "consider_targeted_screen"),
     (2, 0, "prioritize_technical_review"), (2, 1, "consider_targeted_screen"),
     (3, 0, "prioritize_technical_review"), (3, 1, "prioritize_technical_review")),
)
def test_review_strength_uses_distinct_project_backed_job_requirements(
    group, candidate_index, expected_predicate,
):
    projection = build_comparison_group(group)["projections"][candidate_index]
    result = build_recruiter_propositions_v1(projection)
    reviews = [item for item in result.propositions if item.kind == "human_review_recommendation"]
    assert len(reviews) == 1
    assert reviews[0].predicate == expected_predicate
    validate_recruiter_propositions_v1(result, projection=projection)


def test_duplicate_generic_requirement_does_not_create_priority_review():
    projection = build_comparison_group(1)["projections"][1]
    python_requirement = next(ref for ref, terms in projection.facts.items()
                              if ref.startswith("job_requirement:") and "Python" in terms)
    repeated = replace(projection, facts={**projection.facts,
                                          "job_requirement:duplicate_python": projection.facts[python_requirement]},
                       positive_refs=projection.positive_refs | {"job_requirement:duplicate_python"})
    result = build_recruiter_propositions_v1(repeated)
    review = next(item for item in result.propositions
                  if item.kind == "human_review_recommendation")
    assert review.predicate == "consider_targeted_screen"


def test_proposition_build_does_not_change_ranking_snapshot():
    group = build_comparison_group(2)
    before = group["ranking_before"]
    for projection in group["projections"]:
        build_recruiter_propositions_v1(projection)
    run = group["run"]
    assert run.result_fingerprint == before["fingerprint"]
    assert [item.candidate_id for item in run.results] == before["order"]
    assert [item.ltr_score_raw for item in run.results] == before["ltr_scores"]


def test_no_observed_job_overlap_does_not_invent_why_consider_or_review_action():
    projection = _projection(technology="LambdaMART")
    unrelated = replace(
        projection,
        facts={**projection.facts, "job_requirement:technology": ("RAG",)},
    )
    result = build_recruiter_propositions_v1(unrelated)
    assert any(item.kind == "project_observation" for item in result.propositions)
    assert all(item.kind != "technical_alignment" for item in result.propositions)
    assert all(item.kind != "human_review_recommendation" for item in result.propositions)
    assert all("why_consider" not in item.allowed_fields for item in result.propositions)


def test_selected_listed_skill_remains_observable_without_a_job_overlap_claim():
    projection = _projection()
    skill_ref = "candidate:1:skill:docker"
    selected = replace(
        projection,
        facts={**projection.facts, skill_ref: ("Docker",)},
        positive_refs=projection.positive_refs | {skill_ref},
    )
    result = build_recruiter_propositions_v1(selected)
    skill = next(item for item in result.propositions
                 if item.kind == "listed_skill_observation" and "docker" in item.topic_terms)
    assert skill.evidence_refs == (skill_ref,)
    assert skill.source_fact_ids
    assert skill.source_claim_ids == ()
    assert skill.allowed_fields == ("technical_signal",)


def test_unrecognized_but_selected_project_technology_keeps_direct_fact_signal():
    projection = _projection(technology="Temporal")
    project_ref = "candidate:1:project:sample"
    selected = replace(projection, facts={**projection.facts, project_ref: ("Temporal",)})
    result = build_recruiter_propositions_v1(selected)
    project = next(item for item in result.propositions if item.kind == "project_observation")
    assert project.topic_terms == ("temporal",)
    assert project.evidence_refs == (project_ref,)
    assert project.source_claim_ids == ()
    alignment = next(item for item in result.propositions
                     if item.kind == "technical_alignment" and "temporal" in item.topic_terms)
    assert alignment.modality == "alignment"
    assert alignment.source_claim_ids == ()
    assert project_ref in alignment.evidence_refs
    assert "job_requirement:technology" in alignment.job_requirement_refs
    assert any(item.kind == "interview_target" and "temporal" in item.topic_terms
               for item in result.propositions)
    assert any(item.kind == "human_review_recommendation" and "temporal" in item.topic_terms
               for item in result.propositions)
    assert next(item.predicate for item in result.propositions
                if item.kind == "human_review_recommendation") == "consider_targeted_screen"
    validate_recruiter_propositions_v1(result, projection=selected)


def test_unknown_technology_exact_job_relation_does_not_use_substring_or_job_only():
    projection = _projection(technology="Temporal")
    project_ref = "candidate:1:project:sample"
    base = replace(projection, facts={**projection.facts, project_ref: ("Temporal",)})
    altered = replace(base, facts={**base.facts, "job_requirement:technology": ("TemporalDB",)})
    result = build_recruiter_propositions_v1(altered)
    assert not any(item.kind == "technical_alignment" and "temporal" in item.topic_terms
                   for item in result.propositions)
    no_candidate = replace(base, facts={**base.facts, project_ref: ("Unrelated",)})
    assert not any(item.kind == "technical_alignment" and "temporal" in item.topic_terms
                   for item in build_recruiter_propositions_v1(no_candidate).propositions)


def test_open_requirement_without_alias_remains_a_readable_unknown_not_candidate_deficit():
    projection = _projection(open_requirement=True)
    result = build_recruiter_propositions_v1(projection)
    unknown = next(item for item in result.propositions
                   if item.kind == "material_unknown" and "job_requirement:open" in item.evidence_refs)
    assert unknown.topic_terms == ("production operation",)
    assert unknown.modality == "unknown"
    assert unknown.polarity == "undetermined"
    assert "uncertainty" in unknown.allowed_fields
    assert "interview_focus" not in unknown.allowed_fields
    assert any(item.kind == "interview_target" and "job_requirement:open" in item.evidence_refs
               for item in result.propositions)


def test_foreign_candidate_evidence_is_rejected_instead_of_ignored():
    projection = _projection()
    foreign = "candidate:2:project:foreign"
    contaminated = replace(
        projection,
        facts={**projection.facts, foreign: ("RAG",)},
        positive_refs=projection.positive_refs | {foreign},
    )
    with pytest.raises(ValueError, match="candidate_evidence_owner_mismatch"):
        build_recruiter_propositions_v1(contaminated)


def test_public_evidence_entry_reuses_grounded_projection_and_rejects_cross_candidate_output():
    group = build_comparison_group(1)
    from_evidence = build_recruiter_propositions_from_evidence_v1(
        bundle=group["bundle"], source=group["outputs"][0],
    )
    assert from_evidence == build_recruiter_propositions_v1(group["projections"][0])
    foreign_identity = group["outputs"][0].model_copy(update={
        "candidate_id": group["outputs"][1].candidate_id,
        "result_rank": group["outputs"][1].result_rank,
    })
    with pytest.raises(ValueError):
        build_recruiter_propositions_from_evidence_v1(
            bundle=group["bundle"], source=foreign_identity,
        )


@pytest.mark.parametrize(
    ("kind", "mutation"),
    (
        ("technical_alignment", {"modality": "fact"}),
        ("technical_alignment", {"subject": "candidate"}),
        ("technical_alignment", {"predicate": "has_experience"}),
        ("project_observation", {"predicate": "owns_enterprise_platform"}),
        ("project_observation", {"predicate": "achieved_business_outcome"}),
        ("project_observation", {"predicate": "operated_at_production_scale"}),
        ("interview_target", {"modality": "fact"}),
        ("material_unknown", {"polarity": "negative"}),
        ("material_unknown", {"predicate": "lacks_skill"}),
        ("human_review_recommendation", {"predicate": "hire_candidate"}),
    ),
)
def test_forbidden_upgrades_cannot_be_encoded_as_a_valid_proposition(kind, mutation):
    result = build_recruiter_propositions_v1(_projection())
    original = next(item for item in result.propositions if item.kind == kind)
    with pytest.raises(ValidationError):
        RecruiterPropositionV1.model_validate({**original.model_dump(), **mutation})


def test_canonical_review_rejects_fabricated_topic_or_cross_candidate_proposition():
    projection = _projection()
    result = build_recruiter_propositions_v1(projection)
    first = result.propositions[0]
    fabricated = first.model_copy(update={"topic_terms": ("unseen_technology",)})
    changed = result.model_copy(update={"propositions": (fabricated, *result.propositions[1:])})
    with pytest.raises(ValueError, match="noncanonical_recruiter_propositions"):
        validate_recruiter_propositions_v1(changed, projection=projection)
    other = build_recruiter_propositions_v1(_projection(candidate_id="candidate-b", rank=2))
    foreign = result.model_copy(update={"propositions": (other.propositions[0], *result.propositions[1:])})
    with pytest.raises(ValueError, match="noncanonical_recruiter_propositions"):
        validate_recruiter_propositions_v1(foreign, projection=projection)
