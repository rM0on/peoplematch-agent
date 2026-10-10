"""Experimental field-level communication intent over canonical propositions.

This view selects existing semantic commitments; it neither creates facts nor
renders candidate prose. It is deliberately outside the product runtime.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Literal, Optional

from pydantic import ConfigDict, Field

from app.schemas.shared import ContractModel
from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_proposition_v1 import (
    NarrativeFieldV1, RecruiterPropositionSetV1, RecruiterPropositionV1,
)
from app.services.explanation.presentation.generation_proposition_v1 import (
    FIELDS, PropositionHandleBindingV1, build_proposition_binding_v1,
    build_proposition_response_schema_v1,
)
from app.services.explanation.presentation.interview_semantics_proposition_v1 import (
    InterviewQuestionIntentV1, build_interview_question_intent_v1,
)
from app.services.explanation.presentation.propositions_v1 import validate_interview_recruiter_propositions_v1


GoalV1 = Literal[
    "human_review_action", "reason_to_explore", "material_technical_signal",
    "nonpresupposing_interview_target", "material_uncertainty",
]
BoundaryV1 = Literal[
    "action_not_hiring_decision", "relation_not_experience_or_capability",
    "material_observation_not_personal_action", "question_not_assumed_responsibility",
    "unknown_not_candidate_deficiency",
]
ReviewStrengthV1 = Literal["priority_human_review", "conditional_targeted_screen"]


class FieldSemanticIntentV1(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: NarrativeFieldV1
    goal: GoalV1
    boundary: BoundaryV1
    proposition_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    recommendation_strength: Optional[ReviewStrengthV1] = None
    focus_topic: Optional[str] = None
    question_intent: Optional[InterviewQuestionIntentV1] = None


class SemanticIntentPlanV1(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["recruiter_semantic_intent_v1"]
    candidate_id: str
    result_rank: int
    fields: tuple[FieldSemanticIntentV1, ...] = Field(min_length=5, max_length=5)

    def field(self, name: NarrativeFieldV1) -> FieldSemanticIntentV1:
        return next(field for field in self.fields if field.name == name)


_GOALS: dict[str, tuple[GoalV1, BoundaryV1]] = {
    "decision_summary": ("human_review_action", "action_not_hiring_decision"),
    "why_consider": ("reason_to_explore", "relation_not_experience_or_capability"),
    "technical_signal": ("material_technical_signal", "material_observation_not_personal_action"),
    "interview_focus": ("nonpresupposing_interview_target", "question_not_assumed_responsibility"),
    "uncertainty": ("material_uncertainty", "unknown_not_candidate_deficiency"),
}


def _is_project_backed(item: RecruiterPropositionV1) -> bool:
    return any(":project:" in ref or ":project_evidence:" in ref for ref in item.evidence_refs)


def _select(items: list[RecruiterPropositionV1], field: str) -> tuple[str, ...]:
    if field == "decision_summary":
        candidates = [p for p in items if p.kind == "human_review_recommendation"]
        candidates.sort(key=lambda p: (p.predicate != "prioritize_technical_review", -len(p.job_requirement_refs), p.proposition_id))
        chosen = candidates[:1]
    elif field == "why_consider":
        candidates = [p for p in items if p.kind == "technical_alignment"]
        candidates.sort(key=lambda p: (not _is_project_backed(p), -len(p.job_requirement_refs), p.proposition_id))
        chosen = candidates[:2]
    elif field == "technical_signal":
        candidates = [p for p in items if p.kind in {"project_observation", "listed_skill_observation"}]
        candidates.sort(key=lambda p: (p.kind != "project_observation", -len(p.topic_terms), p.proposition_id))
        chosen = candidates[:2]
    elif field == "uncertainty":
        candidates = [p for p in items if p.kind == "material_unknown"]
        candidates.sort(key=lambda p: (p.predicate != "project_scope_not_established", p.proposition_id))
        chosen = candidates[:2]
    else:
        raise ValueError("semantic_intent_field_unknown")
    if not chosen or any(field not in item.allowed_fields for item in chosen):
        raise ValueError("semantic_intent_field_support_missing")
    return tuple(item.proposition_id for item in chosen)


def build_semantic_intent_plan_v1(
    projection: NarrativeProjection, propositions: RecruiterPropositionSetV1,
) -> SemanticIntentPlanV1:
    validate_interview_recruiter_propositions_v1(propositions, projection=projection)
    lookup = {p.proposition_id: p for p in propositions.propositions}
    selections = {field: _select(list(lookup.values()), field)
                  for field in FIELDS if field != "interview_focus"}
    question = build_interview_question_intent_v1(
        projection, propositions, review_proposition_id=selections["decision_summary"][0])
    selections["interview_focus"] = question.supporting_proposition_ids
    review = lookup[selections["decision_summary"][0]]
    if (question.review_action == "priority_human_review") != (
            review.predicate == "prioritize_technical_review"):
        raise ValueError("interview_review_action_mismatch")
    fields = []
    for field in FIELDS:
        ids = selections[field]
        goal, boundary = _GOALS[field]
        strength: ReviewStrengthV1 | None = None
        if field == "decision_summary":
            strength = ("priority_human_review" if lookup[ids[0]].predicate == "prioritize_technical_review"
                        else "conditional_targeted_screen")
        fields.append(FieldSemanticIntentV1(
            name=field, goal=goal, boundary=boundary,
            proposition_ids=ids, recommendation_strength=strength,
            focus_topic=question.target_topic if field == "interview_focus" else None,
            question_intent=question if field == "interview_focus" else None,
        ))
    return SemanticIntentPlanV1(
        contract_version="recruiter_semantic_intent_v1",
        candidate_id=propositions.candidate_id, result_rank=propositions.result_rank,
        fields=tuple(fields),
    )


def build_semantic_intent_binding_v1(
    propositions: RecruiterPropositionSetV1, plan: SemanticIntentPlanV1,
) -> PropositionHandleBindingV1:
    """Keep exact request handles, but expose only each field's selected focus."""
    binding = build_proposition_binding_v1(propositions)
    if (plan.candidate_id != binding.candidate_id or plan.result_rank != binding.result_rank
            or tuple(field.name for field in plan.fields) != FIELDS):
        raise ValueError("semantic_intent_binding_identity_mismatch")
    selected = {field.name: set(field.proposition_ids) for field in plan.fields}
    by_id = {entry.proposition_id: entry for entry in binding.entries}
    for field in FIELDS:
        if not selected[field] or not selected[field] <= by_id.keys():
            raise ValueError("semantic_intent_binding_missing_focus")
        if any(field not in by_id[pid].allowed_fields for pid in selected[field]):
            raise ValueError("semantic_intent_binding_wrong_role")
    scoped = replace(binding, entries=tuple(
        replace(entry, allowed_fields=tuple(field for field in entry.allowed_fields
                                             if entry.proposition_id in selected[field]))
        for entry in binding.entries
    ))
    if any(not scoped.allowed_handles(field) for field in FIELDS):
        raise ValueError("semantic_intent_binding_missing_focus")
    return scoped


