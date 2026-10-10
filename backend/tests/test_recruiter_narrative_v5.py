"""V5 hiring context and narrative preserve existing claim/frame gates."""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from app.services.explanation.presentation.decision_frame_v4_1 import build_hiring_decision_frame_v4_1
from test_recruiter_narrative_v4 import _graph, _projection


def _inputs(*, candidate_id: str = "candidate-a", rank: int = 1, technology: str = "RAG"):
    projection = _projection(candidate_id=candidate_id, rank=rank, technology=technology,
                             open_requirement=True)
    graph = _graph(projection)
    return projection, graph, build_hiring_decision_frame_v4_1(graph)


def _payload(graph):
    review = next(c for c in graph.claims if c.claim_type == "review_recommendation")
    alignment = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    focus = next(c for c in graph.claims if c.claim_type == "interview_focus"
                 and c.relation_type == "verify_observed_scope")
    open_focus = next(c for c in graph.claims if c.relation_type == "open_requirement")
    concept = "RAG" if "rag" in alignment.concepts else "LambdaMART"
    return {
        "contract_version": "recruiter_narrative_v5", "candidate_id": graph.candidate_id,
        "result_rank": graph.result_rank,
        "decision_summary": {"text": "建议安排人工技术面，进一步了解候选人的项目参与范围。",
                             "claim_refs": [review.claim_id]},
        "why_consider": [{"text": f"候选材料中的 {concept} 项目与岗位方向有关。",
                          "claim_refs": [alignment.claim_id]}],
        "technical_signal": [{"text": f"现有项目记录包含 {concept} 相关实践。",
                              "claim_refs": [alignment.claim_id]}],
        "interview_focus": [{"text": f"下一轮可询问 {concept} 项目的方案取舍及实际参与范围。",
                             "claim_refs": [focus.claim_id]}],
        "uncertainty": [{"text": "当前材料尚未说明生产运维实践，面试可确认具体参与范围。",
                         "claim_refs": [open_focus.claim_id]}],
    }


def test_hiring_context_is_canonical_and_candidate_specific():
    from app.services.explanation.presentation.hiring_context_v5 import (
        build_hiring_context_v5, guard_hiring_context_v5,
    )

    _, rag_graph, rag_frame = _inputs()
    _, ranking_graph, ranking_frame = _inputs(
        candidate_id="candidate-b", rank=2, technology="LambdaMART")
    rag = build_hiring_context_v5(rag_graph, rag_frame)
    ranking = build_hiring_context_v5(ranking_graph, ranking_frame)
    guard_hiring_context_v5(rag, graph=rag_graph, frame=rag_frame)
    assert rag.candidate_signal != ranking.candidate_signal
    assert rag.why_this_matters != ranking.why_this_matters
    with pytest.raises(ValueError):
        guard_hiring_context_v5(rag, graph=ranking_graph, frame=ranking_frame)


def test_hiring_context_cannot_invent_responsibility_or_candidate_deficit():
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5

    _, graph, frame = _inputs()
    context = build_hiring_context_v5(graph, frame)
    assert all(item.claim_refs for item in context.why_this_matters)
    assert all(item.claim_refs for item in context.uncertainty_boundary)
    assert not hasattr(context, "candidate_responsibility")
    assert not hasattr(context, "candidate_missing_skill")


def test_v5_contract_requires_claim_refs_in_every_section():
    from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5

    _, graph, _ = _inputs()
    payload = _payload(graph)
    RecruiterNarrativeV5.model_validate(payload)
    payload["why_consider"][0]["claim_refs"] = []
    with pytest.raises(ValidationError):
        RecruiterNarrativeV5.model_validate(payload)


