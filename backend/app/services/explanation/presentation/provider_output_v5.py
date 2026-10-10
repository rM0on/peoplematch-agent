"""Provider-facing V5 DTO and exact Handle-to-Claim resolution."""

from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.shared import ContractModel
from app.services.explanation.presentation.claim_handle_binding_v5 import ClaimHandleBindingV5
from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5


class ProviderParagraphV5(ContractModel):
    text: Annotated[str, StringConstraints(min_length=8, max_length=300)]
    claim_handles: list[str] = Field(min_length=1, max_length=4)


class RecruiterNarrativeV5ProviderOutput(ContractModel):
    contract_version: Literal["recruiter_narrative_v5"]
    candidate_id: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    result_rank: int = Field(ge=1, le=10)
    decision_summary: ProviderParagraphV5
    why_consider: list[ProviderParagraphV5] = Field(min_length=1, max_length=2)
    technical_signal: list[ProviderParagraphV5] = Field(min_length=1, max_length=2)
    interview_focus: list[ProviderParagraphV5] = Field(min_length=1, max_length=2)
    uncertainty: list[ProviderParagraphV5] = Field(min_length=1, max_length=2)


def build_provider_response_schema_v5(binding: ClaimHandleBindingV5) -> dict:
    """Inline paragraph schema so each field has its own native enum."""
    schema = RecruiterNarrativeV5ProviderOutput.model_json_schema()
    paragraph = schema.pop("$defs")["ProviderParagraphV5"]
    for field in ("decision_summary", "why_consider", "technical_signal",
                  "interview_focus", "uncertainty"):
        inline = deepcopy(paragraph)
        inline["properties"]["claim_handles"]["items"] = {
            "type": "string", "enum": list(binding.allowed_handles(field)),
        }
        if field == "decision_summary":
            schema["properties"][field] = inline
        else:
            schema["properties"][field]["items"] = inline
    return schema


def resolve_provider_output_v5(
    output: RecruiterNarrativeV5ProviderOutput, binding: ClaimHandleBindingV5,
) -> RecruiterNarrativeV5:
    if output.candidate_id != binding.candidate_id or output.result_rank != binding.result_rank:
        raise ValueError("provider_output_candidate_mismatch")

    def paragraph(item: ProviderParagraphV5, field: str) -> dict:
        return {"text": item.text,
                "claim_refs": binding.resolve(item.claim_handles, field=field)}

    return RecruiterNarrativeV5.model_validate({
        "contract_version": output.contract_version,
        "candidate_id": output.candidate_id,
        "result_rank": output.result_rank,
        "decision_summary": paragraph(output.decision_summary, "decision_summary"),
        **{field: [paragraph(item, field) for item in getattr(output, field)]
           for field in ("why_consider", "technical_signal", "interview_focus", "uncertainty")},
    })


__all__ = ["ProviderParagraphV5", "RecruiterNarrativeV5ProviderOutput",
           "build_provider_response_schema_v5", "resolve_provider_output_v5"]
