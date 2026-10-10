from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from app.models.explanation_run import MatchExplanationModel
from app.schemas.explanations import (
    ExplanationOutputV1,
    InternalEvidenceBundleV1,
    ProviderEvidenceV1,
)
from app.services.explanation.contracts import (
    EXPLANATION_OUTPUT_VERSION,
    candidate_output_fingerprint,
    project_provider_evidence,
)
from app.services.explanation.evidence import (
    EvidenceBundleBuilder,
    EvidenceFactsV1,
    build_evidence_facts,
)
from app.services.explanation.generation.errors import (
    ExplanationGroundingError,
    ExplanationPlanParseError,
)
from app.services.explanation.generation.contracts import (
    ProviderExplanationPlanV1,
    bind_provider_explanation_plan,
)
from app.services.explanation.generation.grounding import ground_explanation_plan
from app.services.explanation.generation.prompt import (
    build_explanation_provider_request,
    build_explanation_selection_request,
    load_explanation_prompt_v3,
    load_explanation_prompt_v4,
)
from app.services.explanation.generation.semantic_selection import (
    ProviderExplanationSelectionV1,
    SemanticOptionCatalog,
    SemanticSelectionError,
    bind_semantic_selection,
    build_semantic_option_catalog,
)
from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.explanation.generation.reference_projection import (
    ProjectedProviderEvidence,
    ProviderReferenceProjector,
)
from app.services.explanation.generation.rendering import render_explanation_output


@dataclass(frozen=True)
class PreparedExplanationGeneration:
    evidence_bundle: InternalEvidenceBundleV1
    provider_evidence: ProviderEvidenceV1
    evidence_facts: EvidenceFactsV1
    projected: ProjectedProviderEvidence
    initial_request: ExplanationProviderRequest
    effective_top_k: int
    catalog: SemanticOptionCatalog | None


