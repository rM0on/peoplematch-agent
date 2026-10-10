"""Claim-and-frame-only Qwen request for recruiter-facing V4.1 language."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.claims_v4 import RecruiterClaimGraphV4
from app.services.explanation.presentation.contracts_v4 import RecruiterNarrativeV4
from app.services.explanation.presentation.decision_frame_v4_1 import (
    HiringDecisionFrameV1, guard_decision_frame_v4_1,
)


PROMPT_VERSION = "recruiter_narrative_prompt_v4_1"


def build_narrative_v4_1_request(
    frame: HiringDecisionFrameV1, *, graph: RecruiterClaimGraphV4,
    role_title: str, max_output_tokens: int,
) -> ExplanationProviderRequest:
    guard_decision_frame_v4_1(frame, graph=graph)
    if not role_title.strip() or type(max_output_tokens) is not int or not 512 <= max_output_tokens <= 4096:
        raise ValueError("Narrative V4.1 role or token limit invalid")
    instruction = (Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt")
    system_instruction = instruction.read_text(encoding="utf-8").strip()
    if not system_instruction:
        raise RuntimeError("Narrative V4.1 prompt empty")
    selected_refs = {
        ref for section in (frame.why_consider, frame.what_to_verify,
                            frame.current_signal, frame.risk_boundary)
        for entry in section for ref in entry.claim_refs
    }
    payload = {
        "candidate_id": frame.candidate_id,
        "result_rank": frame.result_rank,
        "role_title": role_title,
        "decision_frame": {
            section: [{"claim_refs": entry.claim_refs, "concepts": entry.concepts}
                      for entry in getattr(frame, section)]
            for section in ("why_consider", "what_to_verify", "current_signal", "risk_boundary")
        },
        "claim_graph": [claim.model_dump(mode="json") for claim in graph.claims
                        if claim.claim_id in selected_refs],
        "allowed_technical_concepts": sorted({
            concept for claim in graph.claims if claim.claim_id in selected_refs
            for concept in claim.concepts
        }),
        "output_contract": RecruiterNarrativeV4.model_json_schema(),
    }
    user_instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(user_instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V4.1 prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=system_instruction, user_instruction=user_instruction,
        output_contract_version="recruiter_narrative_v4", max_output_tokens=max_output_tokens,
    )


__all__ = ["PROMPT_VERSION", "build_narrative_v4_1_request"]
