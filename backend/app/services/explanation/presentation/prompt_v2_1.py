from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
from app.services.explanation.presentation.facts_v2 import AtomicFactV2
from app.services.match_runs.contracts import canonical_fingerprint


PROMPT_VERSION = "recruiter_narrative_prompt_v2_1"


@dataclass(frozen=True)
class NarrativeV2_1PromptArtifact:
    version: str
    fingerprint: str
    system_instruction: str


def load_narrative_v2_1_prompt() -> NarrativeV2_1PromptArtifact:
    path = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
    try:
        instruction = path.read_text(encoding="utf-8").strip()
    except OSError:
        raise RuntimeError("Recruiter narrative V2.1 prompt unavailable") from None
    if not instruction:
        raise RuntimeError("Recruiter narrative V2.1 prompt empty")
    return NarrativeV2_1PromptArtifact(
        version=PROMPT_VERSION,
        fingerprint=canonical_fingerprint({
            "version": PROMPT_VERSION,
            "contract": RecruiterNarrativeV2_1.model_json_schema(),
            "instruction": instruction,
        }),
        system_instruction=instruction,
    )


def build_narrative_v2_1_request(
    facts: tuple[AtomicFactV2, ...], *, candidate_id: str, result_rank: int,
    role_title: str, max_output_tokens: int,
) -> ExplanationProviderRequest:
    if (not facts or not any(f.kind == "requirement_alignment" for f in facts)
            or type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096):
        raise ValueError("Narrative V2.1 request invalid")
    prompt = load_narrative_v2_1_prompt()
    payload = {
        "candidate_id": candidate_id,
        "result_rank": result_rank,
        "role_title": role_title,
        "atomic_facts": [
            {"fact_id": f.fact_id, "kind": f.kind, "term": f.term,
             "evidence_refs": f.evidence_refs, "allowed_inference": f.allowed_inference}
            for f in facts
        ],
        "direction_inference_rule": "方向推断仅说明已记录技术组合的关联；引用时还须同时引用支撑它的项目事实，不得升级成候选人职责或成果",
        "term_to_fact_ids": {
            term: sorted(f.fact_id for f in facts if f.term.casefold() == term)
            for term in sorted({f.term.casefold() for f in facts})
        },
        "aligned_terms": sorted({f.term for f in facts if f.kind == "requirement_alignment"}),
        "candidate_direction_terms": sorted({
            f.term for f in facts if f.kind == "project_practice"
            and f.term.casefold() not in {"python", "fastapi"}
        }),
        "required_fact_kinds": {"why_consider": ["requirement_alignment"]},
        "output_contract": RecruiterNarrativeV2_1.model_json_schema(),
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V2.1 prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=prompt.system_instruction,
        user_instruction=instruction,
        output_contract_version="recruiter_narrative_v2_1",
        max_output_tokens=max_output_tokens,
    )


def build_narrative_v2_1_repair_request(
    original: ExplanationProviderRequest, narrative: RecruiterNarrativeV2_1,
    validation_error_summary: dict[str, object],
) -> ExplanationProviderRequest:
    if (validation_error_summary.get("category") != "claim_validation_failed"
            or not validation_error_summary.get("invalid_sections")):
        raise ValueError("Narrative V2.1 repair summary invalid")
    payload = json.loads(original.user_instruction)
    payload["previous_narrative"] = narrative.model_dump(mode="json")
    payload["validation_error_summary"] = validation_error_summary
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V2.1 repair prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=original.system_instruction + (
            "\n上次输出未通过事实校验。只修复 invalid_sections 指定字段。"
            "对每个 unsupported_terms 从 term_to_fact_ids 查找当前字段自己的事实引用；"
            "若没有支持，删除该词及其断言。unsupported_numbers 没有事实支持时删除相应数字。"
            "若 unsafe_claim、unsupported_scale、unsupported_action、responsibility_violation"
            " 或 foreign_candidate 为 true，必须删除该断言，不能只替换同义词。"
            "若 missing_direction_support 为 true，仅在 atomic_facts 存在该方向事实时引用它；"
            "missing_direction_terms 列出待修复的方向词；若不存在这些事实，删除该方向判断。"
            "若 missing_mentioned_fact_term 为 true，"
            "从该字段的 supported_terms 中选一个最相关的技术词自然表达，"
            "或引用已提供的 direction_inference；"
            "若 duplicate_fact_id 为 true，去重。"
            "若 unsupported_production_claim 为 true，删除没有事实依据的高可用、上线或业务成果断言；"
            "可以改为假设性面试问题，但不得暗示候选人已做过。"
            "若 unsupported_personal_work 为 true，删除没有事实支持的个人构建、开发、部署、"
            "优化、掌握或工程能力断言；只能说项目记录涉及相关技术，或提出面试问题。"
            "对规模、职责、动作和结果断言，若 atomic_facts"
            " 没有明确记载，删除断言或改为具体面试问题；未知不等于缺少。"
            "不要加入新事实，不要改 candidate_id/result_rank。重新输出完整 JSON。"
        ),
        user_instruction=instruction,
        output_contract_version=original.output_contract_version,
        max_output_tokens=original.max_output_tokens,
    )


__all__ = ["build_narrative_v2_1_request", "build_narrative_v2_1_repair_request", "load_narrative_v2_1_prompt"]
