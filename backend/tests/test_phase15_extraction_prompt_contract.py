from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services.match_runs.contracts import canonical_fingerprint


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "samples" / "extraction"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_candidate_and_job_prompt_artifacts_are_distinct_versioned_and_hash_pinned() -> None:
    from app.services.profile_extraction.prompts import load_extraction_prompt_v1
    from app.services.profile_extraction.provider import ExtractionTask

    candidate = load_extraction_prompt_v1(ExtractionTask.CANDIDATE)
    job = load_extraction_prompt_v1(ExtractionTask.JOB)

    assert candidate.version == "candidate_extraction_prompt_v1"
    assert job.version == "job_extraction_prompt_v1"
    assert candidate.fingerprint != job.fingerprint
    assert re.fullmatch(r"[a-f0-9]{64}", candidate.fingerprint)
    assert re.fullmatch(r"[a-f0-9]{64}", job.fingerprint)
    assert candidate == load_extraction_prompt_v1(ExtractionTask.CANDIDATE)


@pytest.mark.parametrize("task", ["candidate", "job"])
def test_prompt_artifacts_preserve_the_extraction_security_boundary(task: str) -> None:
    from app.services.profile_extraction.prompts import load_extraction_prompt_v1
    from app.services.profile_extraction.provider import ExtractionTask

    instruction = load_extraction_prompt_v1(ExtractionTask(task)).system_instruction.casefold()

    for required in (
        "untrusted",
        "source-supported",
        "do not browse",
        "do not invent",
        "json only",
    ):
        assert required in instruction


def test_prompt_fingerprint_covers_system_instruction_and_output_contract() -> None:
    from app.services.profile_extraction.prompts import build_job_prompt

    prompt = build_job_prompt("Synthetic job source " * 10)

    assert prompt.prompt_fingerprint == canonical_fingerprint(
        {
            "prompt_version": prompt.prompt_version,
            "system_message": prompt.system_message,
            "output_contract": prompt.output_contract,
        }
    )


def test_extraction_metadata_requires_closed_prompt_provenance() -> None:
    from app.schemas.extraction import ExtractionMetadata

    common = {
        "provider": "deterministic_mock",
        "provider_kind": "mock",
        "attempts": 1,
        "repaired": False,
        "persisted": False,
        "input_fingerprint": "a" * 64,
    }

    with pytest.raises(ValidationError):
        ExtractionMetadata.model_validate(common)
    with pytest.raises(ValidationError):
        ExtractionMetadata.model_validate(
            {
                **common,
                "prompt_version": "runtime_prompt",
                "prompt_fingerprint": "b" * 64,
            }
        )


def test_parser_uses_server_prompt_provenance_not_provider_metadata() -> None:
    from app.schemas.persistence import DataOrigin
    from app.services.profile_extraction.parser import ProfileExtractionService
    from app.services.profile_extraction.provider import ProviderDescriptor

    class ForgingProvider:
        def __init__(self) -> None:
            self.requests = []

        async def generate(self, request):
            self.requests.append(request)
            return SimpleNamespace(
                raw_output=_text("job_matching_engineer_output.json"),
                prompt_version="forged_prompt",
                prompt_fingerprint="f" * 64,
            )

    async def scenario() -> None:
        provider = ForgingProvider()
        service = ProfileExtractionService(
            provider,
            ProviderDescriptor(
                name="trusted_provider",
                kind="openai_compatible",
                data_origin=DataOrigin.LLM_PARSED,
            ),
        )
        result = await service.extract_job(_text("job_matching_engineer.txt"))

        assert result.extraction.prompt_version == "job_extraction_prompt_v1"
        assert result.extraction.prompt_fingerprint == provider.requests[0].prompt_fingerprint
        assert result.extraction.prompt_fingerprint != "f" * 64
        assert provider.requests[0].prompt_version == "job_extraction_prompt_v1"

    asyncio.run(scenario())
