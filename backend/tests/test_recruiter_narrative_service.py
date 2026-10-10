from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from app.services.explanation.contracts import candidate_output_fingerprint, evidence_bundle_fingerprint
from test_recruiter_narrative_presentation import _narrative, _source


class _Repository:
    def __init__(self, source):
        self.source = source
        self.saved = []

    async def load_source(self, match_explanation_id):
        return self.source if match_explanation_id == 42 else None

    async def save(self, record):
        self.saved.append(record)

    async def get(self, narrative_id):
        return next((item for item in self.saved if item.narrative_id == narrative_id), None)


class _Transport:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []
        self.descriptor = SimpleNamespace(
            kind="openai_compatible", name="openai_compatible", configured_model="qwen3.7-plus",
            configuration_fingerprint="a" * 64,
        )

    async def generate(self, request):
        self.requests.append(request)
        return SimpleNamespace(content=json.dumps(self.payload, ensure_ascii=False), observed_model="qwen3.7-plus")


def _service(payload=None):
    from app.repositories.recruiter_narrative_repository import NarrativeSource
    from app.services.explanation.presentation.service import RecruiterNarrativeService

    bundle, output, skill, project, requirement = _source()
    source = NarrativeSource(
        explanation_run_id="source-run-001",
        match_explanation_id=42,
        bundle=bundle,
        output=output,
        candidate_output_fingerprint=candidate_output_fingerprint(output),
        evidence_bundle_fingerprint=evidence_bundle_fingerprint(bundle),
    )
    repository = _Repository(source)
    transport = _Transport(payload or _narrative(skill, project, requirement))
    return RecruiterNarrativeService(repository=repository, provider=transport, max_output_tokens=1024), repository, transport, source


def test_generation_persists_independent_validated_artifact_without_mutating_ranking():
    service, repository, transport, source = _service()
    before = deepcopy(source.bundle.model_dump(mode="json"))

    result = asyncio.run(service.generate(42))

    assert result.status == "COMPLETED"
    assert result.validated_content_json is not None
    assert result.prompt_version == "recruiter_narrative_prompt_v1"
    assert result.provider_kind == "openai_compatible"
    assert result.source_explanation_id == 42
    assert result.ranking_fingerprint == source.bundle.source.result_fingerprint
    assert len(transport.requests) == 1
    assert repository.saved[0].content_fingerprint is not None
    assert source.bundle.model_dump(mode="json") == before


def test_hallucinated_provider_output_fails_closed_and_does_not_persist_prose():
    service, repository, transport, source = _service()
    transport.payload["strengths"][0]["text"] = "熟悉 Kubernetes 和 Python。"
    from app.services.explanation.presentation.service import NarrativeGenerationFailedError

    with pytest.raises(NarrativeGenerationFailedError):
        asyncio.run(service.generate(42))

    assert len(transport.requests) == 1
    assert repository.saved[0].status == "FAILED"
    assert repository.saved[0].validated_content_json is None
    assert repository.saved[0].error_code == "grounding_invalid"


def test_top_level_links_missing_an_existing_statement_reference_are_canonicalized():
    service, repository, transport, _ = _service()
    complete_links = list(transport.payload["evidence_links"])
    transport.payload["evidence_links"] = complete_links[:-1]

    result = asyncio.run(service.generate(42))

    assert result.status == "COMPLETED"
    assert result.validated_content_json["evidence_links"] == complete_links
    assert repository.saved[0].validation_status == "PASSED"


def test_extra_top_level_reference_not_used_by_a_statement_still_fails_closed():
    from app.services.explanation.presentation.service import NarrativeGenerationFailedError

    service, repository, transport, _ = _service()
    transport.payload["evidence_links"].append("candidate:1:skill:" + "b" * 64)

    with pytest.raises(NarrativeGenerationFailedError):
        asyncio.run(service.generate(42))

    assert repository.saved[0].error_code == "schema_invalid"
    assert repository.saved[0].validated_content_json is None


def test_missing_source_fails_before_provider_call():
    service, repository, transport, _ = _service()
    repository.source = None
    from app.services.explanation.presentation.service import NarrativeSourceNotFoundError

    with pytest.raises(NarrativeSourceNotFoundError):
        asyncio.run(service.generate(42))
    assert transport.requests == []


def test_default_mock_selection_never_silently_generates_narrative():
    from app.core.config import Settings
    from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
    from app.exceptions import ProviderUnavailableError

    with pytest.raises(ProviderUnavailableError):
        build_recruiter_narrative_provider(Settings(_env_file=None, explanation_provider="mock"))


def test_narrative_has_separate_bounded_output_budget():
    from app.core.config import Settings
    from pydantic import ValidationError

    settings = Settings(_env_file=None, explanation_max_output_tokens=64)
    assert settings.recruiter_narrative_max_output_tokens == 1024
    with pytest.raises(ValidationError):
        Settings(_env_file=None, recruiter_narrative_max_output_tokens=100)


def test_provider_credentials_are_not_exposed_by_settings_repr():
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        llm_api_key="synthetic-secret-do-not-log",
        explanation_deepseek_api_key="synthetic-legacy-secret-do-not-log",
    )
    rendered = repr(settings)
    assert "synthetic-secret-do-not-log" not in rendered
    assert "synthetic-legacy-secret-do-not-log" not in rendered
