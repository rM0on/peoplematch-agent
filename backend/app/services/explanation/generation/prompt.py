from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from app.services.explanation.generation.contracts import ProviderPromptEvidenceV1
from app.services.explanation.generation.provider import ExplanationProviderRequest
from app.services.match_runs.contracts import canonical_fingerprint


PROMPT_VERSION = "explanation_prompt_v2"
EVIDENCE_CONTRACT_VERSION = "provider_prompt_evidence_v1"
OUTPUT_CONTRACT_VERSION = "explanation_plan_v1"
RepairCategory = Literal[
    "malformed_response",
    "schema_invalid",
    "grounding_invalid",
]
_REPAIR_CATEGORIES = {
    "malformed_response",
    "schema_invalid",
    "grounding_invalid",
}
_REPAIR_GUIDANCE = {
    "malformed_response": (
        "response_was_not_a_single_json_object",
        (
            "return_exactly_one_json_object",
            "conform_to_the_supplied_output_contract",
            "preserve_candidate_coverage_order_and_ranks",
            "do_not_add_candidate_facts",
        ),
    ),
    "schema_invalid": (
        "response_did_not_match_closed_output_contract",
        (
            "conform_to_the_supplied_output_contract",
            "preserve_candidate_coverage_order_and_ranks",
            "do_not_add_candidate_facts",
        ),
    ),
    "grounding_invalid": (
        "selection_not_grounded_in_supplied_evidence",
        (
            "use_only_exact_supplied_evidence_tuples",
            "empty_missing_requirements_require_empty_interview_operations",
            "rewrite_operations_require_exact_supported_evidence",
            "unknown_evidence_references_are_forbidden",
            "summary_refs_must_be_selected_reason_or_risk_refs",
            "preserve_candidate_coverage_order_and_ranks",
            "do_not_add_candidate_facts",
        ),
    ),
}


@dataclass(frozen=True)
class ExplanationPromptArtifact:
    prompt_version: str
    evidence_contract_version: str
    evidence_contract_fingerprint: str
    output_contract_version: str
    output_contract_fingerprint: str
    system_instruction: str
    prompt_fingerprint: str


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _prompt_path(version: str) -> Path:
    return Path(__file__).resolve().parent / "prompts" / f"{version}.txt"


def _contract_path() -> Path:
    return _repository_root() / "data" / "contracts" / "explanation_plan_v1.json"


def _load_output_contract() -> dict:
    try:
        contract = json.loads(_contract_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("explanation_plan_v1 contract artifact is unavailable") from error
    if not isinstance(contract, dict):
        raise RuntimeError("explanation_plan_v1 contract artifact must be an object")
    if contract.get("x-contract-version") != OUTPUT_CONTRACT_VERSION:
        raise RuntimeError("explanation_plan_v1 contract artifact version mismatch")
    if contract.get("additionalProperties") is not False:
        raise RuntimeError("explanation_plan_v1 contract artifact must be closed")
    return contract


def _load_explanation_prompt(version: str) -> ExplanationPromptArtifact:
    try:
        system_instruction = _prompt_path(version).read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError(f"{version} artifact is unavailable") from error
    if not system_instruction:
        raise RuntimeError(f"{version} artifact is empty")
    evidence_contract_fingerprint = canonical_fingerprint(
        ProviderPromptEvidenceV1.model_json_schema()
    )
    output_contract_fingerprint = canonical_fingerprint(_load_output_contract())
    fingerprint = canonical_fingerprint(
        {
            "prompt_version": version,
            "evidence_contract_version": EVIDENCE_CONTRACT_VERSION,
            "evidence_contract_fingerprint": evidence_contract_fingerprint,
            "output_contract_version": OUTPUT_CONTRACT_VERSION,
            "output_contract_fingerprint": output_contract_fingerprint,
            "system_instruction": system_instruction,
        }
    )
    return ExplanationPromptArtifact(
        prompt_version=version,
        evidence_contract_version=EVIDENCE_CONTRACT_VERSION,
        evidence_contract_fingerprint=evidence_contract_fingerprint,
        output_contract_version=OUTPUT_CONTRACT_VERSION,
        output_contract_fingerprint=output_contract_fingerprint,
        system_instruction=system_instruction,
        prompt_fingerprint=fingerprint,
    )


def load_explanation_prompt_v1() -> ExplanationPromptArtifact:
    return _load_explanation_prompt("explanation_prompt_v1")


def load_explanation_prompt_v2() -> ExplanationPromptArtifact:
    return _load_explanation_prompt(PROMPT_VERSION)


def build_explanation_provider_request(
    evidence: ProviderPromptEvidenceV1,
    *,
    max_output_tokens: int,
    max_prompt_bytes: int = 131072,
    repair_category: str | None = None,
    prior_provider_output: str | None = None,
) -> ExplanationProviderRequest:
    """Build the only provider request shape allowed by Phase 9.3.

    ``prior_provider_output`` is accepted only so orchestration can make the
    non-echo policy explicit. It is deliberately discarded and never enters a
    repair prompt, fingerprint, log, or persistence record.
    """

    del prior_provider_output
    if type(max_output_tokens) is not int or not 64 <= max_output_tokens <= 4096:
        raise ValueError("max output tokens must be a bounded integer")
    if type(max_prompt_bytes) is not int or not 1024 <= max_prompt_bytes <= 1048576:
        raise ValueError("max prompt bytes must be a bounded integer")
    if repair_category is not None and repair_category not in _REPAIR_CATEGORIES:
        raise ValueError("repair category is not supported")
    artifact = load_explanation_prompt_v2()
    payload: dict[str, object] = {
        "evidence": evidence.model_dump(mode="json", exclude_none=False),
        "output_contract": _load_output_contract(),
    }
    if repair_category is not None:
        validation_error_summary, constraints = _REPAIR_GUIDANCE[repair_category]
        payload["repair"] = {
            "attempt": 2,
            "category": repair_category,
            "validation_error_summary": validation_error_summary,
            "constraints": list(constraints),
        }
    user_instruction = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if len(user_instruction.encode("utf-8")) > max_prompt_bytes:
        raise ValueError("provider prompt size exceeds the configured byte limit")
    return ExplanationProviderRequest(
        system_instruction=artifact.system_instruction,
        user_instruction=user_instruction,
        output_contract_version=artifact.output_contract_version,
        max_output_tokens=max_output_tokens,
    )


__all__ = [
    "ExplanationPromptArtifact",
    "PROMPT_VERSION",
    "build_explanation_provider_request",
    "load_explanation_prompt_v1",
    "load_explanation_prompt_v2",
]
