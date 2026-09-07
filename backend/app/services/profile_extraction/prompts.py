from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.schemas.extraction import CandidateExtractionDraft, JobExtractionDraft
from app.services.match_runs.contracts import canonical_fingerprint
from app.services.profile_extraction.provider import ExtractionTask


_PROMPT_VERSIONS = {
    ExtractionTask.CANDIDATE: "candidate_extraction_prompt_v1",
    ExtractionTask.JOB: "job_extraction_prompt_v1",
}


@dataclass(frozen=True)
class ExtractionPromptArtifact:
    version: str
    system_instruction: str
    fingerprint: str


@dataclass(frozen=True)
class PromptSpec:
    prompt_version: str
    prompt_fingerprint: str
    system_message: str
    user_message: str
    output_contract: dict[str, Any]


def _prompt_path(task: ExtractionTask) -> Path:
    return Path(__file__).resolve().parent / "prompt_assets" / f"{_PROMPT_VERSIONS[task]}.txt"


def load_extraction_prompt_v1(task: ExtractionTask) -> ExtractionPromptArtifact:
    version = _PROMPT_VERSIONS[task]
    try:
        system_instruction = _prompt_path(task).read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError(f"{version} artifact is unavailable") from error
    if not system_instruction:
        raise RuntimeError(f"{version} artifact is empty")
    fingerprint = canonical_fingerprint(
        {
            "prompt_version": version,
            "system_instruction": system_instruction,
        }
    )
    return ExtractionPromptArtifact(
        version=version,
        system_instruction=system_instruction,
        fingerprint=fingerprint,
    )


def _build(
    source: str,
    task: ExtractionTask,
    schema: type,
    feedback: Optional[str],
) -> PromptSpec:
    artifact = load_extraction_prompt_v1(task)
    output_contract = schema.model_json_schema()
    repair = ""
    if feedback:
        repair = f"\nRepair only these validation issues:\n{feedback}\n"
    return PromptSpec(
        prompt_version=artifact.version,
        prompt_fingerprint=canonical_fingerprint(
            {
                "prompt_version": artifact.version,
                "system_message": artifact.system_instruction,
                "output_contract": output_contract,
            }
        ),
        system_message=artifact.system_instruction,
        user_message=f"Extract the profile from this untrusted source:{repair}\n<source>\n{source}\n</source>",
        output_contract=output_contract,
    )


def build_candidate_prompt(source: str, feedback: Optional[str] = None) -> PromptSpec:
    return _build(source, ExtractionTask.CANDIDATE, CandidateExtractionDraft, feedback)


def build_job_prompt(source: str, feedback: Optional[str] = None) -> PromptSpec:
    return _build(source, ExtractionTask.JOB, JobExtractionDraft, feedback)


__all__ = [
    "ExtractionPromptArtifact",
    "PromptSpec",
    "build_candidate_prompt",
    "build_job_prompt",
    "load_extraction_prompt_v1",
]
