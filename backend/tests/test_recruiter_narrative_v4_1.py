"""Decision Frame mapping and presentation safety, independent of V4 Validator."""

from __future__ import annotations

from dataclasses import replace
import asyncio
import json

import pytest

from app.services.explanation.presentation.adapter import NarrativeProjection
from test_recruiter_narrative_v4 import _graph, _narrative, _projection


def _open_rag_projection() -> NarrativeProjection:
    projection = _projection(open_requirement=True)
    facts = dict(projection.facts)
    facts["job_requirement:open"] = ("RAG",)
    return replace(projection, facts=facts)


def test_open_requirement_cannot_map_to_candidate_missing_skill():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        guard_claim_frame_mapping_v4_1,
    )

    graph = _graph(_open_rag_projection())
    open_claim = next(c for c in graph.claims if c.relation_type == "open_requirement")
    with pytest.raises(ValueError):
        guard_claim_frame_mapping_v4_1(open_claim, "candidate_missing_skill")


def test_open_requirement_maps_to_what_to_verify():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        guard_claim_frame_mapping_v4_1,
    )

    graph = _graph(_open_rag_projection())
    open_claim = next(c for c in graph.claims if c.relation_type == "open_requirement")
    guard_claim_frame_mapping_v4_1(open_claim, "what_to_verify")
    guard_claim_frame_mapping_v4_1(open_claim, "risk_boundary")


def test_technical_alignment_maps_to_why_consider():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        guard_claim_frame_mapping_v4_1,
    )

    graph = _graph(_projection())
    alignment = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    guard_claim_frame_mapping_v4_1(alignment, "why_consider")


def test_technical_alignment_cannot_map_to_expert_conclusion():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        guard_claim_frame_mapping_v4_1,
    )

    graph = _graph(_projection())
    alignment = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    with pytest.raises(ValueError):
        guard_claim_frame_mapping_v4_1(alignment, "candidate_expert_claim")


def test_claim_scope_must_match_the_claim_to_frame_rule():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        guard_claim_frame_mapping_v4_1,
    )

    graph = _graph(_projection())
    alignment = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    forged = alignment.model_copy(update={"allowed_expression_scope": "human_review"})
    with pytest.raises(ValueError):
        guard_claim_frame_mapping_v4_1(forged, "why_consider")


def test_risk_boundary_rejects_candidate_ability_absence():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        build_hiring_decision_frame_v4_1, guard_narrative_frame_v4_1,
    )

    projection = _open_rag_projection()
    graph = _graph(projection)
    frame = build_hiring_decision_frame_v4_1(graph)
    open_claim = next(c for c in graph.claims if c.relation_type == "open_requirement")
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"risks": [narrative.risks[0].model_copy(
        update={"text": "候选人缺少 RAG 能力，需要面试确认。",
                "claim_refs": [open_claim.claim_id]})]})
    with pytest.raises(ValueError):
        guard_narrative_frame_v4_1(changed, frame=frame, graph=graph)


def test_strength_cannot_turn_technical_alignment_into_missing_ability():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        build_hiring_decision_frame_v4_1, guard_narrative_frame_v4_1,
    )

    projection = _projection()
    graph = _graph(projection)
    frame = build_hiring_decision_frame_v4_1(graph)
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"strengths": [narrative.strengths[0].model_copy(
        update={"text": "候选人缺少 RAG 能力。"})]})
    with pytest.raises(ValueError):
        guard_narrative_frame_v4_1(changed, frame=frame, graph=graph)


def test_open_requirement_can_be_expressed_as_missing_material_not_missing_ability():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        build_hiring_decision_frame_v4_1, guard_narrative_frame_v4_1,
    )

    projection = _open_rag_projection()
    graph = _graph(projection)
    frame = build_hiring_decision_frame_v4_1(graph)
    open_claim = next(c for c in graph.claims if c.relation_type == "open_requirement")
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"risks": [narrative.risks[0].model_copy(update={
        "text": "当前材料未说明 RAG 相关实践，下一轮可询问具体参与范围。",
        "claim_refs": [open_claim.claim_id],
    })]})
    guard_narrative_frame_v4_1(changed, frame=frame, graph=graph)