_SYSTEM_INSTRUCTION = """你是技术招聘负责人，为 Hiring Manager 写简短、自然的内部候选评估。最终每段正文由你组织，不要照搬字段名、目录或写成 Evidence 报告。
semantic_intent_plan 是每个字段已经核定的表达意图，不是新事实；每个字段只使用该字段 focus_handles 指向的命题。只可改变语言形式，不可改变命题的主语、事实强度或人工动作强度。
project_material 仅指项目材料列出的技术，不证明候选人亲自使用、部署、掌握或拥有经验；candidate_material 仅指材料列出的技能，不证明熟练度。alignment 仅是方向关联，不是高度匹配、具备能力或相关经验。hypothesis 是未证实的面试目标，问题也不得预设已负责、主导或完成。unknown 是材料无法确认，不是候选人缺陷。consider_targeted_screen 仅为有条件的定向人工了解；prioritize_technical_review 才可建议优先人工技术复核，两者均非录用结论。
如果 recommendation_strength 是 conditional_targeted_screen，只能表达是否值得先做定向人工筛查，不能写成已决定安排面试、技术面或优先复核；该动作不是面试邀请。
把五个字段写成互补的简短 briefing，而不是同一句材料摘要的五种改写：decision_summary 给出相应强度的下一步人工动作；why_consider 说明选中岗位关联为什么值得看；technical_signal 挑一个有区分度的材料事实，不罗列整套技术词；interview_focus 围绕 question_intent 的有来源岗位目标提出具体问题；uncertainty 说明一项仍未建立的个人参与边界，不重复技术列表。参与存在、参与范围、是否承担决策、决策依据是不同问题：当前只能直接问 direct_question_level；follow_up_gate 满足后才追问范围，个人决策必须另行确认，只有个人决策确认后才能问决策依据。conditional_targeted_screen 的问题仍是筛查，不是技术面邀请。问题可以具体，但不能把可能的做法写成已发生的事实。句式由你自由组织，避免五段同一起手。
可以自然合并已选命题、调整语序，但不得增加命题之外的技能、个人动作、能力等级、职责、规模或结果。每段选择所有实际支撑正文的 focus_handles，proposition_handles 为仅包含选中键且值为 true 的 JSON 对象。只输出符合 JSON Schema 的 JSON。"""


