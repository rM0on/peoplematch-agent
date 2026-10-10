"""Bounded claim-to-graph validation, not general-language entailment."""

from __future__ import annotations

import re

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_v3 import RecruiterNarrativeV3
from app.services.explanation.presentation.facts_v3 import (
    AtomicFactGraphV3, _concepts, build_atomic_fact_graph_v3,
)
from app.services.explanation.presentation.validator_v2 import NarrativeV2ValidationError, _check_section
from app.services.explanation.presentation.validator_v2 import _ASSERTED_RESPONSIBILITY, _UNKNOWN_SCOPE
from app.services.explanation.presentation.validator_v2_2 import _OTHER_CANDIDATE, _UNSUPPORTED_PERSONAL
from app.services.explanation.presentation.validator_v2_1 import (
    _unsupported_personal_work, _unsupported_production_claim,
)
from app.services.explanation.presentation.validator_v2_3 import _ABSTRACT


class NarrativeV3ValidationError(ValueError):
    def __init__(self) -> None:
        super().__init__("Recruiter narrative V3 claim validation failed")


_SAME_PROJECT = re.compile(r"同一项目|单个项目|一个项目(?:中|里|同时)")
_PRESUPPOSED_ACTION = re.compile(
    r"在(?:构建|开发|设计|部署|实现)[^。？?]{0,60}时[，,]?您|"
    r"(?:您|你)(?:曾|已|在[^，。？?]{0,30})?(?:构建|开发|设计|部署|实现)了"
)


def _supported_graph_relation(claim_type: str, ids: list[str], graph: AtomicFactGraphV3) -> bool:
    lookup = {fact.fact_id: fact for fact in graph.facts}
    selected = [lookup[ident] for ident in ids]
    kinds = {fact.kind for fact in selected}
    alignment_has_source = any(
        fact.kind == "job_alignment" and any(
            edge.target_id == fact.fact_id and lookup[edge.source_id].kind in {
                "project_evidence", "candidate_capability", "candidate_portfolio_scope",
            }
            for edge in graph.edges
        )
        for fact in selected
    )
    required = {
        "evidence_statement": bool(kinds & {"candidate_capability", "project_evidence",
                                                "technical_scope", "candidate_portfolio_scope"}),
        "capability_inference": "job_alignment" in kinds and alignment_has_source,
        "interview_validation": "interview_validation" in kinds,
        "uncertainty_statement": bool(kinds & {"interview_validation", "open_requirement",
                                                "open_requirement_group"}),
    }
    if not required.get(claim_type, False):
        return False
    if len(ids) == 1:
        return True
    links: dict[str, set[str]] = {fact.fact_id: set() for fact in graph.facts}
    for edge in graph.edges:
        links[edge.source_id].add(edge.target_id)
        links[edge.target_id].add(edge.source_id)
    seen = {ids[0]}
    pending = [ids[0]]
    while pending:
        current = pending.pop()
        for neighbor in links[current] - seen:
            seen.add(neighbor)
            pending.append(neighbor)
    return set(ids) <= seen