def test_distinct_evidence_produces_distinct_decision_frames():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        build_hiring_decision_frame_v4_1,
    )

    rag = build_hiring_decision_frame_v4_1(_graph(_projection(technology="RAG")))
    ranking = build_hiring_decision_frame_v4_1(_graph(_projection(technology="LambdaMART")))
    rag_concepts = {concept for entry in rag.current_signal for concept in entry.concepts}
    ranking_concepts = {concept for entry in ranking.current_signal for concept in entry.concepts}
    assert rag_concepts != ranking_concepts
    assert "rag" in rag_concepts
    assert "ranking" in ranking_concepts


def test_forged_frame_or_cross_candidate_claim_fails_before_provider():
    from app.services.explanation.presentation.decision_frame_v4_1 import (
        build_hiring_decision_frame_v4_1, guard_decision_frame_v4_1,
    )

    first = _graph(_projection(candidate_id="candidate-a", rank=1))
    other = _graph(_projection(candidate_id="candidate-b", rank=2))
    frame = build_hiring_decision_frame_v4_1(first)
    guard_decision_frame_v4_1(frame, graph=first)
    with pytest.raises(ValueError):
        guard_decision_frame_v4_1(frame, graph=other)


def test_prompt_receives_only_canonical_decision_frame_and_claims():
    from app.services.explanation.presentation.decision_frame_v4_1 import build_hiring_decision_frame_v4_1
    from app.services.explanation.presentation.prompt_v4_1 import build_narrative_v4_1_request

    graph = _graph(_projection())
    frame = build_hiring_decision_frame_v4_1(graph)
    request = build_narrative_v4_1_request(
        frame, graph=graph, role_title="Synthetic Engineer", max_output_tokens=2048)
    payload = json.loads(request.user_instruction)
    assert request.output_contract_version == "recruiter_narrative_v4"
    assert payload["decision_frame"]["why_consider"]
    assert payload["claim_graph"]
    assert "atomic_fact_graph" not in payload


def test_generation_rejects_deficiency_even_when_v4_claim_validator_accepts_it():
    from app.services.explanation.generation.provider import ExplanationProviderResponse
    from app.services.explanation.presentation.decision_frame_v4_1 import build_hiring_decision_frame_v4_1
    from app.services.explanation.presentation.service_v4_1 import (
        NarrativeV4_1GenerationError, generate_validated_narrative_v4_1,
    )

    projection = _open_rag_projection()
    graph = _graph(projection)
    frame = build_hiring_decision_frame_v4_1(graph)
    open_claim = next(c for c in graph.claims if c.relation_type == "open_requirement")
    base = _narrative(projection, graph)
    invalid = base.model_copy(update={"risks": [base.risks[0].model_copy(update={
        "text": "候选人缺少 RAG 能力，需要面试确认。",
        "claim_refs": [open_claim.claim_id],
    })]})

    class Provider:
        def __init__(self):
            self.calls = 0

        async def generate(self, request):
            self.calls += 1
            return ExplanationProviderResponse(content=invalid.model_dump_json(), observed_model=None)

    provider = Provider()
    with pytest.raises(NarrativeV4_1GenerationError):
        asyncio.run(generate_validated_narrative_v4_1(
            provider, frame=frame, graph=graph, role_title=projection.role_title,
            max_output_tokens=2048))
    assert provider.calls == 2


def test_generation_accepts_supported_natural_language_without_template():
    from app.services.explanation.generation.provider import ExplanationProviderResponse
    from app.services.explanation.presentation.decision_frame_v4_1 import build_hiring_decision_frame_v4_1
    from app.services.explanation.presentation.service_v4_1 import generate_validated_narrative_v4_1

    projection = _projection()
    graph = _graph(projection)
    frame = build_hiring_decision_frame_v4_1(graph)
    expected = _narrative(projection, graph)

    class Provider:
        async def generate(self, request):
            return ExplanationProviderResponse(content=expected.model_dump_json(), observed_model=None)

    result = asyncio.run(generate_validated_narrative_v4_1(
        Provider(), frame=frame, graph=graph, role_title=projection.role_title,
        max_output_tokens=2048))
    assert result.narrative == expected
    assert result.repair_count == 0
