"""Opt-in short triage task over existing RecruiterProposition semantics.

This is an experimental request adapter, not a new proposition or runtime
layer. Final prose remains model-generated and requires independent review.
"""

from __future__ import annotations

import json

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_proposition_v1 import (
    RecruiterPropositionSetV1, RecruiterPropositionV1,
)
from app.services.explanation.presentation.generation_proposition_v1 import (
    FIELDS, PropositionProviderOutputV1, ResolvedPropositionNarrativeV1,
    build_proposition_response_schema_v1, resolve_proposition_output_v1,
)
from app.services.explanation.presentation.propositions_v1 import validate_recruiter_propositions_v1
from app.services.explanation.presentation.semantic_intent_proposition_v1 import (
    FieldSemanticIntentV1, SemanticIntentPlanV1, build_semantic_intent_binding_v1,
)


_ROLES = {
    "decision_summary": ("human_review_action", "action_not_hiring_decision"),
    "why_consider": ("reason_to_explore", "relation_not_experience_or_capability"),
    "technical_signal": ("material_technical_signal", "material_observation_not_personal_action"),
    "interview_focus": ("nonpresupposing_interview_target", "question_not_assumed_responsibility"),
    "uncertainty": ("material_uncertainty", "unknown_not_candidate_deficiency"),
}


def _project_backed(item: RecruiterPropositionV1) -> bool:
    return any(":project:" in ref or ":project_evidence:" in ref for ref in item.evidence_refs)


def _selected(propositions: RecruiterPropositionSetV1) -> dict[str, RecruiterPropositionV1]:
    items = propositions.propositions
    reviews = [item for item in items if item.kind == "human_review_recommendation"]
    alignments = [item for item in items if item.kind == "technical_alignment"]
    observations = [item for item in items if item.kind in {"project_observation", "listed_skill_observation"}]
    unknowns = [item for item in items if item.kind == "material_unknown"]
    targets = [item for item in items if item.kind == "interview_target"
               and item.predicate == "verify_project_scope"]
    if not all((reviews, alignments, observations, unknowns, targets)):
        raise ValueError("triage_source_coverage_missing")

    review = min(reviews, key=lambda item: (
        item.predicate != "prioritize_technical_review", -len(item.job_requirement_refs), item.proposition_id))
    alignment = min(alignments, key=lambda item: (
        not _project_backed(item), -len(item.job_requirement_refs), item.proposition_id))
    observation = min(observations, key=lambda item: (
        item.kind != "project_observation", -len(set(item.topic_terms) & set(alignment.topic_terms)),
        item.proposition_id))
    unknown = min(unknowns, key=lambda item: (
        item.predicate != "project_scope_not_established", item.proposition_id))
    aligned_terms = {term.casefold() for term in alignment.topic_terms}
    target_candidates = [item for item in targets if aligned_terms & {term.casefold() for term in item.topic_terms}]
    if not target_candidates:
        raise ValueError("triage_job_related_first_check_missing")
    target = min(target_candidates, key=lambda item: (
        -len(aligned_terms & {term.casefold() for term in item.topic_terms}), item.proposition_id))
    return {
        "decision_summary": review, "why_consider": alignment,
        "technical_signal": observation, "interview_focus": target, "uncertainty": unknown,
    }


def build_triage_intent_plan_v1(
    projection: NarrativeProjection, propositions: RecruiterPropositionSetV1,
) -> SemanticIntentPlanV1:
    """Select one existing semantic commitment per field; create no facts."""
    validate_recruiter_propositions_v1(propositions, projection=projection)
    chosen = _selected(propositions)
    fields = []
    for name in FIELDS:
        item = chosen[name]
        if name not in item.allowed_fields:
            raise ValueError("triage_proposition_field_mismatch")
        goal, boundary = _ROLES[name]
        strength = None
        if name == "decision_summary":
            strength = ("priority_human_review" if item.predicate == "prioritize_technical_review"
                        else "conditional_targeted_screen")
        fields.append(FieldSemanticIntentV1(
            name=name, goal=goal, boundary=boundary,
            proposition_ids=(item.proposition_id,), recommendation_strength=strength,
        ))
    return SemanticIntentPlanV1(
        contract_version="recruiter_semantic_intent_v1",
        candidate_id=propositions.candidate_id, result_rank=propositions.result_rank,
        fields=tuple(fields),
    )


