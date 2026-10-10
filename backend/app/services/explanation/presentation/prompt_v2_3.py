from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
from app.services.explanation.presentation.facts_v2_2 import CandidateEvidencePackageV2_2
from app.services.match_runs.contracts import canonical_fingerprint


PROMPT_VERSION = "recruiter_narrative_prompt_v2_3"


@dataclass(frozen=True)
class NarrativeV2_3PromptArtifact:
    version: str
    fingerprint: str
    system_instruction: str


def load_narrative_v2_3_prompt() -> NarrativeV2_3PromptArtifact:
    path = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
    instruction = path.read_text(encoding="utf-8").strip()
    if not instruction:
        raise RuntimeError("Recruiter narrative V2.3 prompt empty")
    return NarrativeV2_3PromptArtifact(
        PROMPT_VERSION,
        canonical_fingerprint({"version": PROMPT_VERSION,
                               "contract": RecruiterNarrativeV2_3.model_json_schema(),
                               "instruction": instruction}),
        instruction,
    )


def build_narrative_v2_3_request(
    package: CandidateEvidencePackageV2_2, *, projection: NarrativeProjection,
    max_output_tokens: int,
) -> ExplanationProviderRequest:
    if (not package.requirement_alignment or not package.project_practice
            or type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096):
        raise ValueError("Narrative V2.3 requires aligned project evidence")
    prompt = load_narrative_v2_3_prompt()
    sections = ("skills", "project_practice", "technical_scope", "requirement_alignment",
                "uncertainties", "interview_verification")
    payload = {
        "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "role_title": projection.role_title,
        "candidate_evidence_package": {
            section: [asdict(fact) | {"evidence_refs": sorted(fact.evidence_refs)}
                      for fact in getattr(package, section)] for section in sections
        },
        "output_contract": RecruiterNarrativeV2_3.model_json_schema(),
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V2.3 prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=prompt.system_instruction,
        user_instruction=instruction,
        output_contract_version="recruiter_narrative_v2_3",
        max_output_tokens=max_output_tokens,
    )


def build_narrative_v2_3_repair_request(
    original: ExplanationProviderRequest, narrative: RecruiterNarrativeV2_3,
    validation_error_summary: dict[str, object],
) -> ExplanationProviderRequest:
    invalid = validation_error_summary.get("invalid_sections")
    if (validation_error_summary.get("category") != "claim_validation_failed"
            or not isinstance(invalid, list) or not invalid
            or any(not isinstance(section, str) or not (
                section == "decision_summary.decision"
                or section in {f"decision_summary.rationale[{i}]" for i in range(3)}
            ) for section in invalid)):
        raise ValueError("Narrative V2.3 repair summary invalid")
    payload = json.loads(original.user_instruction)
    payload["previous_narrative"] = narrative.model_dump(mode="json")
    payload["validation_error_summary"] = validation_error_summary
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V2.3 repair prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=original.system_instruction + (
            "\n上一版未通过事实与招聘动作校验。只修复 invalid_sections 指定字段，"
            "保持候选身份和排名不变。删除抽象评价及任何无来源的技能、个人职责、规模和结果。"
            "每条 rationale 必须引用本候选人的项目范围与岗位关联事实，"
            "verification_focus 应对应真实技术范围而不是泛问。"
            "若只有通用 Python 关联，不得使用 prioritize_review。"
            "不要增加新事实；只保留一条引用完整的 rationale。"
            "输出符合 output_contract 的完整 JSON 对象；不要输出 Markdown、代码围栏或补充文字，"
            "不要只输出被修复的字段或截断对象。"
        ),
        user_instruction=instruction,
        output_contract_version=original.output_contract_version,
        max_output_tokens=original.max_output_tokens,
    )


__all__ = ["build_narrative_v2_3_request", "build_narrative_v2_3_repair_request",
           "load_narrative_v2_3_prompt"]