class ExplanationGenerationPipeline:
    """Pure historical preparation, grounding, and deterministic rendering."""

    def __init__(
        self,
        *,
        max_output_tokens: int,
        max_prompt_bytes: int = 131072,
        protocol_version: str = "v4",
    ) -> None:
        if protocol_version not in {"v3", "v4"}:
            raise ValueError("unsupported explanation provider protocol")
        self.protocol_version = protocol_version
        self.max_output_tokens = max_output_tokens
        self.max_prompt_bytes = max_prompt_bytes
        prompt = load_explanation_prompt_v4() if protocol_version == "v4" else load_explanation_prompt_v3()
        self.prompt_version = prompt.prompt_version
        self.prompt_fingerprint = prompt.prompt_fingerprint

    def prepare(
        self,
        historical_run,
        *,
        requested_top_k: int,
    ) -> PreparedExplanationGeneration:
        if type(requested_top_k) is not int or not 1 <= requested_top_k <= 10:
            raise ValueError("requested top-k must be an integer from one to ten")
        full_bundle = EvidenceBundleBuilder().build(historical_run)
        effective_top_k = min(requested_top_k, len(full_bundle.candidates))
        if effective_top_k < 1:
            raise ValueError("completed MatchRun has no historical Candidate results")
        bundle_payload = full_bundle.model_dump(mode="json", exclude_none=False)
        bundle_payload["candidates"] = bundle_payload["candidates"][:effective_top_k]
        bundle = InternalEvidenceBundleV1.model_validate(bundle_payload)
        facts = build_evidence_facts(bundle)
        provider_evidence = project_provider_evidence(bundle)
        projected = ProviderReferenceProjector().project(
            bundle=bundle,
            evidence_facts=facts,
        )
        catalog = None
        if self.protocol_version == "v4":
            catalog = build_semantic_option_catalog(
                bundle=bundle, evidence_facts=facts, projected=projected,
            )
            request = build_explanation_selection_request(
                catalog, max_output_tokens=self.max_output_tokens,
                max_prompt_bytes=self.max_prompt_bytes,
            )
        else:
            request = build_explanation_provider_request(
                projected.payload, max_output_tokens=self.max_output_tokens,
                max_prompt_bytes=self.max_prompt_bytes,
            )
        return PreparedExplanationGeneration(
            evidence_bundle=bundle,
            provider_evidence=provider_evidence,
            evidence_facts=facts,
            projected=projected,
            initial_request=request,
            effective_top_k=effective_top_k,
            catalog=catalog,
        )

    def repair_request(
        self,
        prepared: PreparedExplanationGeneration,
        *,
        error_category: str,
        prior_provider_output: str | None = None,
    ) -> ExplanationProviderRequest:
        category = {
            "invalid_output": "schema_invalid",
            "grounding_failure": "grounding_invalid",
            "malformed_response": "malformed_response",
        }.get(error_category)
        if category is None:
            raise ValueError("repair category is not supported")
        if self.protocol_version == "v3":
            return build_explanation_provider_request(
                prepared.projected.payload,
                max_output_tokens=self.max_output_tokens,
                max_prompt_bytes=self.max_prompt_bytes,
                repair_category=category,
                prior_provider_output=prior_provider_output,
            )
        if prepared.catalog is None:
            raise ValueError("semantic option catalog is unavailable")
        return build_explanation_selection_request(
            prepared.catalog, max_output_tokens=self.max_output_tokens,
            max_prompt_bytes=self.max_prompt_bytes, repair_category=category,
        )

    def validate_and_render(
        self,
        content: str,
        prepared: PreparedExplanationGeneration,
    ) -> ExplanationOutputV1:
        try:
            if self.protocol_version == "v3":
                provider_plan = ProviderExplanationPlanV1.model_validate_json(content)
                plan = bind_provider_explanation_plan(provider_plan)
            else:
                if prepared.catalog is None:
                    raise ValueError("semantic option catalog is unavailable")
                provider_selection = ProviderExplanationSelectionV1.model_validate_json(content)
                plan = bind_semantic_selection(provider_selection, catalog=prepared.catalog)
        except SemanticSelectionError as error:
            raise ExplanationPlanParseError(
                stage="schema_validation", reason_code=error.reason_code,
                field_path="candidates",
            ) from None
        except ValidationError as error:
            first = error.errors(include_url=False, include_context=False)[0]
            reason_code = first["type"]
            field_path = ".".join(str(part) for part in first["loc"]) or "root"
            raise ExplanationPlanParseError(
                stage="json_decode" if reason_code == "json_invalid" else "schema_validation",
                reason_code=reason_code,
                field_path=field_path,
            ) from None
        except (ValueError, TypeError):
            raise ExplanationPlanParseError() from None
        try:
            grounded = ground_explanation_plan(
                plan,
                reference_map=prepared.projected.reference_map,
                bundle=prepared.evidence_bundle,
                evidence_facts=prepared.evidence_facts,
            )
            return render_explanation_output(
                grounded,
                bundle=prepared.evidence_bundle,
                evidence_facts=prepared.evidence_facts,
            )
        except (ValidationError, ValueError):
            raise ExplanationGroundingError() from None

    def persistence_models(
        self,
        rendered: ExplanationOutputV1,
        *,
        explanation_run_id: str,
        match_run,
    ) -> list[MatchExplanationModel]:
        results = {
            (result.candidate_id, result.result_rank): result
            for result in match_run.results
        }
        models = []
        for output in rendered.candidates:
            source = results.get((output.candidate_id, output.result_rank))
            if source is None or getattr(source, "id", None) is None:
                raise ExplanationGroundingError()
            models.append(
                MatchExplanationModel(
                    explanation_run_id=explanation_run_id,
                    match_result_id=source.id,
                    candidate_id=output.candidate_id,
                    result_rank=output.result_rank,
                    output_schema_version=EXPLANATION_OUTPUT_VERSION,
                    validated_output_json=output.model_dump(
                        mode="json", exclude_none=False
                    ),
                    candidate_output_fingerprint=candidate_output_fingerprint(
                        output
                    ),
                )
            )
        return models


__all__ = [
    "ExplanationGenerationPipeline",
    "PreparedExplanationGeneration",
]