def test_v5_prompt_receives_context_and_rejects_fixed_copy():
    from app.services.explanation.presentation.claim_handle_binding_v5 import build_claim_handle_binding_v5
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
    from app.services.explanation.presentation.prompt_v5 import build_narrative_v5_request

    projection, graph, frame = _inputs()
    context = build_hiring_context_v5(graph, frame)
    binding = build_claim_handle_binding_v5(graph, frame, context)
    request = build_narrative_v5_request(
        context, graph=graph, frame=frame, role_title=projection.role_title,
        max_output_tokens=2048)
    payload = json.loads(request.user_instruction)
    assert payload["hiring_context"]["why_this_matters"]
    assert payload["hiring_context"]["uncertainty_boundary"]
    assert request.output_contract_version == "recruiter_narrative_v5"
    assert request.response_schema["properties"]["why_consider"]["type"] == "array"
    assert request.response_schema["properties"]["why_consider"]["items"]["properties"]["claim_handles"]["items"]["enum"] == list(binding.allowed_handles("why_consider"))
    assert "approved_copy" not in request.user_instruction
    assert "不要罗列技术关键词" in request.system_instruction


def test_v5_prompt_requires_short_handles_not_opaque_ids():
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
    from app.services.explanation.presentation.prompt_v5 import build_narrative_v5_request

    projection, graph, frame = _inputs()
    request = build_narrative_v5_request(
        build_hiring_context_v5(graph, frame), graph=graph, frame=frame,
        role_title=projection.role_title, max_output_tokens=2048)
    assert "claim_handles 只能使用" in request.system_instruction
    assert "逐字符复制输入的 claim_id" not in request.system_instruction


def test_v5_allows_natural_multi_claim_expression():
    from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
    from app.services.explanation.presentation.service_v5 import validate_narrative_v5

    _, graph, frame = _inputs()
    context = build_hiring_context_v5(graph, frame)
    payload = _payload(graph)
    alignment = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    skill = next(c for c in graph.claims if c.claim_type == "skill_requirement_match") if any(
        c.claim_type == "skill_requirement_match" for c in graph.claims) else alignment
    payload["why_consider"][0]["claim_refs"] = list(dict.fromkeys([alignment.claim_id, skill.claim_id]))
    validate_narrative_v5(RecruiterNarrativeV5.model_validate(payload),
                          graph=graph, frame=frame, context=context)


@pytest.mark.parametrize("unsafe_text,field", [
    ("候选人负责企业级 RAG 平台建设。", "why_consider"),
    ("候选人缺少生产运维能力，下一轮需要面试确认。", "uncertainty"),
])
def test_v5_reuses_existing_safety_for_duty_and_missing_skill(unsafe_text, field):
    from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
    from app.services.explanation.presentation.service_v5 import validate_narrative_v5

    _, graph, frame = _inputs()
    context = build_hiring_context_v5(graph, frame)
    payload = _payload(graph)
    payload[field][0]["text"] = unsafe_text
    with pytest.raises(ValueError):
        validate_narrative_v5(RecruiterNarrativeV5.model_validate(payload),
                              graph=graph, frame=frame, context=context)


def test_v5_cross_candidate_claim_reference_fails():
    from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
    from app.services.explanation.presentation.service_v5 import validate_narrative_v5

    _, graph, frame = _inputs()
    _, other, _ = _inputs(candidate_id="candidate-b", rank=2)
    context = build_hiring_context_v5(graph, frame)
    payload = _payload(graph)
    payload["why_consider"][0]["claim_refs"] = [next(
        c.claim_id for c in other.claims if c.claim_type == "technical_alignment")]
    with pytest.raises(ValueError):
        validate_narrative_v5(RecruiterNarrativeV5.model_validate(payload),
                              graph=graph, frame=frame, context=context)


