"""V4 claim graph and claim-scoped narrative safety gates."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3
from app.services.explanation.presentation.claims_v4 import build_recruiter_claim_graph_v4
from app.services.explanation.presentation.contracts_v4 import RecruiterNarrativeV4
from app.services.explanation.presentation.validator_v4 import validate_narrative_v4


def _projection(*, candidate_id="candidate-a", rank=1, technology="RAG", open_requirement=False):
    refs = {f"candidate:{rank}:project:sample", "job_requirement:technology"}
    facts = {f"candidate:{rank}:project:sample": (f"{technology} project practice",),
             "job_requirement:technology": (technology,)}
    if open_requirement:
        refs.add("job_requirement:open")
        facts["job_requirement:open"] = ("production operation",)
    return NarrativeProjection(candidate_id=candidate_id, result_rank=rank,
                               role_title="Synthetic Engineer", facts=facts,
                               verification_status={}, positive_refs=frozenset(refs),
                               risk_refs=frozenset({"job_requirement:open"}) if open_requirement else frozenset(),
                               interview_refs=frozenset(refs))


def _graph(projection):
    return build_recruiter_claim_graph_v4(build_atomic_fact_graph_v3(projection))


def _narrative(projection, graph, *, text=None, claim_id=None):
    alignment = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    focus = next(c for c in graph.claims if c.claim_type == "interview_focus")
    review = next(c for c in graph.claims if c.claim_type == "review_recommendation")
    return RecruiterNarrativeV4.model_validate({
        "contract_version": "recruiter_narrative_v4", "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "summary": {"text": "建议优先安排人工技术复核，重点确认项目参与范围。",
                    "claim_refs": [review.claim_id]},
        "strengths": [{"text": text or "候选材料中的 RAG 项目与岗位方向有关。",
                       "claim_refs": [claim_id or alignment.claim_id]}],
        "risks": [{"text": "项目参与范围尚需面试确认。", "claim_refs": [focus.claim_id]}],
        "interview_focus": [{"text": "下一轮可询问 RAG 方案取舍及实际参与范围。",
                             "claim_refs": [focus.claim_id]}],
    })


def test_rag_fact_yields_technical_alignment_with_real_sources():
    projection = _projection()
    graph = _graph(projection)
    alignment = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    facts = {f.fact_id: f for f in graph.fact_graph.facts}
    assert {facts[i].kind for i in alignment.source_fact_ids} == {"project_evidence", "job_alignment"}
    validate_narrative_v4(_narrative(projection, graph), graph=graph)


def test_rag_fact_cannot_become_enterprise_ownership():
    projection = _projection()
    graph = _graph(projection)
    with pytest.raises(ValueError):
        validate_narrative_v4(_narrative(projection, graph,
            text="候选人负责企业级 RAG 平台建设。"), graph=graph)


def test_open_requirement_yields_interview_focus_not_ability():
    projection = _projection(open_requirement=True)
    graph = _graph(projection)
    open_fact = next(f for f in graph.fact_graph.facts if f.kind == "open_requirement")
    related = [c for c in graph.claims if open_fact.fact_id in c.source_fact_ids]
    assert related and {c.claim_type for c in related} == {"interview_focus"}


def test_open_requirement_cannot_assert_candidate_ability():
    projection = _projection(open_requirement=True)
    graph = _graph(projection)
    open_claim = next(c for c in graph.claims if any(
        f.kind == "open_requirement" and f.fact_id in c.source_fact_ids
        for f in graph.fact_graph.facts))
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"interview_focus": [narrative.interview_focus[0].model_copy(
        update={"text": "候选人具备生产运维能力。", "claim_refs": [open_claim.claim_id]})]})
    with pytest.raises(ValueError):
        validate_narrative_v4(changed, graph=graph)


def test_python_fastapi_are_distinct_technical_entities():
    graph = _graph(_projection(technology="Python/FastAPI"))
    alignments = [c for c in graph.claims if c.claim_type == "technical_alignment"]
    assert {topic for c in alignments for topic in c.concepts} >= {"python", "fastapi"}
    assert "python/fastapi" not in {topic for c in alignments for topic in c.concepts}


def test_cross_candidate_claim_reference_fails():
    first = _projection()
    other = _projection(candidate_id="candidate-b", rank=2)
    graph = _graph(first)
    other_graph = _graph(other)
    other_claim = next(c for c in other_graph.claims if c.claim_type == "technical_alignment")
    with pytest.raises(ValueError):
        validate_narrative_v4(_narrative(first, graph, claim_id=other_claim.claim_id), graph=graph)


def test_existing_claim_cannot_exceed_expression_scope():
    projection = _projection()
    graph = _graph(projection)
    with pytest.raises(ValueError):
        validate_narrative_v4(_narrative(projection, graph,
            text="候选人主导 RAG 项目并将检索准确率提高 50%。"), graph=graph)


def test_claim_graph_is_deterministic_and_read_only():
    projection = _projection()
    facts = build_atomic_fact_graph_v3(projection)
    before = repr(facts)
    assert _graph(projection) == _graph(projection)
    assert repr(facts) == before


def test_v4_prompt_sends_only_precomputed_claims():
    from app.services.explanation.presentation.prompt_v4 import build_narrative_v4_request

    graph = _graph(_projection())
    request = build_narrative_v4_request(graph, role_title="Synthetic Engineer",
                                         max_output_tokens=2048)
    assert request.output_contract_version == "recruiter_narrative_v4"
    assert '"claim_graph"' in request.user_instruction
    assert '"atomic_fact_graph"' not in request.user_instruction
    assert "approved_copy" not in request.user_instruction


def test_v4_contract_requires_claim_reference_per_paragraph():
    from pydantic import ValidationError

    projection = _projection()
    graph = _graph(projection)
    payload = _narrative(projection, graph).model_dump(mode="json")
    payload["strengths"][0]["claim_refs"] = []
    with pytest.raises(ValidationError):
        RecruiterNarrativeV4.model_validate(payload)


def test_role_label_engineer_is_not_a_candidate_capability_claim():
    projection = _projection()
    graph = _graph(projection)
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"summary": narrative.summary.model_copy(
        update={"text": "建议优先安排 Engineer 岗位的人工技术复核。"})})
    validate_narrative_v4(changed, graph=graph)


def test_prompt_forbids_unlisted_adjacent_technology_inference():
    from app.services.explanation.presentation.prompt_v4 import load_narrative_v4_prompt

    instruction = load_narrative_v4_prompt().system_instruction
    assert "RAG 不自动证明 Retrieval" in instruction


def test_repair_request_is_bounded_to_existing_claim_graph():
    from app.services.explanation.presentation.prompt_v4 import (
        build_narrative_v4_repair_request, build_narrative_v4_request,
    )

    projection = _projection()
    graph = _graph(projection)
    request = build_narrative_v4_request(graph, role_title=projection.role_title,
                                         max_output_tokens=2048)
    repair = build_narrative_v4_repair_request(
        request, _narrative(projection, graph),
        {"strengths[0]": "technical_concept_outside_claim_scope"},
    )
    assert repair.output_contract_version == "recruiter_narrative_v4"
    assert "technical_concept_outside_claim_scope" in repair.user_instruction
    assert '"claim_graph"' in repair.user_instruction
    assert "不得创建新的 Claim" in repair.system_instruction


def test_v4_generation_allows_one_validated_claim_repair():
    from app.services.explanation.generation.provider import ExplanationProviderResponse
    from app.services.explanation.presentation.service_v4 import generate_validated_narrative_v4

    projection = _projection()
    graph = _graph(projection)
    valid = _narrative(projection, graph)
    invalid = _narrative(projection, graph, text="候选人负责企业级 RAG 平台建设。")

    class Provider:
        def __init__(self):
            self.calls = []

        async def generate(self, request):
            self.calls.append(request)
            content = invalid if len(self.calls) == 1 else valid
            return ExplanationProviderResponse(content=content.model_dump_json(), observed_model=None)

    provider = Provider()
    result = asyncio.run(generate_validated_narrative_v4(
        provider, graph=graph, role_title=projection.role_title, max_output_tokens=2048))
    assert result.narrative == valid
    assert result.repair_count == 1
    assert len(provider.calls) == 2


def test_v4_generation_rejects_second_invalid_output():
    from app.services.explanation.generation.provider import ExplanationProviderResponse
    from app.services.explanation.presentation.service_v4 import (
        NarrativeV4GenerationError, generate_validated_narrative_v4,
    )

    projection = _projection()
    graph = _graph(projection)
    invalid = _narrative(projection, graph, text="候选人负责企业级 RAG 平台建设。")

    class Provider:
        def __init__(self):
            self.calls = 0

        async def generate(self, request):
            self.calls += 1
            return ExplanationProviderResponse(content=invalid.model_dump_json(), observed_model=None)

    provider = Provider()
    with pytest.raises(NarrativeV4GenerationError) as failure:
        asyncio.run(generate_validated_narrative_v4(
            provider, graph=graph, role_title=projection.role_title, max_output_tokens=2048))
    assert provider.calls == 2
    assert failure.value.diagnostics["strengths[0]"] == "forbidden_responsibility_scale_outcome_or_hiring_decision"


@pytest.mark.parametrize("unsupported", [
    "候选人构建了 RAG 系统并主导架构。",
    "候选人拥有丰富的 RAG 实战经验。",
])
def test_claim_scope_rejects_unverified_ownership_and_experience_grade(unsupported):
    projection = _projection()
    graph = _graph(projection)
    with pytest.raises(ValueError):
        validate_narrative_v4(_narrative(projection, graph, text=unsupported), graph=graph)
