"""V5 natural-language generation guarded by unchanged V4 and V4.1 checks."""

from __future__ import annotations

from dataclasses import dataclass
import time

from pydantic import ValidationError

from app.services.explanation.presentation.claims_v4 import RecruiterClaimGraphV4
from app.services.explanation.presentation.claim_handle_binding_v5 import build_claim_handle_binding_v5
from app.services.explanation.presentation.contracts_v4 import RecruiterNarrativeV4
from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
from app.services.explanation.presentation.decision_frame_v4_1 import (
    HiringDecisionFrameV1, diagnose_narrative_frame_v4_1,
)
from app.services.explanation.presentation.hiring_context_v5 import (
    HiringContextGraphV5, guard_hiring_context_v5,
)
from app.services.explanation.presentation.prompt_v5 import (
    build_narrative_v5_repair_request, build_narrative_v5_request,
)
from app.services.explanation.presentation.provider_output_v5 import (
    RecruiterNarrativeV5ProviderOutput, resolve_provider_output_v5,
)
from app.services.explanation.presentation.validator_v4 import diagnose_narrative_v4


class NarrativeV5GenerationError(ValueError):
    def __init__(self, reason: str, diagnostics: dict[str, str] | None = None) -> None:
        self.reason = reason
        self.diagnostics = diagnostics or {}
        super().__init__("Recruiter narrative V5 generation failed")


@dataclass(frozen=True)
class NarrativeV5GenerationResult:
    narrative: RecruiterNarrativeV5
    repair_count: int
    latency_seconds: float


def diagnose_narrative_v5(
    narrative: RecruiterNarrativeV5, *, graph: RecruiterClaimGraphV4,
    frame: HiringDecisionFrameV1, context: HiringContextGraphV5,
) -> dict[str, str]:
    """Validate every V5 paragraph through both existing gates, without rewriting them."""
    try:
        guard_hiring_context_v5(context, graph=graph, frame=frame)
    except ValueError as error:
        return {"hiring_context": str(error)}
    if narrative.candidate_id != context.candidate_id or narrative.result_rank != context.result_rank:
        return {"identity": "candidate_mismatch"}
    failures: dict[str, str] = {}
    for field in ("why_consider", "technical_signal"):
        for index, paragraph in enumerate(getattr(narrative, field)):
            # A single V4 strength slot validates each V5 observation separately.
            # This retains the V4 maximum cardinality without dropping any paragraph.
            bridge = RecruiterNarrativeV4(
                contract_version="recruiter_narrative_v4",
                candidate_id=narrative.candidate_id, result_rank=narrative.result_rank,
                summary=narrative.decision_summary, strengths=[paragraph],
                risks=narrative.uncertainty, interview_focus=narrative.interview_focus,
            )
            diagnosed = diagnose_narrative_v4(bridge, graph=graph)
            for section, reason in diagnosed.items():
                target = f"{field}[{index}]" if section == "strengths[0]" else (
                    "decision_summary" if section == "summary" else
                    section.replace("risks", "uncertainty"))
                failures[target] = reason
            for section, reason in diagnose_narrative_frame_v4_1(
                bridge, frame=frame, graph=graph).items():
                target = f"{field}[{index}]" if section == "strengths[0]" else (
                    "decision_summary" if section == "summary" else
                    section.replace("risks", "uncertainty"))
                failures[f"{target}.frame"] = reason
    return failures


def validate_narrative_v5(
    narrative: RecruiterNarrativeV5, *, graph: RecruiterClaimGraphV4,
    frame: HiringDecisionFrameV1, context: HiringContextGraphV5,
) -> None:
    failures = diagnose_narrative_v5(narrative, graph=graph, frame=frame, context=context)
    if failures:
        raise NarrativeV5GenerationError("claim_or_frame_invalid", failures)


async def generate_validated_narrative_v5(
    provider, *, context: HiringContextGraphV5, graph: RecruiterClaimGraphV4,
    frame: HiringDecisionFrameV1, role_title: str, max_output_tokens: int = 4096,
    allow_schema_repair: bool = False,
) -> NarrativeV5GenerationResult:
    if allow_schema_repair:
        raise NarrativeV5GenerationError("schema_repair_unavailable_for_handle_protocol")
    binding = build_claim_handle_binding_v5(graph, frame, context)
    request = build_narrative_v5_request(
        context, graph=graph, frame=frame, role_title=role_title,
        max_output_tokens=max_output_tokens, binding=binding)
    start = time.monotonic()
    response = await provider.generate(request)
    try:
        provider_output = RecruiterNarrativeV5ProviderOutput.model_validate_json(response.content)
    except (ValidationError, ValueError, TypeError):
        raise NarrativeV5GenerationError("schema_invalid") from None
    try:
        narrative = resolve_provider_output_v5(provider_output, binding)
    except ValueError:
        raise NarrativeV5GenerationError("handle_invalid") from None
    failures = diagnose_narrative_v5(narrative, graph=graph, frame=frame, context=context)
    if not failures:
        return NarrativeV5GenerationResult(narrative, 0, round(time.monotonic() - start, 3))
    repair = build_narrative_v5_repair_request(request, provider_output, failures)
    response = await provider.generate(repair)
    try:
        provider_output = RecruiterNarrativeV5ProviderOutput.model_validate_json(response.content)
    except (ValidationError, ValueError, TypeError):
        raise NarrativeV5GenerationError("repair_schema_invalid", failures) from None
    try:
        narrative = resolve_provider_output_v5(provider_output, binding)
    except ValueError:
        raise NarrativeV5GenerationError("repair_handle_invalid", failures) from None
    final_failures = diagnose_narrative_v5(narrative, graph=graph, frame=frame, context=context)
    if final_failures:
        raise NarrativeV5GenerationError("repair_claim_or_frame_invalid", final_failures)
    return NarrativeV5GenerationResult(narrative, 1, round(time.monotonic() - start, 3))


__all__ = ["NarrativeV5GenerationError", "NarrativeV5GenerationResult",
           "diagnose_narrative_v5", "validate_narrative_v5", "generate_validated_narrative_v5"]
