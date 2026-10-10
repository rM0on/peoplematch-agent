"""Request-scoped Claim Handle protocol; opaque Claim IDs never go to Qwen."""

from __future__ import annotations

from copy import deepcopy
import json
import asyncio

import pytest

from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
from test_recruiter_narrative_v5 import _inputs, _payload


def _setup(candidate_id="candidate-a", rank=1):
    from app.services.explanation.presentation.claim_handle_binding_v5 import build_claim_handle_binding_v5

    projection, graph, frame = _inputs(candidate_id=candidate_id, rank=rank)
    context = build_hiring_context_v5(graph, frame)
    return projection, graph, frame, context, build_claim_handle_binding_v5(graph, frame, context)


def _provider_payload(graph, binding):
    original = _payload(graph)

    def paragraph(value):
        return {"text": value["text"],
                "claim_handles": [binding.handle_for(ref) for ref in value["claim_refs"]]}

    return {
        **{key: original[key] for key in ("contract_version", "candidate_id", "result_rank")},
        "decision_summary": paragraph(original["decision_summary"]),
        **{key: [paragraph(item) for item in original[key]] for key in
           ("why_consider", "technical_signal", "interview_focus", "uncertainty")},
    }


def test_binding_is_deterministic_and_isolated_per_candidate():
    from app.services.explanation.presentation.claim_handle_binding_v5 import build_claim_handle_binding_v5

    _, graph, frame, context, first = _setup()
    assert first == build_claim_handle_binding_v5(graph, frame, context)
    assert first.entries[0].handle == "C01"
    assert all(entry.candidate_id == graph.candidate_id for entry in first.entries)
    _, other_graph, _, _, other = _setup("candidate-b", 2)
    assert other.entries[0].handle == "C01"
    assert first.entries[0].claim_id != other.entries[0].claim_id
    assert other_graph.candidate_id != graph.candidate_id


@pytest.mark.parametrize("invalid", ["C99", "c01", "C1", "class:C01", "claim:C01"])
def test_resolver_fails_closed_on_unknown_or_malformed_handle(invalid):
    _, _, _, _, binding = _setup()
    with pytest.raises(ValueError):
        binding.resolve([invalid], field="decision_summary")


def test_resolver_checks_role_and_cross_candidate_identity():
    from app.services.explanation.presentation.provider_output_v5 import (
        RecruiterNarrativeV5ProviderOutput, resolve_provider_output_v5,
    )

    _, graph, _, _, binding = _setup()
    review = next(c for c in graph.claims if c.claim_type == "review_recommendation")
    technical = next(c for c in graph.claims if c.claim_type == "technical_alignment")
    with pytest.raises(ValueError):
        binding.resolve([binding.handle_for(technical.claim_id)], field="interview_focus")
    with pytest.raises(ValueError):
        binding.handle_for("claim:" + "0" * 32)
    payload = _provider_payload(graph, binding)
    payload["candidate_id"] = "candidate-b"
    with pytest.raises(ValueError):
        resolve_provider_output_v5(RecruiterNarrativeV5ProviderOutput.model_validate(payload), binding)
    assert binding.resolve([binding.handle_for(review.claim_id)], field="decision_summary") == [review.claim_id]


def test_resolver_preserves_text_claim_content_and_selected_order():
    from app.services.explanation.presentation.provider_output_v5 import (
        RecruiterNarrativeV5ProviderOutput, resolve_provider_output_v5,
    )

    _, graph, frame, context, binding = _setup()
    payload = _provider_payload(graph, binding)
    allowed = binding.allowed_handles("interview_focus")
    assert len(allowed) >= 2
    payload["interview_focus"][0]["claim_handles"] = list(reversed(allowed[:2]))
    before = (repr(graph), repr(frame), repr(context), deepcopy(payload))
    narrative = resolve_provider_output_v5(
        RecruiterNarrativeV5ProviderOutput.model_validate(payload), binding)
    assert narrative.interview_focus[0].claim_refs == [
        binding.resolve([handle], field="interview_focus")[0]
        for handle in reversed(allowed[:2])]
    assert narrative.interview_focus[0].text == payload["interview_focus"][0]["text"]
    assert before == (repr(graph), repr(frame), repr(context), payload)


def test_provider_schema_has_field_specific_handle_enums_and_rejects_wrong_handle():
    from app.services.explanation.presentation.provider_output_v5 import build_provider_response_schema_v5

    _, graph, _, _, binding = _setup()
    schema = build_provider_response_schema_v5(binding)
    payload = _provider_payload(graph, binding)
    summary_enum = schema["properties"]["decision_summary"]["properties"]["claim_handles"]["items"]["enum"]
    why_enum = schema["properties"]["why_consider"]["items"]["properties"]["claim_handles"]["items"]["enum"]
    interview_enum = schema["properties"]["interview_focus"]["items"]["properties"]["claim_handles"]["items"]["enum"]
    assert set(summary_enum) != set(why_enum)
    assert set(why_enum) != set(interview_enum)
    payload["interview_focus"][0]["claim_handles"] = [why_enum[0]]
    assert why_enum[0] not in interview_enum
    with pytest.raises(ValueError):
        binding.resolve(payload["interview_focus"][0]["claim_handles"], field="interview_focus")


def test_provider_request_contains_only_handles_not_opaque_ids():
    from app.services.explanation.presentation.prompt_v5 import build_narrative_v5_request

    projection, graph, frame, context, binding = _setup()
    request = build_narrative_v5_request(
        context, graph=graph, frame=frame, role_title=projection.role_title,
        max_output_tokens=2048, binding=binding)
    prompt = json.loads(request.user_instruction)
    assert "claim_catalog" in prompt
    assert all("claim_id" not in item for item in prompt["claim_catalog"])
    assert "claim:" not in request.user_instruction
    assert "fact:" not in request.user_instruction
    assert request.response_schema["properties"]["why_consider"]["type"] == "array"


def test_generation_rejects_invalid_handle_without_typo_repair_or_second_call():
    from app.services.explanation.generation.provider import ExplanationProviderResponse
    from app.services.explanation.presentation.service_v5 import (
        NarrativeV5GenerationError, generate_validated_narrative_v5,
    )

    projection, graph, frame, context, binding = _setup()
    payload = _provider_payload(graph, binding)
    payload["why_consider"][0]["claim_handles"] = ["class:C01"]

    class Provider:
        calls = 0

        async def generate(self, request):
            self.calls += 1
            return ExplanationProviderResponse(content=json.dumps(payload), observed_model=None)

    provider = Provider()
    with pytest.raises(NarrativeV5GenerationError) as raised:
        asyncio.run(generate_validated_narrative_v5(
            provider, context=context, graph=graph, frame=frame,
            role_title=projection.role_title))
    assert raised.value.reason == "handle_invalid"
    assert provider.calls == 1
