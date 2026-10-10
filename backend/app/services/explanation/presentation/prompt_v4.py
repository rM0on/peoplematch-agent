"""Claim-only Qwen request for independent V4 recruiter narratives."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.claims_v4 import RecruiterClaimGraphV4
from app.services.explanation.presentation.contracts_v4 import RecruiterNarrativeV4
from app.services.match_runs.contracts import canonical_fingerprint


PROMPT_VERSION = "recruiter_narrative_prompt_v4"


@dataclass(frozen=True)
class NarrativeV4PromptArtifact:
    version: str
    fingerprint: str
    system_instruction: str


def load_narrative_v4_prompt() -> NarrativeV4PromptArtifact:
    path = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
    instruction = path.read_text(encoding="utf-8").strip()
    if not instruction:
        raise RuntimeError("Recruiter narrative V4 prompt empty")
    return NarrativeV4PromptArtifact(
        PROMPT_VERSION,
        canonical_fingerprint({"version": PROMPT_VERSION,
                               "contract": RecruiterNarrativeV4.model_json_schema(),
                               "instruction": instruction}),
        instruction,
    )


def build_narrative_v4_request(
    graph: RecruiterClaimGraphV4, *, role_title: str, max_output_tokens: int,
) -> ExplanationProviderRequest:
    if (not graph.claims or not role_title.strip() or type(max_output_tokens) is not int
            or not 512 <= max_output_tokens <= 4096):
        raise ValueError("Narrative V4 claim graph or token limit invalid")
    prompt = load_narrative_v4_prompt()
    payload = {
        "candidate_id": graph.candidate_id,
        "result_rank": graph.result_rank,
        "role_title": role_title,
        "claim_graph": [claim.model_dump(mode="json") for claim in graph.claims],
        "output_contract": RecruiterNarrativeV4.model_json_schema(),
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V4 prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=prompt.system_instruction,
        user_instruction=instruction,
        output_contract_version="recruiter_narrative_v4",
        max_output_tokens=max_output_tokens,
    )


def build_narrative_v4_repair_request(
    original: ExplanationProviderRequest,
    narrative: RecruiterNarrativeV4,
    failures: dict[str, str],
) -> ExplanationProviderRequest:
    """One constrained retry; source claims remain exactly the original set."""
    if (original.output_contract_version != "recruiter_narrative_v4" or not failures
            or len(failures) > 8):
        raise ValueError("Narrative V4 repair input invalid")
    payload = json.loads(original.user_instruction)
    payload["previous_narrative"] = narrative.model_dump(mode="json")
    payload["validation_errors"] = failures
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 196608:
        raise ValueError("Narrative V4 repair prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=original.system_instruction + "\n\n这是一次受约束修复。只修正 validation_errors 指出的段落；删除超出所引 Claim 范围的概念，或引用已有且真正支持该概念的 Claim。不得创建新的 Claim、事实或候选经历。修复后的完整 JSON 仍须符合原始 output_contract；如果无支持来源，则用已有 Claim 的范围重新表达，不得虚构。",
        user_instruction=instruction,
        output_contract_version=original.output_contract_version,
        max_output_tokens=original.max_output_tokens,
    )


__all__ = ["build_narrative_v4_request", "build_narrative_v4_repair_request",
           "load_narrative_v4_prompt"]