def _first_check_topic(
    projection: NarrativeProjection, alignment: RecruiterPropositionV1,
    target: RecruiterPropositionV1,
) -> str:
    if not ({term.casefold() for term in alignment.topic_terms}
            & {term.casefold() for term in target.topic_terms}):
        raise ValueError("triage_first_check_not_job_sourced")
    if not alignment.job_requirement_refs or not alignment.job_requirement_terms:
        raise ValueError("triage_first_check_not_job_sourced")
    source_terms = {term.casefold() for ref in alignment.job_requirement_refs
                    if ref in projection.positive_refs
                    for term in projection.facts[ref]}
    choices = source_terms & {term.casefold() for term in alignment.job_requirement_terms}
    if not choices:
        raise ValueError("triage_first_check_not_job_sourced")
    return min(choices)


_SYSTEM_INSTRUCTION = """你为招聘人员写一段可在十秒内读完的内部筛查提示。事实与下一步人工动作已由输入确定；你只负责自然、简洁地表达，不推断候选人个人经验、使用行为、能力等级、职责、技术决策或结果。
五个 JSON 字段各写一个简短内容，不重复同一句话：decision_summary 只给出既定强度的人工动作；why_consider 只说明选定的岗位方向关联；technical_signal 只提一个选定的材料技术信号；uncertainty 只说明尚未知的个人参与信息；interview_focus 只提出 first_check 指定的首要筛查问题。五句组成一个短 briefing，不是证据目录或技术清单。每个数组字段恰好一项，正文句式由你自由决定。
project_material 仅证明项目材料列出技术，不能写成候选人亲自使用或具备经验；alignment 仅是岗位方向关联，不能写成高度匹配或能力结论；unknown 不是候选人缺陷。interview_focus 只可核实是否参与及若参与的范围，不追问负责、选型、架构决策或依据。conditional_targeted_screen 是有条件的人工筛查，不是安排技术面或优先复核。不得提升任何事实或行动强度。
每段只引用本字段给定的 proposition_handles 键；键值为 true。只输出符合 JSON Schema 的 JSON。"""


def build_triage_generation_request_v1(
    projection: NarrativeProjection, propositions: RecruiterPropositionSetV1,
    plan: SemanticIntentPlanV1, *, max_output_tokens: int,
) -> ExplanationProviderRequest:
    if plan != build_triage_intent_plan_v1(projection, propositions):
        raise ValueError("noncanonical_triage_intent_plan")
    if type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096:
        raise ValueError("triage_max_output_tokens_invalid")
    chosen = _selected(propositions)
    binding = build_semantic_intent_binding_v1(propositions, plan)
    by_id = {entry.proposition_id: entry.handle for entry in binding.entries}
    catalog = {}
    for name in FIELDS:
        item = chosen[name]
        catalog[name] = {
            "handle": by_id[item.proposition_id], "kind": item.kind,
            "subject": item.subject, "predicate": item.predicate,
            "modality": item.modality, "topic_terms": item.topic_terms,
            "job_requirement_terms": item.job_requirement_terms,
        }
    topic = _first_check_topic(projection, chosen["why_consider"], chosen["interview_focus"])
    payload = {
        "candidate_id": propositions.candidate_id,
        "result_rank": propositions.result_rank,
        "role_title": projection.role_title,
        "review_action": plan.field("decision_summary").recommendation_strength,
        "first_check": {"topic": topic, "level": "participation_or_scope_only"},
        "proposition_catalog": catalog,
        "semantic_intent_plan": [
            {"name": field.name, "goal": field.goal, "boundary": field.boundary,
             "focus_handles": [by_id[pid] for pid in field.proposition_ids],
             "recommendation_strength": field.recommendation_strength}
            for field in plan.fields
        ],
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("triage_catalog_too_large")
    schema = build_proposition_response_schema_v1(binding)
    for name in FIELDS:
        if name != "decision_summary":
            schema["properties"][name]["maxItems"] = 1
    return ExplanationProviderRequest(
        system_instruction=_SYSTEM_INSTRUCTION,
        user_instruction=instruction,
        output_contract_version="recruiter_proposition_generation_v1",
        max_output_tokens=max_output_tokens,
        response_schema=schema,
    )


def resolve_triage_output_v1(
    output: PropositionProviderOutputV1, propositions: RecruiterPropositionSetV1,
    plan: SemanticIntentPlanV1,
) -> ResolvedPropositionNarrativeV1:
    if output.candidate_id != propositions.candidate_id or output.result_rank != propositions.result_rank:
        raise ValueError("triage_output_candidate_mismatch")
    if any(len(getattr(output, name)) != 1 for name in FIELDS if name != "decision_summary"):
        raise ValueError("triage_multiple_items")
    binding = build_semantic_intent_binding_v1(propositions, plan)
    return resolve_proposition_output_v1(output, binding)


__all__ = [
    "build_triage_intent_plan_v1", "build_triage_generation_request_v1", "resolve_triage_output_v1",
]