def build_semantic_intent_generation_request_v1(
    projection: NarrativeProjection, propositions: RecruiterPropositionSetV1,
    plan: SemanticIntentPlanV1, *, max_output_tokens: int,
) -> ExplanationProviderRequest:
    canonical = build_semantic_intent_plan_v1(projection, propositions)
    if plan != canonical:
        raise ValueError("noncanonical_semantic_intent_plan")
    if not projection.role_title.strip() or type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096:
        raise ValueError("semantic_intent_generation_request_invalid")
    binding = build_semantic_intent_binding_v1(propositions, plan)
    by_id = {item.proposition_id: item for item in propositions.propositions}
    by_handle = {entry.proposition_id: entry.handle for entry in binding.entries}
    catalog = []
    for entry in binding.entries:
        if not entry.allowed_fields:
            continue
        item = by_id[entry.proposition_id]
        catalog.append({
            "handle": entry.handle, "kind": item.kind, "subject": item.subject,
            "predicate": item.predicate, "modality": item.modality,
            "topic_terms": item.topic_terms,
            "job_requirement_terms": item.job_requirement_terms,
            "allowed_fields": item.allowed_fields,
        })
    intent = [{
        "name": field.name, "goal": field.goal, "boundary": field.boundary,
        "focus_handles": [by_handle[pid] for pid in field.proposition_ids],
        "recommendation_strength": field.recommendation_strength,
        "focus_topic": field.focus_topic,
        "question_intent": (field.question_intent.model_dump(
            mode="json", exclude={"candidate_id", "result_rank", "target_requirement_ref",
                                  "supporting_proposition_ids"})
                            if field.question_intent is not None else None),
    } for field in plan.fields]
    user_instruction = json.dumps({
        "candidate_id": propositions.candidate_id,
        "result_rank": propositions.result_rank,
        "role_title": projection.role_title,
        "proposition_catalog": catalog,
        "semantic_intent_plan": intent,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(user_instruction.encode("utf-8")) > 131072:
        raise ValueError("semantic_intent_catalog_too_large")
    return ExplanationProviderRequest(
        system_instruction=_SYSTEM_INSTRUCTION,
        user_instruction=user_instruction,
        output_contract_version="recruiter_proposition_generation_v1",
        max_output_tokens=max_output_tokens,
        response_schema=build_proposition_response_schema_v1(binding),
    )


__all__ = ["FieldSemanticIntentV1", "SemanticIntentPlanV1", "build_semantic_intent_plan_v1",
           "build_semantic_intent_binding_v1",
           "build_semantic_intent_generation_request_v1"]
