from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts import RecruiterNarrativeV1
from app.services.explanation.presentation.copy_catalog import approved_copy
from app.services.match_runs.contracts import canonical_fingerprint


PROMPT_VERSION = "recruiter_narrative_prompt_v1"
CONTRACT_VERSION = "recruiter_narrative_v1"


@dataclass(frozen=True)
class NarrativePromptArtifact:
    version: str
    fingerprint: str
    system_instruction: str


def load_narrative_prompt() -> NarrativePromptArtifact:
    path = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
    try:
        instruction = path.read_text(encoding="utf-8").strip()
    except OSError:
        raise RuntimeError("Recruiter narrative prompt is unavailable") from None
    if not instruction:
        raise RuntimeError("Recruiter narrative prompt is empty")
    return NarrativePromptArtifact(
        version=PROMPT_VERSION,
        fingerprint=canonical_fingerprint(
            {"version": PROMPT_VERSION, "contract": RecruiterNarrativeV1.model_json_schema(), "instruction": instruction}
        ),
        system_instruction=instruction,
    )


def build_narrative_request(
    projection: NarrativeProjection, *, max_output_tokens: int
) -> ExplanationProviderRequest:
    if type(max_output_tokens) is not int or not 256 <= max_output_tokens <= 4096:
        raise ValueError("Narrative output token budget is invalid")
    prompt = load_narrative_prompt()
    payload = {
        "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "role_title": projection.role_title,
        "facts": [
            {"evidence_link": ref, "terms": list(terms)}
            for ref, terms in sorted(projection.facts.items())
        ],
        "allowed_positive_links": sorted(projection.positive_refs),
        "allowed_risk_links": sorted(projection.risk_refs),
        "allowed_interview_links": sorted(projection.interview_refs),
        "approved_copy": {
            section: [item.model_dump(mode="json") for item in items]
            for section, items in approved_copy(projection).items()
        },
        "output_contract": RecruiterNarrativeV1.model_json_schema(),
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=prompt.system_instruction,
        user_instruction=instruction,
        output_contract_version=CONTRACT_VERSION,
        max_output_tokens=max_output_tokens,
    )


__all__ = ["NarrativePromptArtifact", "build_narrative_request", "load_narrative_prompt"]
