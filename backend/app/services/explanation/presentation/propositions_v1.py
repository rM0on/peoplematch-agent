"""Deterministic semantic propositions over selected, validated explanation evidence.

This module does not inspect generated prose. It records what evidence can support
before language generation and remains independent of ranking and provider calls.
"""

from __future__ import annotations

from app.schemas.explanations import CandidateExplanationOutput, InternalEvidenceBundleV1
from app.services.explanation.presentation.adapter import NarrativeProjection, build_narrative_projection
from app.services.explanation.presentation.claims_v4 import build_recruiter_claim_graph_v4
from app.services.explanation.presentation.contracts_proposition_v1 import (
    PredicateV1, PropositionKindV1, RecruiterPropositionSetV1, RecruiterPropositionV1,
    proposition_semantics_v1,
)
from app.services.explanation.presentation.facts_v2 import (
    build_atomic_facts, build_selected_requirement_verification_facts,
)
from app.services.explanation.presentation.facts_v3 import _concepts, build_atomic_fact_graph_v3
from app.services.match_runs.contracts import canonical_fingerprint


def build_recruiter_propositions_from_evidence_v1(
    *, bundle: InternalEvidenceBundleV1, source: CandidateExplanationOutput,
) -> RecruiterPropositionSetV1:
    """Safe entry: reuse the existing ownership/reference checks before projection."""
    return build_recruiter_propositions_v1(build_narrative_projection(bundle=bundle, source=source))


def _check_projection(projection: NarrativeProjection) -> None:
    if not projection.candidate_id or projection.result_rank < 1:
        raise ValueError("invalid_candidate_identity")
    selected = projection.positive_refs | projection.risk_refs | projection.interview_refs
    if not selected <= projection.facts.keys():
        raise ValueError("selected_evidence_missing_from_projection")
    owner = f"candidate:{projection.result_rank}:"
    for ref in projection.facts:
        if ref.startswith("candidate:") and not ref.startswith(owner):
            raise ValueError("candidate_evidence_owner_mismatch")
        if not ref.startswith((owner, "job_requirement:")):
            raise ValueError("unsupported_evidence_reference_namespace")
    if not any(ref.startswith(owner) for ref in projection.positive_refs):
        raise ValueError("candidate_positive_evidence_missing")
    if not any(ref.startswith("job_requirement:") for ref in projection.positive_refs):
        raise ValueError("job_requirement_evidence_missing")


def build_recruiter_propositions_v1(projection: NarrativeProjection) -> RecruiterPropositionSetV1:
    """Rebuild V3/V4 provenance; never infer personal ability, duty, scale or impact."""
    return _build_recruiter_propositions_v1(projection, include_interview_requirements=False)


def build_recruiter_propositions_for_interview_v1(
    projection: NarrativeProjection,
) -> RecruiterPropositionSetV1:
    """Experimental, additive JD-verification view; the historical builder stays exact."""
    return _build_recruiter_propositions_v1(projection, include_interview_requirements=True)


