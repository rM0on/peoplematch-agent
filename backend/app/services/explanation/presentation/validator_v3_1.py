"""Validate V3.1 hiring-claim semantics against the existing per-candidate fact graph."""

from __future__ import annotations

import re

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_v3_1 import RecruiterNarrativeV3_1
from app.services.explanation.presentation.facts_v3 import _concepts, build_atomic_fact_graph_v3
from app.services.explanation.presentation.validator_v2 import NarrativeV2ValidationError, _check_section
from app.services.explanation.presentation.validator_v2_1 import (
    _unsupported_personal_work, _unsupported_production_claim,
)
from app.services.explanation.presentation.validator_v2_2 import _OTHER_CANDIDATE, _UNSUPPORTED_PERSONAL
from app.services.explanation.presentation.validator_v2_3 import _ABSTRACT
from app.services.explanation.presentation.validator_v3 import (
    _PRESUPPOSED_ACTION, _SAME_PROJECT, _supported_graph_relation,
)


class NarrativeV3_1ValidationError(ValueError):
    def __init__(self) -> None:
        super().__init__("Recruiter narrative V3.1 claim validation failed")


# These are semantic overclaims, not accepted-sentence templates. Surface wording remains free.
_ABILITY_CONCLUSION = re.compile(
    r"(?:候选人|其)[^。；？?]{0,50}(?:具备|掌握|胜任|符合|满足|证明)[^。；？?]{0,50}"
    r"(?:能力|经验|岗位|要求|专家|水平)|"
    r"(?:高度匹配|完全符合|符合岗位要求|已经具备岗位所需)"
)
_HIRING_OUTCOME = re.compile(
    r"(?:推荐|建议)(?:直接)?录用|直接进入终面|无需(?:人工|进一步)复核|"
    r"(?:大概率|很可能)(?:通过|录用)|录用概率|匹配百分比"
)
_PERSONAL_OWNERSHIP = re.compile(
    r"(?:候选人|其)(?:曾|已)?[^。；？?]{0,35}(?:负责|主导|建设|搭建|交付|上线|开发了|实现了)"
)
_PRODUCTION_SCALE = re.compile(r"企业级|百万|千万|亿级|大规模|生产级")
_CAUTIOUS_SCALE = re.compile(r"需|待|尚未|未体现|未说明|确认|核实|了解|验证|是否|建议")
_REVIEW_ACTION = re.compile(r"建议|可(?:优先)?(?:安排|进入)|复核|人工评估")
_INTERVIEW_ACTION = re.compile(r"面试|下一轮|确认|核实|了解|验证|询问|[？?]")


def diagnose_narrative_v3_1_sections(
    narrative: RecruiterNarrativeV3_1, *, projection: NarrativeProjection,
) -> dict[str, str]:
    graph = build_atomic_fact_graph_v3(projection)
    lookup = {fact.fact_id: fact for fact in graph.facts}
    sections = [
        ("decision_summary", narrative.decision_summary, {"review_recommendation"}),
        *((f"strengths[{i}]", item, {"evidence_summary", "job_alignment_observation"})
          for i, item in enumerate(narrative.strengths)),
        *((f"risks[{i}]", item, {"interview_validation"}) for i, item in enumerate(narrative.risks)),
        *((f"interview_focus[{i}]", item, {"interview_validation"})
          for i, item in enumerate(narrative.interview_focus)),
    ]
    relation = {
        "evidence_summary": "evidence_statement",
        "job_alignment_observation": "capability_inference",
        "interview_validation": "interview_validation",
        "review_recommendation": "capability_inference",
    }
    invalid: dict[str, str] = {}
    for label, item, allowed_types in sections:
        ids = item.fact_ids
        if item.claim_type not in allowed_types:
            invalid[label] = "claim_type_mismatch"
            continue
        if len(ids) != len(set(ids)) or any(ident not in lookup for ident in ids):
            invalid[label] = "unknown_or_duplicate_fact_id"
            continue
        if not _supported_graph_relation(relation[item.claim_type], ids, graph):
            invalid[label] = "unsupported_graph_relation"
            continue
        selected = [lookup[ident] for ident in ids]
        text = item.text
        project_refs = {ref for fact in selected for ref in fact.evidence_refs
                        if ref.startswith(f"candidate:{projection.result_rank}:project:")}
        cautious = item.claim_type == "interview_validation"
        if ("项目" in text and not project_refs or len(project_refs) > 1 and _SAME_PROJECT.search(text)
                or _OTHER_CANDIDATE.search(text) or _ABSTRACT.search(text)
                or _HIRING_OUTCOME.search(text) or _PRESUPPOSED_ACTION.search(text)
                or _UNSUPPORTED_PERSONAL.search(text) and not cautious
                or _PERSONAL_OWNERSHIP.search(text) and not cautious
                or _unsupported_personal_work(text) and not cautious
                or _unsupported_production_claim(text)
                or _PRODUCTION_SCALE.search(text) and not (cautious and _CAUTIOUS_SCALE.search(text))):
            invalid[label] = "unsafe_assertion"
            continue
        if item.claim_type in {"evidence_summary", "job_alignment_observation"} and _ABILITY_CONCLUSION.search(text):
            invalid[label] = "ability_conclusion_from_evidence"
            continue
        if label.startswith("interview_focus") and not _INTERVIEW_ACTION.search(text):
            invalid[label] = "interview_action_missing"
            continue
        if item.claim_type == "review_recommendation" and not _REVIEW_ACTION.search(text):
            invalid[label] = "review_action_missing"
            continue
        try:
            _check_section((text,), ids, facts=lookup, cautious=cautious,
                           job_role=projection.role_title, allow_unknown_scale=True)
        except NarrativeV2ValidationError:
            invalid[label] = "unsupported_surface_or_caution"
            continue
        if item.claim_type != "review_recommendation":
            concepts = {concept for fact in selected for concept in fact.concepts}
            if concepts and not concepts.intersection(_concepts((text,))):
                invalid[label] = "missing_cited_concept"
    if narrative.decision == "prioritize_review":
        selected = [lookup[ident] for ident in narrative.decision_summary.fact_ids if ident in lookup]
        if not any(fact.kind == "job_alignment" and set(fact.concepts) - {"python"}
                   and any(edge.target_id == fact.fact_id and lookup[edge.source_id].kind == "project_evidence"
                           for edge in graph.edges) for fact in selected):
            invalid["decision"] = "priority_without_project_alignment"
    return invalid


def invalid_narrative_v3_1_sections(
    narrative: RecruiterNarrativeV3_1, *, projection: NarrativeProjection,
) -> tuple[str, ...]:
    return tuple(diagnose_narrative_v3_1_sections(narrative, projection=projection))


def validate_narrative_v3_1_projection(
    narrative: RecruiterNarrativeV3_1, *, projection: NarrativeProjection,
) -> None:
    if (narrative.candidate_id != projection.candidate_id
            or narrative.result_rank != projection.result_rank
            or invalid_narrative_v3_1_sections(narrative, projection=projection)):
        raise NarrativeV3_1ValidationError()


__all__ = ["NarrativeV3_1ValidationError", "diagnose_narrative_v3_1_sections",
           "invalid_narrative_v3_1_sections", "validate_narrative_v3_1_projection"]
