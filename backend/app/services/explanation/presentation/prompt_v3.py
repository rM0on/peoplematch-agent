"""Real-provider V3 request built only from validated per-candidate graph facts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_v3 import RecruiterNarrativeV3
from app.services.explanation.presentation.facts_v3 import AtomicFactGraphV3
from app.services.match_runs.contracts import canonical_fingerprint


PROMPT_VERSION = "recruiter_narrative_prompt_v3"


@dataclass(frozen=True)
class NarrativeV3PromptArtifact:
    version: str
    fingerprint: str
    system_instruction: str


def load_narrative_v3_prompt() -> NarrativeV3PromptArtifact:
    path = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
    instruction = path.read_text(encoding="utf-8").strip()
    if not instruction:
        raise RuntimeError("Recruiter narrative V3 prompt empty")
    return NarrativeV3PromptArtifact(
        PROMPT_VERSION,
        canonical_fingerprint({"version": PROMPT_VERSION,
                               "contract": RecruiterNarrativeV3.model_json_schema(),
                               "instruction": instruction}),
        instruction,
    )


def build_narrative_v3_request(graph: AtomicFactGraphV3, *, projection: NarrativeProjection,
                               max_output_tokens: int) -> ExplanationProviderRequest:
    if (graph.candidate_id != projection.candidate_id or graph.result_rank != projection.result_rank
            or not graph.claim_candidates or type(max_output_tokens) is not int
            or not 512 <= max_output_tokens <= 4096):
        raise ValueError("Narrative V3 graph or token limit invalid")
    prompt = load_narrative_v3_prompt()
    payload = {
        "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "role_title": projection.role_title,
        "atomic_fact_graph": {
            "facts": [asdict(fact) for fact in graph.facts],
            "edges": [asdict(edge) for edge in graph.edges],
            "claim_candidates": [asdict(claim) for claim in graph.claim_candidates],
        },
        "output_contract": RecruiterNarrativeV3.model_json_schema(),
    }
    instruction = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 131072:
        raise ValueError("Narrative V3 prompt exceeds byte limit")
    return ExplanationProviderRequest(
        system_instruction=prompt.system_instruction,
        user_instruction=instruction,
        output_contract_version="recruiter_narrative_v3",
        max_output_tokens=max_output_tokens,
    )


__all__ = ["build_narrative_v3_request", "load_narrative_v3_prompt"]
