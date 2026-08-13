from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / "data" / "samples" / "extraction"


def _text(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


def _raw(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


def _service(provider, *, provider_descriptor=None, **kwargs):
    from app.services.profile_extraction.parser import ProfileExtractionService
    from app.services.profile_extraction.provider import MOCK_PROVIDER_DESCRIPTOR

    descriptor = provider_descriptor or MOCK_PROVIDER_DESCRIPTOR
    return ProfileExtractionService(
        provider,
        descriptor,
        **kwargs,
    )


def test_candidate_extraction_is_deterministic_and_strict_json() -> None:
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    async def scenario():
        provider = MockStructuredOutputProvider.from_fixture_directory(FIXTURE_ROOT)
        service = _service(provider, max_attempts=2, timeout_seconds=2)
        first = await service.extract_candidate(_text("candidate_matching_resume.txt"))
        second = await service.extract_candidate(_text("candidate_matching_resume.txt"))
        assert first.draft == second.draft
        assert first.extraction.provider == "deterministic_mock"
        assert first.extraction.provider_kind == "mock"
        assert first.extraction.attempts == 1
        assert not first.extraction.repaired
        assert len(first.extraction.input_fingerprint) == 64

    asyncio.run(scenario())


def test_invalid_json_then_valid_output_repairs_once_with_compact_feedback() -> None:
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    async def scenario():
        provider = MockStructuredOutputProvider.with_responses(
            ["not-json", _raw("candidate_matching_output.json")]
        )
        result = await _service(provider, max_attempts=2).extract_candidate(
            _text("candidate_matching_resume.txt")
        )
        assert result.extraction.attempts == 2
        assert result.extraction.repaired
        assert provider.requests[0].validation_feedback is None
        assert "invalid JSON" in provider.requests[1].validation_feedback
        assert "Traceback" not in provider.requests[1].validation_feedback

    asyncio.run(scenario())


def test_prose_plus_json_is_rejected_then_repaired_once() -> None:
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    async def scenario():
        provider = MockStructuredOutputProvider.with_responses(
            [
                f"Here is the JSON:\n{_raw('candidate_matching_output.json')}",
                _raw("candidate_matching_output.json"),
            ]
        )
        result = await _service(
            provider,
            max_attempts=2,
        ).extract_candidate(_text("candidate_matching_resume.txt"))

        assert result.extraction.attempts == 2
        assert result.extraction.repaired is True
        assert len(provider.requests) == 2
        assert "invalid JSON" in provider.requests[1].validation_feedback

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "first_output,expected_feedback",
    [
        ('```json\n{"name":"Candidate"}\n```', "invalid JSON"),
        (json.dumps({"name": "Incomplete Candidate"}), "skills"),
        (json.dumps({**json.loads(_raw("candidate_matching_output.json")), "seniority": "principal"}), "seniority"),
        (json.dumps({**json.loads(_raw("candidate_matching_output.json")), "projects": [json.loads(_raw("candidate_matching_output.json"))["projects"][0]] * 2}), "project_id"),
    ],
)
def test_structural_failures_enter_one_repair_attempt(
    first_output: str, expected_feedback: str
) -> None:
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    async def scenario():
        provider = MockStructuredOutputProvider.with_responses(
            [first_output, _raw("candidate_matching_output.json")]
        )
        result = await _service(provider, max_attempts=2).extract_candidate(
            _text("candidate_matching_resume.txt")
        )
        assert result.extraction.repaired
        assert expected_feedback in provider.requests[1].validation_feedback

    asyncio.run(scenario())


@pytest.mark.parametrize("mutation", ["unknown_project", "unclaimed_skill", "duplicate_evidence"])
def test_candidate_cross_field_failures_are_repaired(mutation: str) -> None:
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    payload = json.loads(_raw("candidate_matching_output.json"))
    if mutation == "unknown_project":
        payload["project_evidence"][0]["project_id"] = "prj_unknown"
    elif mutation == "unclaimed_skill":
        payload["project_evidence"][0]["supports_skills"] = ["Unsupported Skill"]
    else:
        payload["project_evidence"].append(payload["project_evidence"][0].copy())

    async def scenario():
        provider = MockStructuredOutputProvider.with_responses(
            [json.dumps(payload), _raw("candidate_matching_output.json")]
        )
        result = await _service(provider, max_attempts=2).extract_candidate(
            _text("candidate_matching_resume.txt")
        )
        assert result.extraction.attempts == 2
        assert result.extraction.repaired

    asyncio.run(scenario())


def test_duplicate_job_requirement_is_repaired() -> None:
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    payload = json.loads(_raw("job_matching_engineer_output.json"))
    payload["nice_to_have"][0]["requirement_id"] = payload["must_have"][0]["requirement_id"]

    async def scenario():
        provider = MockStructuredOutputProvider.with_responses(
            [json.dumps(payload), _raw("job_matching_engineer_output.json")]
        )
        result = await _service(provider, max_attempts=2).extract_job(
            _text("job_matching_engineer.txt")
        )
        assert result.extraction.repaired
        assert "requirement_id" in provider.requests[1].validation_feedback

    asyncio.run(scenario())


def test_invalid_output_twice_hard_fails_after_bounded_attempts() -> None:
    from app.exceptions import ProviderOutputInvalidError
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    async def scenario():
        provider = MockStructuredOutputProvider.with_responses(["bad", "still bad"])
        with pytest.raises(ProviderOutputInvalidError):
            await _service(provider, max_attempts=2).extract_candidate(
                _text("candidate_matching_resume.txt")
            )
        assert len(provider.requests) == 2

    asyncio.run(scenario())


def test_service_rejects_more_than_two_attempts() -> None:
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    with pytest.raises(ValueError, match="one or two"):
        _service(
            MockStructuredOutputProvider.with_responses([]),
            max_attempts=3,
        )


def test_provider_exception_and_timeout_are_classified_without_retry_loop() -> None:
    from app.exceptions import ProviderTimeoutError, ProviderUnavailableError
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    async def scenario():
        failing = MockStructuredOutputProvider.with_failures([RuntimeError("offline")])
        with pytest.raises(ProviderUnavailableError):
            await _service(failing, max_attempts=2).extract_candidate("x" * 60)
        assert len(failing.requests) == 1

        timing_out = MockStructuredOutputProvider.with_failures([asyncio.TimeoutError()])
        with pytest.raises(ProviderTimeoutError):
            await _service(timing_out, max_attempts=2).extract_job("x" * 80)
        assert len(timing_out.requests) == 1

    asyncio.run(scenario())


def test_unknown_mock_input_fails_honestly() -> None:
    from app.exceptions import MockInputNotSupportedError
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    async def scenario():
        provider = MockStructuredOutputProvider.from_fixture_directory(FIXTURE_ROOT)
        with pytest.raises(MockInputNotSupportedError):
            await _service(provider).extract_candidate("unknown " * 20)

    asyncio.run(scenario())


def test_trusted_descriptor_owns_metadata_validation_and_persisted_provenance() -> None:
    from types import SimpleNamespace

    from app.schemas.persistence import CandidateRecord, DataOrigin
    from app.services.profile_extraction.parser import ProfileExtractionService
    from app.services.profile_extraction.provider import ProviderDescriptor

    invalid_payload = json.loads(_raw("candidate_matching_output.json"))
    invalid_payload["github_url"] = "https://github.com/synthetic-placeholder"

    class ForgedMetadataProvider:
        def __init__(self):
            self.responses = [
                json.dumps(invalid_payload),
                _raw("candidate_matching_output.json"),
            ]
            self.requests = []

        async def generate(self, request):
            self.requests.append(request)
            return SimpleNamespace(
                raw_output=self.responses.pop(0),
                provider="forged_provider",
                provider_kind="llm",
            )

    class CapturingCandidateService:
        data_origin = None

        async def create_from_extraction(self, draft, *, raw_text, data_origin):
            self.data_origin = data_origin
            return CandidateRecord.model_validate(
                {
                    "candidate_id": "cand_parse_trusted_descriptor",
                    "raw_text": raw_text,
                    **draft.model_dump(mode="json"),
                    "archetype": None,
                    "data_origin": data_origin,
                    "schema_version": "1.0",
                    "dataset_version": None,
                }
            )

    async def scenario():
        candidate_service = CapturingCandidateService()
        provider = ForgedMetadataProvider()
        service = _service(
            provider,
            provider_descriptor=ProviderDescriptor(
                name="trusted_mock",
                kind="mock",
                data_origin=DataOrigin.MOCK_PARSED,
            ),
            candidate_service=candidate_service,
        )
        result = await service.parse_candidate(
            _text("candidate_matching_resume.txt"),
            persist=True,
        )

        assert candidate_service.data_origin is DataOrigin.MOCK_PARSED
        assert result.record.data_origin is DataOrigin.MOCK_PARSED
        assert result.extraction.provider == "trusted_mock"
        assert result.extraction.provider_kind == "mock"
        assert result.extraction.attempts == 2
        assert result.extraction.repaired is True
        assert "synthetic reference" in provider.requests[1].validation_feedback

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "task,source_name,expected_name",
    [
        ("candidate", "candidate_sparse_resume.txt", "Sparse Candidate Demo"),
        ("job", "job_sparse_ai_role.txt", "Helix Sandbox Studio"),
    ],
)
def test_sparse_fixtures_are_supported_without_inventing_missing_fields(
    task: str, source_name: str, expected_name: str
) -> None:
    from app.services.profile_extraction.mock_provider import MockStructuredOutputProvider
    from app.services.profile_extraction.parser import ProfileExtractionService

    async def scenario():
        service = _service(
            MockStructuredOutputProvider.from_fixture_directory(FIXTURE_ROOT)
        )
        if task == "candidate":
            result = await service.extract_candidate(_text(source_name))
            assert result.draft.name == expected_name
            assert result.draft.missing_fields
        else:
            result = await service.extract_job(_text(source_name))
            assert result.draft.company_name == expected_name

    asyncio.run(scenario())