def _build_recruiter_propositions_v1(
    projection: NarrativeProjection, *, include_interview_requirements: bool,
) -> RecruiterPropositionSetV1:
    _check_projection(projection)
    atomic_facts = build_atomic_facts(projection)
    requirement_sources = (build_selected_requirement_verification_facts(projection)
                           if include_interview_requirements else ())
    fact_graph = build_atomic_fact_graph_v3(projection)
    claim_graph = build_recruiter_claim_graph_v4(fact_graph)
    facts = {fact.fact_id: fact for fact in (*atomic_facts, *requirement_sources, *fact_graph.facts)}
    claims = {claim.claim_id: claim for claim in claim_graph.claims}
    propositions: dict[str, RecruiterPropositionV1] = {}

    def add(kind: PropositionKindV1, predicate: PredicateV1, topics: tuple[str, ...],
            fact_ids: tuple[str, ...], claim_ids: tuple[str, ...]) -> None:
        selected_facts = tuple(sorted(set(fact_ids)))
        selected_claims = tuple(sorted(set(claim_ids)))
        if not topics or not selected_facts:
            raise ValueError("proposition_support_missing")
        if any(ref not in facts for ref in selected_facts):
            raise ValueError("proposition_source_fact_missing")
        if any(ref not in claims or claims[ref].candidate_id != projection.candidate_id
               for ref in selected_claims):
            raise ValueError("proposition_source_claim_owner_mismatch")
        evidence_refs = tuple(sorted({ref for fact_id in selected_facts
                                      for ref in facts[fact_id].evidence_refs}))
        if not set(evidence_refs) <= projection.facts.keys():
            raise ValueError("proposition_evidence_outside_projection")
        requirement_refs = tuple(ref for ref in evidence_refs if ref.startswith("job_requirement:"))
        requirement_terms = tuple(sorted({term for ref in requirement_refs
                                          for term in projection.facts[ref]}, key=str.casefold))
        subject, modality, polarity, fields = proposition_semantics_v1(kind, predicate)
        topics = tuple(sorted(set(topics), key=str.casefold))
        proposition_id = "proposition:" + canonical_fingerprint({
            "version": "1", "candidate": projection.candidate_id, "rank": projection.result_rank,
            "kind": kind, "predicate": predicate, "topics": topics,
            "facts": selected_facts, "claims": selected_claims, "evidence": evidence_refs,
        })[:32]
        propositions[proposition_id] = RecruiterPropositionV1(
            proposition_id=proposition_id,
            candidate_id=projection.candidate_id,
            result_rank=projection.result_rank,
            kind=kind, subject=subject, predicate=predicate,
            modality=modality, polarity=polarity,
            topic_terms=topics, job_requirement_terms=requirement_terms,
            source_fact_ids=selected_facts, source_claim_ids=selected_claims,
            evidence_refs=evidence_refs, job_requirement_refs=requirement_refs,
            allowed_fields=fields,
        )

    # Direct observations must not disappear merely because V3's closed alias
    # vocabulary or V4's job-overlap claims do not recognize a source term.
    def source_topics(terms: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(topic for term in terms for topic in (_concepts((term,)) or (term.strip().casefold(),)))

    projects: dict[str, list] = {}
    for fact in atomic_facts:
        if fact.kind == "candidate_skill":
            add("listed_skill_observation", "lists_skill", source_topics((fact.term,)),
                (fact.fact_id,), ())
        elif fact.kind == "project_practice":
            for ref in fact.evidence_refs:
                projects.setdefault(ref, []).append(fact)
    for project_facts in projects.values():
        add("project_observation", "lists_project_technologies",
            source_topics(tuple(fact.term for fact in project_facts)),
            tuple(fact.fact_id for fact in project_facts), ())

    for claim in claim_graph.claims:
        if claim.claim_type in {"technical_alignment", "skill_requirement_match"}:
            add("technical_alignment", "overlaps_job_requirement", claim.concepts,
                claim.source_fact_ids, (claim.claim_id,))
        elif claim.claim_type == "interview_focus":
            predicate: PredicateV1 = (
                "verify_open_requirement" if claim.relation_type == "open_requirement"
                else "verify_project_scope"
            )
            topics = claim.concepts or tuple(term for source in claim.source_fact_ids
                                              for term in facts[source].source_terms)
            add("interview_target", predicate, topics, claim.source_fact_ids, (claim.claim_id,))
            if claim.relation_type == "open_requirement":
                add("material_unknown", "requirement_evidence_not_established", topics,
                    claim.source_fact_ids, (claim.claim_id,))
        elif claim.claim_type == "project_depth_validation":
            add("material_unknown", "project_scope_not_established", claim.concepts,
                claim.source_fact_ids, (claim.claim_id,))

    # V3/V4 deliberately use a closed alias vocabulary. An exact V2
    # candidate/job relation remains valid even when the alias is unknown.
    # Do not infer synonyms, capability, responsibility, or project depth.
    fallback_alignments = []
    for relation in atomic_facts:
        if relation.kind != "requirement_alignment" or _concepts((relation.term,)):
            continue
        candidate_ref = next((ref for ref in relation.evidence_refs
                              if ref.startswith(f"candidate:{projection.result_rank}:")), None)
        if candidate_ref is None:
            continue
        direct = next((fact for fact in atomic_facts
                       if fact.kind in {"candidate_skill", "project_practice"}
                       and fact.term == relation.term and fact.evidence_refs == (candidate_ref,)), None)
        if direct is None:
            raise ValueError("exact_alignment_candidate_source_missing")
        topic = source_topics((relation.term,))
        add("technical_alignment", "overlaps_job_requirement", topic,
            (relation.fact_id, direct.fact_id), ())
        if direct.kind == "project_practice":
            add("interview_target", "verify_project_scope", topic, (direct.fact_id,), ())
            add("material_unknown", "project_scope_not_established", topic, (direct.fact_id,), ())
            fallback_alignments.append((relation, direct, topic))

    # A selected JD requirement without an observed candidate relation is an
    # interview target, not evidence that the candidate lacks the requirement.
    if include_interview_requirements:
        aligned_requirements = {
            ref for item in propositions.values() if item.kind == "technical_alignment"
            for ref in item.job_requirement_refs
        }
        existing_open_requirements = {
            ref for item in propositions.values() if item.predicate == "verify_open_requirement"
            for ref in item.job_requirement_refs
        }
        for source in requirement_sources:
            requirement_ref = source.evidence_refs[0]
            if requirement_ref in aligned_requirements or requirement_ref in existing_open_requirements:
                continue
            add("interview_target", "verify_open_requirement", source_topics((source.term,)),
                (source.fact_id,), ())

    # Priority is a hiring-action strength, not a consequence of merely having
    # one shared technology. Count distinct selected JD requirements supported
    # by project evidence; never use LTR score or candidate rank here.
    project_backed_pairs = {
        (requirement_ref, topic)
        for item in propositions.values() if item.kind == "technical_alignment"
        and any(":project:" in ref or ":project_evidence:" in ref for ref in item.evidence_refs)
        for requirement_ref in item.job_requirement_refs
        for topic in set(item.topic_terms) & set(source_topics(projection.facts[requirement_ref]))
    }
    project_backed_requirements = {ref for ref, _ in project_backed_pairs}
    project_backed_topics = {topic for _, topic in project_backed_pairs}
    review_predicate: PredicateV1 = (
        "prioritize_technical_review" if len(project_backed_requirements) >= 2
        and len(project_backed_topics) >= 2
        else "consider_targeted_screen"
    )

    # Many V4 review claims can describe one hiring action. Merge their verified
    # lineage into one proposition; this never turns a technical overlap into hiring.
    reviews = [claim for claim in claim_graph.claims if claim.claim_type == "review_recommendation"]
    if reviews:
        lineage = {claim.claim_id: claim for claim in reviews}
        for review in reviews:
            for parent_id in review.source_claim_ids:
                parent = claims.get(parent_id)
                if parent is None or parent.candidate_id != projection.candidate_id:
                    raise ValueError("review_claim_parent_missing")
                lineage[parent_id] = parent
        alignments = [claim for claim in lineage.values()
                      if claim.claim_type in {"technical_alignment", "skill_requirement_match"}]
        focuses = [claim for claim in lineage.values() if claim.claim_type == "interview_focus"]
        if not alignments or not focuses:
            raise ValueError("review_claim_lineage_incomplete")
        add("human_review_recommendation", review_predicate,
            tuple(topic for claim in alignments for topic in claim.concepts),
            tuple(fact_id for claim in lineage.values() for fact_id in claim.source_fact_ids),
            tuple(lineage),
        )
    for relation, direct, topic in fallback_alignments:
        add("human_review_recommendation", review_predicate, topic,
            (relation.fact_id, direct.fact_id), ())
    return RecruiterPropositionSetV1(
        contract_version="recruiter_proposition_v1",
        candidate_id=projection.candidate_id,
        result_rank=projection.result_rank,
        propositions=tuple(sorted(propositions.values(), key=lambda item: item.proposition_id)),
    )


def validate_recruiter_propositions_v1(
    result: RecruiterPropositionSetV1, *, projection: NarrativeProjection,
) -> None:
    if result != build_recruiter_propositions_v1(projection):
        raise ValueError("noncanonical_recruiter_propositions")


def validate_interview_recruiter_propositions_v1(
    result: RecruiterPropositionSetV1, *, projection: NarrativeProjection,
) -> None:
    if result != build_recruiter_propositions_for_interview_v1(projection):
        raise ValueError("noncanonical_interview_recruiter_propositions")


__all__ = ["build_recruiter_propositions_from_evidence_v1", "build_recruiter_propositions_v1",
           "validate_recruiter_propositions_v1", "build_recruiter_propositions_for_interview_v1",
           "validate_interview_recruiter_propositions_v1"]
