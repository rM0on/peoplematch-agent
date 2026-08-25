from __future__ import annotations

import asyncio
import json

from app.core.config import Settings
from app.services.explanation.evidence import build_evidence_facts
from app.services.explanation.generation.contracts import ExplanationPlanV1
from app.services.explanation.generation.prompt import (
    build_explanation_provider_request,
)
from app.services.explanation.generation.reference_projection import (
    ProviderReferenceProjector,
)
from test_explanation_generation_contracts import _bundle, _two_candidate_bundle
from test_explanation_grounding_rendering import _missing_requirement_bundle


def _request(bundle):
    facts = build_evidence_facts(bundle)
    projected = ProviderReferenceProjector().project(
        bundle=bundle,
        evidence_facts=facts,
    )
    return projected, build_explanation_provider_request(
        projected.payload,
        max_output_tokens=512,
    )


def test_mock_provider_is_deterministic_closed_and_offline() -> None:
    from app.services.explanation.generation.mock_provider import (
        DeterministicExplanationProvider,
    )

    projected, request = _request(_bundle())
    provider = DeterministicExplanationProvider()

    first = asyncio.run(provider.generate(request))
    second = asyncio.run(provider.generate(request))
    first_plan = ExplanationPlanV1.model_validate_json(first.content)
    second_plan = ExplanationPlanV1.model_validate_json(second.content)

    assert first == second
    assert first_plan == second_plan
    assert provider.descriptor.kind == "deterministic"
    assert provider.descriptor.name == "mock"
    assert first.observed_model == provider.descriptor.configured_model
    serialized = first.content
    assert "candidate:" not in serialized
    assert "job_requirement:" not in serialized
    assert "workflow_fingerprint" not in serialized
    assert "text" not in serialized
    assert first_plan.candidates[0].candidate_ref == (
        projected.payload.candidates[0].candidate_ref
    )


def test_mock_provider_selects_only_exact_fact_tuples_and_deterministic_gaps() -> None:
    from app.services.explanation.generation.mock_provider import (
        DeterministicExplanationProvider,
    )

    bundle = _missing_requirement_bundle()
    projected, request = _request(bundle)
    plan = ExplanationPlanV1.model_validate_json(
        asyncio.run(DeterministicExplanationProvider().generate(request)).content
    )
    candidate = plan.candidates[0]
    prompt_facts = projected.payload.candidates[0].facts

    exact_reasons = {
        (item.category, item.statement_key, tuple(item.evidence_refs))
        for item in prompt_facts.match_reasons
    }
    exact_ranking = {
        ("ranking_context", "ranking_context_recorded", tuple(item.evidence_refs))
        for item in prompt_facts.ranking_context
    }
    assert all(
        (item.category, item.template_key, tuple(item.evidence_refs))
        in exact_reasons | exact_ranking
        for item in candidate.match_reasons
    )
    assert [
        item.model_dump(mode="json")
        for item in candidate.interview_question_operations
    ] == [
        {
            "operation": "ask_evidence_clarification",
            "evidence_refs": prompt_facts.missing_requirements[0].evidence_refs,
        }
    ]
    assert candidate.rewrite_operations == []
    assert "missing_skills" not in json.loads(
        asyncio.run(DeterministicExplanationProvider().generate(request)).content
    )["candidates"][0]


def test_mock_provider_preserves_candidate_coverage_and_top1_structure() -> None:
    from app.services.explanation.generation.mock_provider import (
        DeterministicExplanationProvider,
    )

    projected, request = _request(_two_candidate_bundle())
    plan = ExplanationPlanV1.model_validate_json(
        asyncio.run(DeterministicExplanationProvider().generate(request)).content
    )

    assert [item.result_rank for item in plan.candidates] == [1, 2]
    assert plan.candidates[0].why_not_top1 is None
    assert plan.candidates[1].why_not_top1.evidence_refs == (
        projected.payload.candidates[1].facts.comparison.evidence_refs
    )


def test_provider_factory_supports_offline_mock_without_credentials() -> None:
    from app.services.explanation.generation.factory import build_explanation_provider
    from app.services.explanation.generation.mock_provider import (
        DeterministicExplanationProvider,
    )

    provider = build_explanation_provider(
        Settings(_env_file=None, explanation_provider="mock")
    )

    assert isinstance(provider, DeterministicExplanationProvider)
    assert "key" not in repr(provider).casefold()
