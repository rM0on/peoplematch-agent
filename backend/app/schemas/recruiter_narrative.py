from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.services.explanation.presentation.contracts import RecruiterNarrativeV1


class RecruiterNarrativeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative_id: str
    explanation_run_id: str
    source_explanation_id: int
    candidate_id: str
    result_rank: int
    ranking_fingerprint: str
    status: str
    validation_status: str
    provider_kind: str
    provider_name: str
    configured_model: str
    prompt_version: str
    prompt_fingerprint: str
    content_fingerprint: Optional[str]
    error_code: Optional[str]
    created_at: Optional[datetime]
    narrative: Optional[RecruiterNarrativeV1]


def narrative_response_from_model(model) -> RecruiterNarrativeResponse:
    return RecruiterNarrativeResponse(
        narrative_id=model.narrative_id,
        explanation_run_id=model.explanation_run_id,
        source_explanation_id=model.source_explanation_id,
        candidate_id=model.candidate_id,
        result_rank=model.result_rank,
        ranking_fingerprint=model.ranking_fingerprint,
        status=model.status,
        validation_status=model.validation_status,
        provider_kind=model.provider_kind,
        provider_name=model.provider_name,
        configured_model=model.configured_model,
        prompt_version=model.prompt_version,
        prompt_fingerprint=model.prompt_fingerprint,
        content_fingerprint=model.content_fingerprint,
        error_code=model.error_code,
        created_at=model.created_at,
        narrative=(
            RecruiterNarrativeV1.model_validate(model.validated_content_json)
            if model.status == "COMPLETED" else None
        ),
    )


__all__ = ["RecruiterNarrativeResponse", "narrative_response_from_model"]