def test_v5_generation_uses_provider_prose_without_copy_fallback():
    from app.services.explanation.generation.provider import ExplanationProviderResponse
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
    from app.services.explanation.presentation.service_v5 import generate_validated_narrative_v5
    from app.services.explanation.presentation.claim_handle_binding_v5 import build_claim_handle_binding_v5
    from test_claim_handle_binding_v5 import _provider_payload

    projection, graph, frame = _inputs()
    context = build_hiring_context_v5(graph, frame)
    binding = build_claim_handle_binding_v5(graph, frame, context)

    class Provider:
        async def generate(self, request):
            return ExplanationProviderResponse(content=json.dumps(_provider_payload(graph, binding), ensure_ascii=False),
                                               observed_model=None)

    result = asyncio.run(generate_validated_narrative_v5(
        Provider(), context=context, graph=graph, frame=frame,
        role_title=projection.role_title, max_output_tokens=2048))
    assert result.repair_count == 0
    assert result.narrative.candidate_id == graph.candidate_id


@pytest.mark.parametrize("field", ["uncertainty", "interview_focus"])
def test_v5_guard_diagnostic_attributes_only_the_actual_section(field):
    from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
    from app.services.explanation.presentation.service_v5 import diagnose_narrative_v5

    _, graph, frame = _inputs()
    context = build_hiring_context_v5(graph, frame)
    payload = _payload(graph)
    alignment = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    payload[field][0]["claim_refs"] = [alignment.claim_id]
    failures = diagnose_narrative_v5(
        RecruiterNarrativeV5.model_validate(payload), graph=graph, frame=frame, context=context)
    assert f"{field}[0].frame" in failures
    assert "why_consider[0].frame" not in failures
    assert "technical_signal[0].frame" not in failures


def test_v5_semantic_diagnostics_include_text_provenance_and_precise_section():
    from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
    from app.services.explanation.presentation.semantic_diagnostics_v5 import collect_v5_semantic_diagnostics

    _, graph, frame = _inputs()
    context = build_hiring_context_v5(graph, frame)
    payload = _payload(graph)
    alignment = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    payload["uncertainty"][0]["claim_refs"] = [alignment.claim_id]
    records = collect_v5_semantic_diagnostics(
        RecruiterNarrativeV5.model_validate(payload), run_id="synthetic-run-1",
        graph=graph, frame=frame, context=context)
    by_field = {record.field: record for record in records}
    assert by_field["uncertainty[0]"].generated_text == payload["uncertainty"][0]["text"]
    assert by_field["uncertainty[0]"].claim_types == ("technical_alignment",)
    assert by_field["uncertainty[0]"].source_fact_types
    assert by_field["uncertainty[0]"].guard_reason_code == "CLAIM_TYPE_MISMATCH"
    assert by_field["uncertainty[0]"].guard_actual_section == "uncertainty[0]"
    assert by_field["why_consider[0]"].guard_pass is True
    assert by_field["technical_signal[0]"].guard_pass is True
    assert all(record.classification_pending for record in records)


def test_v5_known_foreign_claim_diagnostic_reports_owner_without_accepting_it():
    from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
    from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
    from app.services.explanation.presentation.semantic_diagnostics_v5 import collect_v5_semantic_diagnostics
    from app.services.explanation.presentation.service_v5 import diagnose_narrative_v5

    _, graph, frame = _inputs()
    _, foreign, _ = _inputs(candidate_id="candidate-b", rank=2)
    foreign_id = next(c.claim_id for c in foreign.claims if c.claim_type == "technical_alignment")
    context = build_hiring_context_v5(graph, frame)
    payload = _payload(graph)
    payload["why_consider"][0]["claim_refs"] = [foreign_id]
    narrative = RecruiterNarrativeV5.model_validate(payload)
    assert diagnose_narrative_v5(narrative, graph=graph, frame=frame, context=context)
    records = collect_v5_semantic_diagnostics(
        narrative, run_id="synthetic-run-2", graph=graph, frame=frame, context=context,
        known_claim_owners={foreign_id: foreign.candidate_id})
    row = next(record for record in records if record.field == "why_consider[0]")
    assert row.validator_reason_code == "CLAIM_OWNER_MISMATCH"
    assert row.guard_reason_code == "CLAIM_OWNER_MISMATCH"
    assert row.decision_frame_type == "unresolved_claim_ref"
