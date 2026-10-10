"""Opt-in V4 generation over immutable recruiter claims; no ranking writes."""

from __future__ import annotations

from dataclasses import dataclass
import time

from pydantic import ValidationError

from app.services.explanation.presentation.claims_v4 import RecruiterClaimGraphV4
from app.services.explanation.presentation.contracts_v4 import RecruiterNarrativeV4
from app.services.explanation.presentation.prompt_v4 import (
    build_narrative_v4_repair_request, build_narrative_v4_request,
)
from app.services.explanation.presentation.validator_v4 import diagnose_narrative_v4


class NarrativeV4GenerationError(ValueError):
    def __init__(self, reason: str, diagnostics: dict[str, str] | None = None) -> None:
        self.reason = reason
        self.diagnostics = diagnostics or {}
        super().__init__("Recruiter narrative V4 generation failed")


@dataclass(frozen=True)
class NarrativeV4GenerationResult:
    narrative: RecruiterNarrativeV4
    repair_count: int
    latency_seconds: float


async def generate_validated_narrative_v4(
    provider, *, graph: RecruiterClaimGraphV4, role_title: str,
    max_output_tokens: int = 4096,
) -> NarrativeV4GenerationResult:
    request = build_narrative_v4_request(
        graph, role_title=role_title, max_output_tokens=max_output_tokens)
    start = time.monotonic()
    response = await provider.generate(request)
    try:
        narrative = RecruiterNarrativeV4.model_validate_json(response.content)
    except (ValidationError, ValueError, TypeError):
        raise NarrativeV4GenerationError("schema_invalid") from None
    failures = diagnose_narrative_v4(narrative, graph=graph)
    if not failures:
        return NarrativeV4GenerationResult(narrative, 0, round(time.monotonic() - start, 3))
    repair = build_narrative_v4_repair_request(request, narrative, failures)
    response = await provider.generate(repair)
    try:
        narrative = RecruiterNarrativeV4.model_validate_json(response.content)
    except (ValidationError, ValueError, TypeError):
        raise NarrativeV4GenerationError("repair_schema_invalid") from None
    final_failures = diagnose_narrative_v4(narrative, graph=graph)
    if final_failures:
        raise NarrativeV4GenerationError("repair_claim_invalid", final_failures)
    return NarrativeV4GenerationResult(narrative, 1, round(time.monotonic() - start, 3))


__all__ = ["NarrativeV4GenerationError", "NarrativeV4GenerationResult",
           "generate_validated_narrative_v4"]
