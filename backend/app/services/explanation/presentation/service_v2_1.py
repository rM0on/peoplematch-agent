from __future__ import annotations

import json
import re
from uuid import uuid4

from pydantic import ValidationError

from app.exceptions import ProviderUnavailableError
from app.models.recruiter_narrative import RecruiterNarrativeModel
from app.services.explanation.generation.provider import ExplanationProviderError
from app.services.explanation.presentation.adapter import build_narrative_projection
from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
from app.services.explanation.presentation.facts_v2_1 import build_atomic_facts_v2_1
from app.services.explanation.presentation.prompt_v2_1 import (
    build_narrative_v2_1_repair_request, build_narrative_v2_1_request, load_narrative_v2_1_prompt,
)
from app.services.explanation.presentation.service import NarrativeGenerationFailedError, NarrativeSourceNotFoundError
from app.services.explanation.presentation.validator import NarrativeValidationError
from app.services.explanation.presentation.validator_v2_1 import (
    NarrativeV2_1ValidationError, invalid_narrative_v2_1_sections,
    validation_error_summary_v2_1, validate_narrative_v2_1,
)
from app.services.match_runs.contracts import canonical_fingerprint


_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")


class RecruiterNarrativeV2_1Service:
    def __init__(self, *, repository, provider=None, max_output_tokens: int = 2048) -> None:
        self.repository = repository
        self.provider = provider
        self.max_output_tokens = max_output_tokens

    async def generate(self, match_explanation_id: int) -> RecruiterNarrativeModel:
        if self.provider is None:
            raise ProviderUnavailableError("Recruiter narrative provider is not configured")
        source = await self.repository.load_source(match_explanation_id)
        if source is None:
            raise NarrativeSourceNotFoundError()
        try:
            projection = build_narrative_projection(bundle=source.bundle, source=source.output)
            facts = build_atomic_facts_v2_1(projection)
            if not any(f.kind == "requirement_alignment" for f in facts):
                raise NarrativeV2_1ValidationError()
        except (NarrativeValidationError, NarrativeV2_1ValidationError):
            raise NarrativeGenerationFailedError("", "source_evidence_unavailable") from None
        prompt = load_narrative_v2_1_prompt()
        descriptor = self.provider.descriptor
        record = RecruiterNarrativeModel(
            narrative_id=str(uuid4()),
            explanation_run_id=source.explanation_run_id,
            source_explanation_id=match_explanation_id,
            candidate_id=source.output.candidate_id,
            result_rank=source.output.result_rank,
            source_output_fingerprint=source.candidate_output_fingerprint,
            source_bundle_fingerprint=source.evidence_bundle_fingerprint,
            ranking_fingerprint=source.bundle.source.result_fingerprint,
            provider_kind=descriptor.kind,
            provider_name=descriptor.name,
            configured_model=descriptor.configured_model,
            observed_model=None,
            provider_configuration_fingerprint=descriptor.configuration_fingerprint,
            prompt_version=prompt.version,
            prompt_fingerprint=prompt.fingerprint,
            status="FAILED",
            validation_status="FAILED",
            validated_content_json=None,
            content_fingerprint=None,
            error_code="internal_error",
        )
        try:
            request = build_narrative_v2_1_request(
                facts, candidate_id=source.output.candidate_id,
                result_rank=source.output.result_rank, role_title=projection.role_title,
                max_output_tokens=self.max_output_tokens,
            )
            response = await self.provider.generate(request)
            try:
                narrative = RecruiterNarrativeV2_1.model_validate(json.loads(response.content))
            except (ValidationError, ValueError, TypeError):
                record.error_code = "schema_invalid"
                raise NarrativeV2_1ValidationError() from None
            try:
                validate_narrative_v2_1(narrative, facts=facts, bundle=source.bundle, source=source.output)
            except NarrativeV2_1ValidationError:
                invalid_sections = invalid_narrative_v2_1_sections(narrative, projection=projection)
                if (narrative.candidate_id != source.output.candidate_id
                        or narrative.result_rank != source.output.result_rank or not invalid_sections):
                    raise
                repair = build_narrative_v2_1_repair_request(
                    request, narrative, validation_error_summary_v2_1(narrative, projection=projection),
                )
                response = await self.provider.generate(repair)
                try:
                    narrative = RecruiterNarrativeV2_1.model_validate(json.loads(response.content))
                except (ValidationError, ValueError, TypeError):
                    record.error_code = "schema_invalid"
                    raise NarrativeV2_1ValidationError() from None
                validate_narrative_v2_1(narrative, facts=facts, bundle=source.bundle, source=source.output)
            record.status = "COMPLETED"
            record.validation_status = "PASSED"
            record.validated_content_json = narrative.model_dump(mode="json")
            record.content_fingerprint = canonical_fingerprint(record.validated_content_json)
            record.observed_model = (
                response.observed_model if response.observed_model
                and _SAFE_MODEL.fullmatch(response.observed_model) else None
            )
            record.error_code = None
        except NarrativeV2_1ValidationError:
            if record.error_code == "internal_error":
                record.error_code = "grounding_invalid"
        except ExplanationProviderError as error:
            record.error_code = {
                "timeout": "provider_timeout", "rate_limited": "provider_rate_limited",
                "transport": "provider_unavailable",
            }.get(error.category, "provider_unavailable")
        await self.repository.save(record)
        if record.status != "COMPLETED":
            raise NarrativeGenerationFailedError(record.narrative_id, record.error_code)
        return record

    async def get(self, narrative_id: str) -> RecruiterNarrativeModel:
        record = await self.repository.get(narrative_id)
        if record is None or record.prompt_version != "recruiter_narrative_prompt_v2_1":
            raise NarrativeSourceNotFoundError()
        if record.status == "COMPLETED":
            try:
                narrative = RecruiterNarrativeV2_1.model_validate(record.validated_content_json)
                if record.content_fingerprint != canonical_fingerprint(narrative.model_dump(mode="json")):
                    raise ValueError("content fingerprint mismatch")
            except (ValidationError, ValueError):
                raise NarrativeGenerationFailedError(record.narrative_id, "stored_content_invalid") from None
        return record


__all__ = ["RecruiterNarrativeV2_1Service"]
