from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.services.explanation.presentation.contracts_v2 import RecruiterNarrativeV2


class RecruiterNarrativeV2Response(BaseModel):
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
    narrative: Optional[RecruiterNarrativeV2]


def narrative_v2_response_from_model(record) -> RecruiterNarrativeV2Response:
    return RecruiterNarrativeV2Response(
        narrative_id=record.narrative_id,
        explanation_run_id=record.explanation_run_id,
        source_explanation_id=record.source_explanation_id,
        candidate_id=record.candidate_id,
        result_rank=record.result_rank,
        ranking_fingerprint=record.ranking_fingerprint,
        status=record.status,
        validation_status=record.validation_status,
        provider_kind=record.provider_kind,
        provider_name=record.provider_name,
        configured_model=record.configured_model,
        prompt_version=record.prompt_version,
        prompt_fingerprint=record.prompt_fingerprint,
        content_fingerprint=record.content_fingerprint,
        error_code=record.error_code,
        created_at=record.created_at,
        narrative=(RecruiterNarrativeV2.model_validate(record.validated_content_json)
                   if record.status == "COMPLETED" else None),
    )


__all__ = ["RecruiterNarrativeV2Response", "narrative_v2_response_from_model"]