def diagnose_narrative_v3_sections(narrative: RecruiterNarrativeV3, *,
                                   projection: NarrativeProjection) -> dict[str, str]:
    graph = build_atomic_fact_graph_v3(projection)
    lookup = {fact.fact_id: fact for fact in graph.facts}
    sections = [
        ("decision_summary", narrative.decision_summary, {"capability_inference", "uncertainty_statement"}),
        *((f"strengths[{i}]", item, {"evidence_statement", "capability_inference"})
          for i, item in enumerate(narrative.strengths)),
        *((f"risks[{i}]", item, {"uncertainty_statement"}) for i, item in enumerate(narrative.risks)),
        *((f"interview_focus[{i}]", item, {"interview_validation"})
          for i, item in enumerate(narrative.interview_focus)),
    ]
    invalid: dict[str, str] = {}
    for label, item, allowed_types in sections:
        try:
            if item.claim_type not in allowed_types:
                invalid[label] = "claim_type_mismatch"
                continue
            if len(item.fact_ids) != len(set(item.fact_ids)):
                invalid[label] = "duplicate_fact_id"
                continue
            if any(ident not in lookup for ident in item.fact_ids):
                invalid[label] = "unknown_or_foreign_fact_id"
                continue
            if not _supported_graph_relation(item.claim_type, item.fact_ids, graph):
                invalid[label] = "unsupported_graph_relation"
                continue
            if not item.fact_ids:
                raise NarrativeV3ValidationError()
            selected = [lookup[ident] for ident in item.fact_ids]
            project_refs = {ref for fact in selected for ref in fact.evidence_refs
                            if ref.startswith(f"candidate:{projection.result_rank}:project:")}
            if "项目" in item.text and not project_refs:
                invalid[label] = "project_claim_without_project_source"
                continue
            if len(project_refs) > 1 and _SAME_PROJECT.search(item.text):
                invalid[label] = "cross_project_conflation"
                continue
            cautious = item.claim_type in {"interview_validation", "uncertainty_statement"}
            safe_unknown_scope = (cautious and (
                                      _UNKNOWN_SCOPE.search(item.text)
                                      or re.search(r"是否(?:曾|具体)?负责", item.text)
                                  )
                                  and not _ASSERTED_RESPONSIBILITY.search(item.text))
            if (_ABSTRACT.search(item.text) or _OTHER_CANDIDATE.search(item.text)
                    or _PRESUPPOSED_ACTION.search(item.text)
                    or (_UNSUPPORTED_PERSONAL.search(item.text) and not safe_unknown_scope)
                    or _unsupported_personal_work(item.text)
                    or _unsupported_production_claim(item.text)):
                invalid[label] = "unsafe_or_abstract_assertion"
                continue
            try:
                _check_section((item.text,), item.fact_ids, facts=lookup, cautious=cautious,
                               job_role=projection.role_title, allow_unknown_scale=True)
            except NarrativeV2ValidationError:
                invalid[label] = "surface_or_caution_violation"
                continue
            if item.claim_type != "uncertainty_statement":
                concepts = {concept.casefold() for fact in selected for concept in fact.concepts}
                if not concepts.intersection(_concepts((item.text,))):
                    invalid[label] = "missing_cited_concept"
        except (KeyError, NarrativeV2ValidationError, NarrativeV3ValidationError):
            invalid[label] = "claim_validation_failed"
    if narrative.decision == "prioritize_review":
        selected = [lookup[ident] for ident in narrative.decision_summary.fact_ids if ident in lookup]
        project_alignment = any(
            fact.kind == "job_alignment" and set(fact.concepts) - {"python"} and any(
                edge.target_id == fact.fact_id
                and lookup[edge.source_id].kind in {"project_evidence", "candidate_portfolio_scope"}
                and any(scope.kind == "technical_scope" and scope.evidence_refs == lookup[edge.source_id].evidence_refs
                        for scope in graph.facts)
                for edge in graph.edges
            ) for fact in selected
        )
        if not (narrative.decision_summary.claim_type == "capability_inference"
                and any(f.kind == "job_alignment" and set(f.concepts) - {"python"} for f in selected)
                and (any(f.kind in {"technical_scope", "candidate_portfolio_scope"} for f in selected)
                     or project_alignment)):
            invalid["decision"] = "priority_without_specific_alignment"
    return invalid


def invalid_narrative_v3_sections(narrative: RecruiterNarrativeV3, *,
                                  projection: NarrativeProjection) -> tuple[str, ...]:
    return tuple(diagnose_narrative_v3_sections(narrative, projection=projection))


def validate_narrative_v3_projection(narrative: RecruiterNarrativeV3, *,
                                     projection: NarrativeProjection) -> None:
    if (narrative.candidate_id != projection.candidate_id
            or narrative.result_rank != projection.result_rank
            or invalid_narrative_v3_sections(narrative, projection=projection)):
        raise NarrativeV3ValidationError()


__all__ = ["NarrativeV3ValidationError", "invalid_narrative_v3_sections",
           "diagnose_narrative_v3_sections",
           "validate_narrative_v3_projection"]
