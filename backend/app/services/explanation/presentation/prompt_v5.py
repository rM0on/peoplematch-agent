"""Hiring-context-scoped Qwen request; no raw resume or generated facts."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.claims_v4 import RecruiterClaimGraphV4
from app.services.explanation.presentation.claim_handle_binding_v5 import (
    ClaimHandleBindingV5, build_claim_handle_binding_v5,
)
from app.services.explanation.presentation.decision_frame_v4_1 import HiringDecisionFrameV1
from app.services.explanation.presentation.hiring_context_v5 import (
    HiringContextGraphV5, guard_hiring_context_v5,
)
from app.services.explanation.presentation.provider_output_v5 import (
    RecruiterNarrativeV5ProviderOutput, build_provider_response_schema_v5,
)


PROMPT_VERSION = "recruiter_narrative_prompt_v5"


_CLAIM_EPISTEMIC_POLICY = {
    ("technical_alignment", "observed_requirement_overlap"): (
        "ALIGNMENT", "只观察已列项目方向与岗位要求的关联；可说值得在技术面继续了解，不能说候选人具备相关经验、掌握技术或已有成熟能力。"),
    ("skill_requirement_match", "listed_skill_overlap"): (
        "ALIGNMENT", "只观察已列技能与岗位要求的关联；不能推断熟练度、项目经验、职责或能力等级。"),
    ("project_depth_validation", "verify_observed_scope"): (
        "INTERVIEW_TARGET", "只提出项目参与深度的非预设式验证问题；用是否、实际参与范围或职责边界提问，不能预设候选人已负责、主导或设计。"),
    ("interview_focus", "verify_observed_scope"): (
        "INTERVIEW_TARGET", "只提出已知项目方向的非预设式面试问题；确认是否参与及具体职责，不能把待验证的负责、主导或设计写成既成事实。"),
    ("interview_focus", "open_requirement"): (
        "UNKNOWN", "岗位要求仍是未知的验证方向；可问是否涉及，不能说候选人缺少该能力，也不能说已经具备。"),
    ("review_recommendation", "alignment_plus_interview_focus"): (
        "ALIGNMENT", "只可建议人工技术复核或下一轮了解；不证明候选人能力，不作录用结论。"),
}


def _model_facing_epistemic_policy(claim_type: str, relation_type: str) -> tuple[str, str]:
    try:
        return _CLAIM_EPISTEMIC_POLICY[(claim_type, relation_type)]
    except KeyError as error:
        raise ValueError("unsupported_claim_epistemic_policy") from error


def build_narrative_v5_request(
    context: HiringContextGraphV5, *, graph: RecruiterClaimGraphV4,
    frame: HiringDecisionFrameV1, role_title: str, max_output_tokens: int,
    binding: ClaimHandleBindingV5 | None = None,
) -> ExplanationProviderRequest:
    guard_hiring_context_v5(context, graph=graph, frame=frame)
    canonical_binding = build_claim_handle_binding_v5(graph, frame, context)
    if binding is not None and binding != canonical_binding:
        raise ValueError("noncanonical_claim_handle_binding")
    binding = canonical_binding
    if not role_title.strip() or type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096:
        raise ValueError("Narrative V5 role or token limit invalid")
    instruction = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
    system_instruction = instruction.read_text(encoding="utf-8").strip()
    if not system_instruction:
        raise RuntimeError("Narrative V5 prompt empty")
    sections = ("candidate_signal", "why_this_matters", "interview_focus", "uncertainty_boundary")
    response_schema = build_provider_response_schema_v5(binding)
    catalog = []
    for entry in binding.entries:
        epistemic_role, expression_boundary = _model_facing_epistemic_policy(
            entry.claim_type, entry.relation_type)
        catalog.append({
            "handle": entry.handle, "claim_type": entry.claim_type,
            "relation_type": entry.relation_type, "concepts": entry.concepts,
            "allowed_frame_roles": entry.allowed_frame_roles,
            "epistemic_role": epistemic_role,
            "expression_boundary": expression_boundary,
        })
    payload = {
        "candidate_id": context.candidate_id,
        "result_rank": context.result_rank,
        "role_title": role_title,
        "hiring_context": {section: [
            {"claim_handles": [binding.handle_for(ref) for ref in item.claim_refs],
             "concepts": item.concepts,
             "job_relation": item.job_relation}
            for item in getattr(context, section)
        ] for section in sections},
        "claim_catalog": catalog,
        "output_contract": response_schema,
    }
    user_instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(user_instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V5 prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=system_instruction, user_instruction=user_instruction,
        output_contract_version="recruiter_narrative_v5", max_output_tokens=max_output_tokens,
        response_schema=response_schema,
    )


def build_narrative_v5_repair_request(
    original: ExplanationProviderRequest, narrative: RecruiterNarrativeV5ProviderOutput,
    failures: dict[str, str],
) -> ExplanationProviderRequest:
    if original.output_contract_version != "recruiter_narrative_v5" or not failures or len(failures) > 12:
        raise ValueError("Narrative V5 repair input invalid")
    payload = json.loads(original.user_instruction)
    payload["previous_narrative"] = narrative.model_dump(mode="json")
    payload["validation_errors"] = failures
    user_instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(user_instruction.encode("utf-8")) > 196608:
        raise ValueError("Narrative V5 repair prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=original.system_instruction +
        "\n\n受约束修复：仅调整 validation_errors 指向的表达或 claim_refs。"
        "保持招聘语言自然，但删除无 Claim 支持的技术、职责、规模和能力结论。"
        "只能使用原 claim_catalog 中的短 Handle，不得创建 Claim 或事实；输出完整的原始 JSON 契约。",
        user_instruction=user_instruction,
        output_contract_version=original.output_contract_version,
        max_output_tokens=original.max_output_tokens,
        response_schema=original.response_schema,
    )


__all__ = ["PROMPT_VERSION", "build_narrative_v5_request",
           "build_narrative_v5_repair_request"]
