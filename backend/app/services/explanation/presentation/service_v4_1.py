"""Opt-in V4.1 presentation generation; V4 Claim Validator remains unchanged."""

from __future__ import annotations

import time

from pydantic import ValidationError

from app.services.explanation.presentation.claims_v4 import RecruiterClaimGraphV4
from app.services.explanation.presentation.contracts_v4 import RecruiterNarrativeV4
from app.services.explanation.presentation.decision_frame_v4_1 import (
    HiringDecisionFrameV1, guard_narrative_frame_v4_1,
)
from app.services.explanation.presentation.prompt_v4 import build_narrative_v4_repair_request
from app.services.explanation.presentation.prompt_v4_1 import build_narrative_v4_1_request
from app.services.explanation.presentation.service_v4 import NarrativeV4GenerationResult
from app.services.explanation.presentation.validator_v4 import diagnose_narrative_v4
from app.services.explanation.presentation.facts_v3 import _concepts


class NarrativeV4_1GenerationError(ValueError):
    def __init__(self, reason: str, diagnostics: dict[str, str] | None = None) -> None:
        self.reason = reason
        self.diagnostics = diagnostics or {}
        super().__init__("Recruiter narrative V4.1 generation failed")


def _diagnose(
    narrative: RecruiterNarrativeV4, *, frame: HiringDecisionFrameV1,
    graph: RecruiterClaimGraphV4,
) -> dict[str, str]:
    failures = diagnose_narrative_v4(narrative, graph=graph)
    if any(reason == "technical_concept_outside_claim_scope" for reason in failures.values()):
        lookup = {claim.claim_id: claim for claim in graph.claims}
        paragraphs = {"summary": narrative.summary}
        paragraphs.update({f"strengths[{i}]": item for i, item in enumerate(narrative.strengths)})
        paragraphs.update({f"risks[{i}]": item for i, item in enumerate(narrative.risks)})
        paragraphs.update({f"interview_focus[{i}]": item
                           for i, item in enumerate(narrative.interview_focus)})
        for section, reason in tuple(failures.items()):
            if reason != "technical_concept_outside_claim_scope":
                continue
            paragraph = paragraphs[section]
            allowed = {concept for ref in paragraph.claim_refs if ref in lookup
                       for concept in lookup[ref].concepts}
            extra = sorted(set(_concepts((paragraph.text,))) - allowed)
            if extra:
                failures[section] = f"{reason}; delete unsupported concepts: {', '.join(extra)}"
    try:
        guard_narrative_frame_v4_1(narrative, frame=frame, graph=graph)
    except ValueError as error:
        failures["decision_frame"] = str(error)
    return failures


async def generate_validated_narrative_v4_1(
    provider, *, frame: HiringDecisionFrameV1, graph: RecruiterClaimGraphV4,
    role_title: str, max_output_tokens: int = 4096,
) -> NarrativeV4GenerationResult:
    request = build_narrative_v4_1_request(
        frame, graph=graph, role_title=role_title, max_output_tokens=max_output_tokens)
    start = time.monotonic()
    response = await provider.generate(request)
    try:
        narrative = RecruiterNarrativeV4.model_validate_json(response.content)
    except (ValidationError, ValueError, TypeError):
        raise NarrativeV4_1GenerationError("schema_invalid") from None
    failures = _diagnose(narrative, frame=frame, graph=graph)
    if not failures:
        return NarrativeV4GenerationResult(narrative, 0, round(time.monotonic() - start, 3))
    repair = build_narrative_v4_repair_request(request, narrative, failures)
    response = await provider.generate(repair)
    try:
        narrative = RecruiterNarrativeV4.model_validate_json(response.content)
    except (ValidationError, ValueError, TypeError):
        raise NarrativeV4_1GenerationError("repair_schema_invalid", failures) from None
    final_failures = _diagnose(narrative, frame=frame, graph=graph)
    if final_failures:
        raise NarrativeV4_1GenerationError("repair_claim_or_frame_invalid", final_failures)
    return NarrativeV4GenerationResult(narrative, 1, round(time.monotonic() - start, 3))


__all__ = ["NarrativeV4_1GenerationError", "generate_validated_narrative_v4_1"]
