from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

from app.schemas.explanations import CandidateExplanationOutput
from app.services.explanation.contracts import (
    EXPLANATION_OUTPUT_VERSION,
    candidate_output_fingerprint,
    explanation_result_fingerprint,
)
from app.services.explanation.generation.errors import (
    ExplanationPersistenceIntegrityError,
)


class ExplanationGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_k: Annotated[StrictInt, Field(ge=1, le=10)]


class ExplanationRunSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    explanation_run_id: str
    match_run_id: str
    status: str
    requested_top_k: int
    effective_top_k: Optional[int] = None
    explanation_count: int
    provider_kind: Optional[str] = None
    provider_name: Optional[str] = None
    configured_model: Optional[str] = None
    observed_model: Optional[str] = None
    prompt_version: Optional[str] = None
    attempt_count: int
    repaired: bool
    error_code: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ExplanationRunDetailResponse(ExplanationRunSummaryResponse):
    error_detail_safe: Optional[
        Annotated[
            str,
            StringConstraints(min_length=1, max_length=500),
        ]
    ] = None
    explanations: list[CandidateExplanationOutput] = Field(default_factory=list)


def explanation_summary_from_model(model) -> ExplanationRunSummaryResponse:
    return ExplanationRunSummaryResponse(
        **{
            name: getattr(model, name)
            for name in ExplanationRunSummaryResponse.model_fields
        }
    )


def explanation_detail_from_model(model) -> ExplanationRunDetailResponse:
    values = {
        name: getattr(model, name)
        for name in ExplanationRunSummaryResponse.model_fields
    }
    values["error_detail_safe"] = model.error_detail_safe
    try:
        outputs = []
        for item in model.explanations:
            output = CandidateExplanationOutput.model_validate(
                item.validated_output_json
            )
            if (
                item.candidate_id != output.candidate_id
                or item.result_rank != output.result_rank
                or item.output_schema_version != EXPLANATION_OUTPUT_VERSION
                or item.output_schema_version != output.output_schema_version
                or item.candidate_output_fingerprint
                != candidate_output_fingerprint(output)
            ):
                raise ValueError("persisted child columns diverge from output")
            outputs.append(output)
        if model.status == "COMPLETED":
            ranks = [item.result_rank for item in outputs]
            candidate_ids = [item.candidate_id for item in outputs]
            if (
                len(outputs) != model.explanation_count
                or len(outputs) != model.effective_top_k
                or ranks != list(range(1, len(outputs) + 1))
                or len(candidate_ids) != len(set(candidate_ids))
                or getattr(model, "output_schema_version", EXPLANATION_OUTPUT_VERSION)
                != EXPLANATION_OUTPUT_VERSION
                or (
                    getattr(model, "result_fingerprint", None) is not None
                    and model.result_fingerprint
                    != explanation_result_fingerprint(outputs)
                )
            ):
                raise ValueError("persisted explanation aggregate is inconsistent")
    except (TypeError, ValueError):
        raise ExplanationPersistenceIntegrityError() from None
    values["explanations"] = outputs
    return ExplanationRunDetailResponse(**values)


__all__ = [
    "ExplanationGenerationRequest",
    "ExplanationRunDetailResponse",
    "ExplanationRunSummaryResponse",
    "explanation_detail_from_model",
    "explanation_summary_from_model",
]
