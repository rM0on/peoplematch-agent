"""Opt-in V3.1 real-provider prompt over the unchanged validated V3 fact graph."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_v3_1 import RecruiterNarrativeV3_1
from app.services.explanation.presentation.facts_v3 import AtomicFactGraphV3
from app.services.match_runs.contracts import canonical_fingerprint


PROMPT_VERSION = "recruiter_narrative_prompt_v3_1"


@dataclass(frozen=True)
class NarrativeV3_1PromptArtifact:
    version: str
    fingerprint: str
    system_instruction: str


def load_narrative_v3_1_prompt() -> NarrativeV3_1PromptArtifact:
    path = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
    instruction = path.read_text(encoding="utf-8").strip()
    if not instruction:
        raise RuntimeError("Recruiter narrative V3.1 prompt empty")
    return NarrativeV3_1PromptArtifact(
        PROMPT_VERSION,
        canonical_fingerprint({"version": PROMPT_VERSION,
                               "contract": RecruiterNarrativeV3_1.model_json_schema(),
                               "instruction": instruction}),
        instruction,
    )


def build_narrative_v3_1_request(
    graph: AtomicFactGraphV3, *, projection: NarrativeProjection, max_output_tokens: int,
) -> ExplanationProviderRequest:
    if (graph.candidate_id != projection.candidate_id or graph.result_rank != projection.result_rank
            or not graph.claim_candidates or type(max_output_tokens) is not int
            or not 512 <= max_output_tokens <= 4096):
        raise ValueError("Narrative V3.1 graph or token limit invalid")
    prompt = load_narrative_v3_1_prompt()
    # Rename relation categories in the provider view; fact IDs and graph remain unchanged.
    semantic_types = {
        "evidence_statement": ("evidence_summary",),
        "capability_inference": ("job_alignment_observation", "review_recommendation"),
        "interview_validation": ("interview_validation",),
        "uncertainty_statement": ("interview_validation",),
    }
    claim_candidates = [
        {"claim_type": claim_type, "topic": candidate.topic, "fact_ids": candidate.fact_ids}
        for candidate in graph.claim_candidates
        for claim_type in semantic_types[candidate.claim_type]
    ]
    payload = {
        "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "role_title": projection.role_title,
        "atomic_fact_graph": {
            "facts": [asdict(fact) for fact in graph.facts],
            "edges": [asdict(edge) for edge in graph.edges],
            "claim_candidates": claim_candidates,
        },
        "output_contract": RecruiterNarrativeV3_1.model_json_schema(),
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V3.1 prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=prompt.system_instruction,
        user_instruction=instruction,
        output_contract_version="recruiter_narrative_v3_1",
        max_output_tokens=max_output_tokens,
    )


__all__ = ["build_narrative_v3_1_request", "load_narrative_v3_1_prompt"]
