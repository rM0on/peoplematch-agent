"""Strict V5 schema and bounded, content-preserving structure repair."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from app.services.explanation.generation.provider import ExplanationProviderResponse
from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
from app.services.explanation.presentation.service_v5 import (
    NarrativeV5GenerationError, generate_validated_narrative_v5,
)
from app.services.explanation.presentation.schema_repair_v1 import (
    prepare_schema_repair_v1, build_schema_repair_v1_request,
    schema_repair_preserves_content_v1,
)
from app.services.explanation.generation.provider import ExplanationProviderRequest
from test_recruiter_narrative_v5 import _inputs, _payload


class SequenceProvider:
    def __init__(self, *payloads: dict) -> None:
        self.responses = list(payloads)
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        return ExplanationProviderResponse(
            content=json.dumps(self.responses.pop(0), ensure_ascii=False),
            observed_model=None,
        )


def _object_for_list(payload: dict) -> dict:
    malformed = deepcopy(payload)
    malformed["why_consider"] = malformed["why_consider"][0]
    malformed["technical_signal"] = malformed["technical_signal"][0]
    return malformed


def _generate(provider: SequenceProvider, graph, frame, projection, *, allow_schema_repair: bool = True):
    return asyncio.run(generate_validated_narrative_v5(
        provider, context=build_hiring_context_v5(graph, frame),
        graph=graph, frame=frame, role_title=projection.role_title,
        allow_schema_repair=allow_schema_repair,
    ))


def test_v5_contract_rejects_object_for_list_without_coercion() -> None:
    _, graph, _ = _inputs()
    valid = _payload(graph)
    RecruiterNarrativeV5.model_validate(valid)
    with pytest.raises(ValidationError) as raised:
        RecruiterNarrativeV5.model_validate(_object_for_list(valid))
    failures = {(tuple(item["loc"]), item["type"]) for item in raised.value.errors()}
    assert (("why_consider",), "list_type") in failures
    assert (("technical_signal",), "list_type") in failures


def test_v5_native_schema_path_fails_closed_without_schema_repair_by_default() -> None:
    projection, graph, frame = _inputs()
    provider = SequenceProvider(_object_for_list(_payload(graph)))
    with pytest.raises(NarrativeV5GenerationError) as raised:
        asyncio.run(generate_validated_narrative_v5(
            provider, context=build_hiring_context_v5(graph, frame),
            graph=graph, frame=frame, role_title=projection.role_title,
        ))
    assert raised.value.reason == "schema_invalid"
    assert len(provider.requests) == 1
    assert provider.requests[0].response_schema is not None


def test_v5_repairs_only_container_shape_without_changing_content() -> None:
    _, graph, _ = _inputs()
    valid = _payload(graph)
    malformed = _object_for_list(valid)
    with pytest.raises(ValidationError) as raised:
        RecruiterNarrativeV5.model_validate(malformed)
    original, errors = prepare_schema_repair_v1(json.dumps(malformed), raised.value)
    request = ExplanationProviderRequest("system", "user", "recruiter_narrative_v5", 2048)
    repair = build_schema_repair_v1_request(request, original_output=original, schema_errors=errors)
    repair_input = json.loads(repair.user_instruction)
    assert repair_input["original_output"] == _object_for_list(valid)
    assert repair_input["target_json_schema"]["properties"]["why_consider"]["type"] == "array"
    assert repair_input["schema_errors"] == [
        {"field": "why_consider", "type": "list_type"},
        {"field": "technical_signal", "type": "list_type"},
    ]
    assert schema_repair_preserves_content_v1(original, json.dumps(valid))


@pytest.mark.parametrize("change", ["text", "claim_refs"])
def test_v5_rejects_schema_repair_that_changes_semantics(change: str) -> None:
    _, graph, _ = _inputs()
    valid = _payload(graph)
    changed = deepcopy(valid)
    if change == "text":
        changed["why_consider"][0]["text"] = "候选人主导企业级系统建设。"
    else:
        changed["why_consider"][0]["claim_refs"] = ["invented-claim"]
    assert not schema_repair_preserves_content_v1(
        _object_for_list(valid), json.dumps(changed, ensure_ascii=False))


def test_v5_schema_repair_is_bounded_to_one_attempt() -> None:
    projection, graph, frame = _inputs()
    malformed = _object_for_list(_payload(graph))
    provider = SequenceProvider(malformed, malformed)

    with pytest.raises(NarrativeV5GenerationError) as raised:
        _generate(provider, graph, frame, projection)

    assert raised.value.reason == "schema_repair_unavailable_for_handle_protocol"
    assert len(provider.requests) == 0


def test_v5_schema_repair_does_not_launder_unsupported_claim() -> None:
    _, graph, frame = _inputs()
    unsafe = _payload(graph)
    unsafe["why_consider"][0]["text"] = "候选人负责企业级 RAG 平台建设。"
    assert schema_repair_preserves_content_v1(
        _object_for_list(unsafe), json.dumps(unsafe, ensure_ascii=False))
    from app.services.explanation.presentation.service_v5 import validate_narrative_v5
    with pytest.raises(NarrativeV5GenerationError) as raised:
        validate_narrative_v5(
            RecruiterNarrativeV5.model_validate(unsafe), graph=graph, frame=frame,
            context=build_hiring_context_v5(graph, frame))
    assert "why_consider[0]" in raised.value.diagnostics
