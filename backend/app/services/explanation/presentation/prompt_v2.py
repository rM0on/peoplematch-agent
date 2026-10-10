from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.contracts_v2 import RecruiterNarrativeV2
from app.services.explanation.presentation.facts_v2 import AtomicFactV2
from app.services.match_runs.contracts import canonical_fingerprint


PROMPT_VERSION = "recruiter_narrative_prompt_v2"


@dataclass(frozen=True)
class NarrativeV2PromptArtifact:
    version: str
    fingerprint: str
    system_instruction: str


def load_narrative_v2_prompt() -> NarrativeV2PromptArtifact:
    path = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
    try:
        instruction = path.read_text(encoding="utf-8").strip()
    except OSError:
        raise RuntimeError("Recruiter narrative V2 prompt unavailable") from None
    if not instruction:
        raise RuntimeError("Recruiter narrative V2 prompt empty")
    return NarrativeV2PromptArtifact(
        version=PROMPT_VERSION,
        fingerprint=canonical_fingerprint({"version": PROMPT_VERSION, "contract": RecruiterNarrativeV2.model_json_schema(), "instruction": instruction}),
        system_instruction=instruction,
    )


def build_narrative_v2_request(
    facts: tuple[AtomicFactV2, ...], *, candidate_id: str, result_rank: int, role_title: str,
    max_output_tokens: int,
) -> ExplanationProviderRequest:
    if not facts or type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096:
        raise ValueError("Narrative V2 request invalid")
    prompt = load_narrative_v2_prompt()
    alignments = sorted(
        (fact for fact in facts if fact.kind == "requirement_alignment"),
        key=lambda fact: (fact.term.casefold() in {"python", "fastapi"}, fact.term.casefold(), fact.fact_id),
    )
    if not alignments:
        raise ValueError("Narrative V2 requires aligned evidence")
    anchor = alignments[0]
    candidate_sources = sorted(
        (fact for fact in facts if fact.kind in {"project_practice", "candidate_skill"}
         and fact.term.casefold() == anchor.term.casefold()),
        key=lambda fact: (fact.kind != "project_practice", fact.fact_id),
    )
    if not candidate_sources:
        raise ValueError("Narrative V2 alignment lacks candidate source")
    payload = {
        "candidate_id": candidate_id,
        "result_rank": result_rank,
        "role_title": role_title,
        "atomic_facts": [
            {"fact_id": fact.fact_id, "kind": fact.kind, "term": fact.term,
             "evidence_refs": fact.evidence_refs, "allowed_inference": fact.allowed_inference}
            for fact in facts
        ],
        "term_to_fact_ids": {
            term: sorted(fact.fact_id for fact in facts if fact.term.casefold() == term)
            for term in sorted({fact.term.casefold() for fact in facts})
        },
        "required_fact_kinds": {
            "decision_summary": ["requirement_alignment"],
            "why_review": ["requirement_alignment"],
        },
        "why_review_focus": {
            "term": anchor.term,
            "candidate_fact_id": candidate_sources[0].fact_id,
            "alignment_fact_id": anchor.fact_id,
        },
        "output_contract": RecruiterNarrativeV2.model_json_schema(),
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V2 prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=prompt.system_instruction,
        user_instruction=instruction,
        output_contract_version="recruiter_narrative_v2",
        max_output_tokens=max_output_tokens,
    )


def build_narrative_v2_repair_request(
    original: ExplanationProviderRequest, narrative: RecruiterNarrativeV2,
    validation_error_summary: dict[str, object],
) -> ExplanationProviderRequest:
    if (validation_error_summary.get("category") != "claim_validation_failed"
            or not validation_error_summary.get("invalid_sections")):
        raise ValueError("Narrative V2 repair summary invalid")
    payload = json.loads(original.user_instruction)
    payload["previous_narrative"] = narrative.model_dump(mode="json")
    payload["validation_error_summary"] = validation_error_summary
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V2 repair prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=original.system_instruction + (
            "\n前一次输出未通过事实校验。只修复 validation_error_summary 指明的字段："
            "若提及已记录技术词，使用 term_to_fact_ids 加入该字段自己的正确 fact_id；"
            "validation_error_summary 中的 unsupported_terms 必须在对应字段补齐真实支持引用，"
            "否则删去该词；unsafe_claim 为 true 时删除未经证实的断言，不能只改变措辞。"
            "unsupported_scale、unsupported_action 或 responsibility_violation 为 true 时，"
            "删除相应的规模、个人工作动作或职责断言；若只是未知信息，可改写成明确的面试核实问题。"
            "若内容超出 atomic_facts 的 allowed_inference，删除该断言或改成待核实问题。"
            "不要引入任何新事实、项目、职责、规模或结果；不要更改 candidate_id/result_rank。"
            "重新输出完整 JSON。修复后仍须通过原始 Schema 和 Claim Validation。"
        ),
        user_instruction=instruction,
        output_contract_version=original.output_contract_version,
        max_output_tokens=original.max_output_tokens,
    )


__all__ = ["build_narrative_v2_request", "build_narrative_v2_repair_request", "load_narrative_v2_prompt"]
