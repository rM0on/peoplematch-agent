from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_v2_2 import RecruiterNarrativeV2_2
from app.services.explanation.presentation.facts_v2_2 import CandidateEvidencePackageV2_2
from app.services.match_runs.contracts import canonical_fingerprint


PROMPT_VERSION = "recruiter_narrative_prompt_v2_2"


@dataclass(frozen=True)
class NarrativeV2_2PromptArtifact:
    version: str
    fingerprint: str
    system_instruction: str


def load_narrative_v2_2_prompt() -> NarrativeV2_2PromptArtifact:
    path = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
    instruction = path.read_text(encoding="utf-8").strip()
    if not instruction:
        raise RuntimeError("Recruiter narrative V2.2 prompt empty")
    return NarrativeV2_2PromptArtifact(
        PROMPT_VERSION,
        canonical_fingerprint({"version": PROMPT_VERSION,
                               "contract": RecruiterNarrativeV2_2.model_json_schema(),
                               "instruction": instruction}),
        instruction,
    )


def build_narrative_v2_2_request(
    package: CandidateEvidencePackageV2_2, *, projection: NarrativeProjection,
    max_output_tokens: int,
) -> ExplanationProviderRequest:
    if (not package.requirement_alignment or not package.project_practice
            or type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096):
        raise ValueError("Narrative V2.2 request requires aligned project evidence")
    prompt = load_narrative_v2_2_prompt()
    sections = ("skills", "project_practice", "technical_scope", "requirement_alignment",
                "uncertainties", "interview_verification")
    payload = {
        "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "role_title": projection.role_title,
        "candidate_evidence_package": {
            section: [asdict(fact) | {"evidence_refs": sorted(fact.evidence_refs)}
                      for fact in getattr(package, section)]
            for section in sections
        },
        "output_contract": RecruiterNarrativeV2_2.model_json_schema(),
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V2.2 prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=prompt.system_instruction,
        user_instruction=instruction,
        output_contract_version="recruiter_narrative_v2_2",
        max_output_tokens=max_output_tokens,
    )


def build_narrative_v2_2_repair_request(
    original: ExplanationProviderRequest, narrative: RecruiterNarrativeV2_2,
    validation_error_summary: dict[str, object],
) -> ExplanationProviderRequest:
    if (validation_error_summary.get("category") != "claim_validation_failed"
            or not validation_error_summary.get("invalid_sections")):
        raise ValueError("Narrative V2.2 repair summary invalid")
    payload = json.loads(original.user_instruction)
    payload["previous_narrative"] = narrative.model_dump(mode="json")
    payload["validation_error_summary"] = validation_error_summary
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V2.2 repair prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=original.system_instruction + (
            "\n上次输出未通过事实校验。只修复 invalid_sections；保留已有可信内容。"
            "每个字段只引用该字段实际陈述技术词所需的 fact_id。"
            "unsupported_terms 或 unsupported_numbers 如果没有对应事实必须删除。"
            "unknown_fact_id 必须替换为 candidate_evidence_package 内的本候选人引用。"
            "personal_action、unsupported_scale、unsafe_claim、cross_candidate 为 true 时删除断言，"
            "不能换同义词隐藏。missing_alignment 时引用真实岗位关联事实，若没有则删除岗位匹配判断。"
            "不能添加个人职责、规模、部署或结果；保持候选身份与排名，重新输出完整 JSON。"
        ),
        user_instruction=instruction,
        output_contract_version=original.output_contract_version,
        max_output_tokens=original.max_output_tokens,
    )


__all__ = ["build_narrative_v2_2_request", "build_narrative_v2_2_repair_request",
           "load_narrative_v2_2_prompt"]
