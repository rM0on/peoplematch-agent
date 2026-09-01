from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.explanation.generation.reference_projection import (
    ProviderReferenceProjector,
)
from app.services.explanation.evidence import build_evidence_facts
from test_explanation_generation_contracts import _bundle
from app.services.match_runs.contracts import canonical_fingerprint


def _prompt_module():
    from app.services.explanation.generation import prompt

    return prompt


def _projected_payload():
    bundle = _bundle()
    facts = build_evidence_facts(bundle)
    return ProviderReferenceProjector().project(
        bundle=bundle,
        evidence_facts=facts,
    ).payload


def test_prompt_artifact_is_versioned_closed_and_fingerprinted() -> None:
    prompt = _prompt_module()

    artifact = prompt.load_explanation_prompt_v1()

    assert artifact.prompt_version == "explanation_prompt_v1"
    assert artifact.evidence_contract_version == "provider_prompt_evidence_v1"
    assert artifact.output_contract_version == "explanation_plan_v1"
    assert len(artifact.evidence_contract_fingerprint) == 64
    assert len(artifact.output_contract_fingerprint) == 64
    assert len(artifact.prompt_fingerprint) == 64
    assert artifact.prompt_fingerprint == prompt.load_explanation_prompt_v1().prompt_fingerprint
    instruction = artifact.system_instruction.casefold()
    for required in (
        "untrusted data",
        "opaque reference",
        "do not modify ranking",
        "do not infer",
        "json object",
    ):
        assert required in instruction
    for forbidden_claim in (
        "hiring probability",
        "personality",
        "communication ability",
        "leadership",
        "culture fit",
        "salary",
        "employment verification",
        "business impact",
    ):
        assert forbidden_claim in instruction

    assert artifact.prompt_fingerprint == canonical_fingerprint(
        {
            "prompt_version": artifact.prompt_version,
            "evidence_contract_version": artifact.evidence_contract_version,
            "evidence_contract_fingerprint": artifact.evidence_contract_fingerprint,
            "output_contract_version": artifact.output_contract_version,
            "output_contract_fingerprint": artifact.output_contract_fingerprint,
            "system_instruction": artifact.system_instruction,
        }
    )


def test_prompt_request_contains_only_opaque_projection_and_closed_plan_schema() -> None:
    prompt = _prompt_module()

    request = prompt.build_explanation_provider_request(
        _projected_payload(),
        max_output_tokens=512,
    )
    user_payload = json.loads(request.user_instruction)
    serialized = json.dumps(user_payload, sort_keys=True)

    assert request.output_contract_version == "explanation_plan_v1"
    assert request.max_output_tokens == 512
    assert user_payload["evidence"]["contract_version"] == (
        "provider_prompt_evidence_v1"
    )
    assert user_payload["output_contract"]["x-contract-version"] == (
        "explanation_plan_v1"
    )
    assert user_payload["output_contract"]["additionalProperties"] is False
    assert "ref_0001" in serialized
    for forbidden in (
        "candidate:1:",
        "job_requirement:",
        "workflow_fingerprint",
        "ranking_input_fingerprint",
        "result_fingerprint",
        "runtime_provenance",
        "raw_resume",
        "raw_jd",
        "candidate_001",
        "request_id",
        "api_key",
    ):
        assert forbidden not in serialized


def test_repair_request_is_bounded_and_does_not_echo_raw_provider_output() -> None:
    prompt = _prompt_module()
    raw_provider_output = "RAW PRIVATE PROVIDER OUTPUT\nBearer secret"

    request = prompt.build_explanation_provider_request(
        _projected_payload(),
        max_output_tokens=256,
        repair_category="schema_invalid",
        prior_provider_output=raw_provider_output,
    )

    assert request.max_output_tokens == 256
    assert raw_provider_output not in request.system_instruction
    assert raw_provider_output not in request.user_instruction
    payload = json.loads(request.user_instruction)
    assert payload["repair"] == {"category": "schema_invalid", "attempt": 2}


def test_prompt_request_rejects_oversized_provider_input_before_transport() -> None:
    prompt = _prompt_module()

    with pytest.raises(ValueError, match="size|bytes|large"):
        prompt.build_explanation_provider_request(
            _projected_payload(),
            max_output_tokens=256,
            max_prompt_bytes=1024,
        )


@pytest.mark.parametrize(
    "category",
    ["totally_arbitrary", "raw_resume_private", "provider_error_body"],
)
def test_repair_category_is_closed(category: str) -> None:
    prompt = _prompt_module()

    with pytest.raises(ValueError, match="repair category"):
        prompt.build_explanation_provider_request(
            _projected_payload(),
            max_output_tokens=256,
            repair_category=category,
        )


def test_explanation_plan_artifact_matches_runtime_schema_exactly() -> None:
    from app.services.explanation.generation.contracts import ExplanationPlanV1

    root = Path(__file__).resolve().parents[2]
    artifact_path = root / "data" / "contracts" / "explanation_plan_v1.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert artifact["x-contract-version"] == "explanation_plan_v1"
    assert artifact["additionalProperties"] is False
    runtime = ExplanationPlanV1.model_json_schema()
    runtime["x-contract-version"] = "explanation_plan_v1"
    assert artifact == runtime


def test_provider_prompt_evidence_artifact_matches_runtime_schema_exactly() -> None:
    from app.services.explanation.generation.contracts import ProviderPromptEvidenceV1

    root = Path(__file__).resolve().parents[2]
    artifact_path = root / "data" / "contracts" / "provider_prompt_evidence_v1.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert artifact["x-contract-version"] == "provider_prompt_evidence_v1"
    runtime = ProviderPromptEvidenceV1.model_json_schema()
    runtime["x-contract-version"] = "provider_prompt_evidence_v1"
    assert artifact == runtime
    object_schemas = [artifact, *artifact.get("$defs", {}).values()]
    for schema in object_schemas:
        if schema.get("type") == "object":
            assert schema.get("additionalProperties") is False


def test_backend_image_copies_explanation_contract_to_runtime_repository_root() -> None:
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY data/contracts /data/contracts" in dockerfile
