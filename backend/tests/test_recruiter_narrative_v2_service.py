from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from test_recruiter_narrative_service import _service
from test_recruiter_narrative_v2 import _case


def test_v2_service_persists_independent_artifact_without_mutating_source():
    from app.services.explanation.presentation.service_v2 import RecruiterNarrativeV2Service

    _, _, _, _, payload = _case()
    _, repository, transport, source = _service(payload)
    before = deepcopy(source.bundle.model_dump(mode="json"))
    service = RecruiterNarrativeV2Service(repository=repository, provider=transport, max_output_tokens=2048)

    record = asyncio.run(service.generate(42))

    assert record.status == "COMPLETED"
    assert record.prompt_version == "recruiter_narrative_prompt_v2"
    assert record.validated_content_json["contract_version"] == "recruiter_narrative_v2"
    assert record.ranking_fingerprint == source.bundle.source.result_fingerprint
    assert record.content_fingerprint is not None
    assert source.bundle.model_dump(mode="json") == before
    assert asyncio.run(service.get(record.narrative_id)).narrative_id == record.narrative_id


def test_v2_service_rejects_unsupported_claim_without_persisting_it():
    from app.services.explanation.presentation.service import NarrativeGenerationFailedError
    from app.services.explanation.presentation.service_v2 import RecruiterNarrativeV2Service

    _, _, _, _, payload = _case()
    payload["strengths"][0]["explanation"] = "候选人熟悉 Kubernetes 和 Python。"
    _, repository, transport, _ = _service(payload)
    service = RecruiterNarrativeV2Service(repository=repository, provider=transport, max_output_tokens=2048)

    with pytest.raises(NarrativeGenerationFailedError):
        asyncio.run(service.generate(42))
    assert repository.saved[0].error_code == "grounding_invalid"
    assert repository.saved[0].validated_content_json is None


def test_v2_service_repairs_claim_invalid_once_without_weakening_validation():
    from app.services.explanation.presentation.service_v2 import RecruiterNarrativeV2Service

    _, _, _, _, valid = _case()
    invalid = deepcopy(valid)
    invalid["why_review"]["text"] += " 还熟悉 Kubernetes。"
    _, repository, transport, source = _service(invalid)
    original_generate = transport.generate

    async def responses(request):
        if len(transport.requests) == 0:
            return await original_generate(request)
        transport.requests.append(request)
        from types import SimpleNamespace
        import json
        return SimpleNamespace(content=json.dumps(valid, ensure_ascii=False), observed_model="qwen3.7-plus")

    transport.generate = responses
    record = asyncio.run(RecruiterNarrativeV2Service(repository=repository, provider=transport).generate(42))
    assert len(transport.requests) == 2
    assert "validation_error_summary" in transport.requests[1].user_instruction
    assert '"unsupported_terms":["kubernetes"]' in transport.requests[1].user_instruction
    assert "Kubernetes" not in record.validated_content_json["why_review"]["text"]
    assert record.ranking_fingerprint == source.bundle.source.result_fingerprint


def test_v2_service_fails_closed_when_repair_is_still_invalid():
    from app.services.explanation.presentation.service import NarrativeGenerationFailedError
    from app.services.explanation.presentation.service_v2 import RecruiterNarrativeV2Service

    _, _, _, _, payload = _case()
    payload["why_review"]["text"] += " 还熟悉 Kubernetes。"
    _, repository, transport, _ = _service(payload)
    with pytest.raises(NarrativeGenerationFailedError):
        asyncio.run(RecruiterNarrativeV2Service(repository=repository, provider=transport).generate(42))
    assert len(transport.requests) == 2
    assert repository.saved[0].validated_content_json is None
