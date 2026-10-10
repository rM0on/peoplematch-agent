"""Deterministic, per-candidate recruiter claims over the frozen V3 fact graph."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.explanation.presentation.contracts_v4 import RecruiterClaimV1
from app.services.explanation.presentation.facts_v3 import AtomicFactGraphV3
from app.services.match_runs.contracts import canonical_fingerprint


_FORBIDDEN = ("personal_ownership", "production_scale", "business_outcome",
              "ability_grade", "hiring_decision")


@dataclass(frozen=True)
class RecruiterClaimGraphV4:
    candidate_id: str
    result_rank: int
    fact_graph: AtomicFactGraphV3
    claims: tuple[RecruiterClaimV1, ...]


def _claim(graph: AtomicFactGraphV3, claim_type: str, relation: str, scope: str,
           sources: tuple[str, ...], concepts: tuple[str, ...],
           parents: tuple[str, ...] = ()) -> RecruiterClaimV1:
    sources = tuple(sorted(set(sources)))
    concepts = tuple(sorted(set(concepts)))
    parents = tuple(sorted(set(parents)))
    return RecruiterClaimV1(
        claim_id="claim:" + canonical_fingerprint({
            "version": "4", "candidate": graph.candidate_id, "rank": graph.result_rank,
            "type": claim_type, "relation": relation, "sources": sources,
            "concepts": concepts, "parents": parents,
        })[:32],
        candidate_id=graph.candidate_id, claim_type=claim_type,
        source_fact_ids=sources, relation_type=relation,
        allowed_expression_scope=scope, forbidden_expression_scope=_FORBIDDEN,
        concepts=concepts, source_claim_ids=parents,
    )


def build_recruiter_claim_graph_v4(graph: AtomicFactGraphV3) -> RecruiterClaimGraphV4:
    """Only observed V3 edges may produce claim relations; no provider input is accepted."""
    facts = {fact.fact_id: fact for fact in graph.facts}
    claims: dict[str, RecruiterClaimV1] = {}
    alignments: list[RecruiterClaimV1] = []
    focuses: list[RecruiterClaimV1] = []

    for edge in graph.edges:
        source = facts.get(edge.source_id)
        target = facts.get(edge.target_id)
        if source is None or target is None:
            continue
        if (edge.relation == "observed_requirement_overlap"
                and target.kind == "job_alignment"
                and source.kind in {"project_evidence", "candidate_capability"}):
            kind = "technical_alignment" if source.kind == "project_evidence" else "skill_requirement_match"
            scope = "technical_direction" if source.kind == "project_evidence" else "skill_observation"
            relation = edge.relation if source.kind == "project_evidence" else "listed_skill_overlap"
            for concept in target.concepts:
                claim = _claim(graph, kind, relation, scope,
                               (source.fact_id, target.fact_id), (concept,))
                claims[claim.claim_id] = claim
                if kind == "technical_alignment":
                    alignments.append(claim)
        elif (edge.relation == "verify_observed_scope"
              and source.kind == "project_evidence" and target.kind == "interview_validation"):
            depth = _claim(graph, "project_depth_validation", edge.relation,
                           "project_verification", (source.fact_id, target.fact_id), target.concepts)
            focus = _claim(graph, "interview_focus", edge.relation,
                           "project_verification", (source.fact_id, target.fact_id), target.concepts)
            claims[depth.claim_id] = depth
            claims[focus.claim_id] = focus
            focuses.append(focus)

    for fact in facts.values():
        if fact.kind == "open_requirement":
            claim = _claim(graph, "interview_focus", "open_requirement", "open_question",
                           (fact.fact_id,), fact.concepts)
            claims[claim.claim_id] = claim
            focuses.append(claim)

    for alignment in alignments:
        for focus in focuses:
            if focus.relation_type == "open_requirement" or set(alignment.concepts) & set(focus.concepts):
                review = _claim(
                    graph, "review_recommendation", "alignment_plus_interview_focus",
                    "human_review", alignment.source_fact_ids,
                    tuple(sorted(set(alignment.concepts) | set(focus.concepts))),
                    (alignment.claim_id, focus.claim_id),
                )
                claims[review.claim_id] = review
    return RecruiterClaimGraphV4(graph.candidate_id, graph.result_rank, graph,
                                 tuple(sorted(claims.values(), key=lambda item: item.claim_id)))


__all__ = ["RecruiterClaimGraphV4", "build_recruiter_claim_graph_v4"]
