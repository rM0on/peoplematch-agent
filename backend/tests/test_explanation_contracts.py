from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.explanations import (
    CandidateExplanationOutput,
    EvidenceId,
    ExplanationRunRecord,
    ExplanationRunStatus,
    InternalEvidenceBundleV1,
    ProviderEvidenceV1,
    ExplanationOutputV1,
)
from app.services.explanation.contracts import (
    EVIDENCE_BUNDLE_VERSION,
    EXPLANATION_OUTPUT_VERSION,
    PROVIDER_EVIDENCE_VERSION,
    candidate_output_fingerprint,
    evidence_bundle_fingerprint,
    explanation_result_fingerprint,
    project_provider_evidence,
    provider_evidence_fingerprint,
)


ROOT = Path(__file__).resolve().parents[2]


def _job(*, provider: bool = False) -> dict:
    value = {
        "role_title": "AI Engineer",
        "role_direction": ["applied_ai"],
        "requirements": [
            {
                "evidence_id": "job_requirement:req_python",
                "requirement_id": "req_python",
                "priority": "must_have",
                "category": "skill",
                "text": "Strong Python engineering skills",
                "evidence_expectation": "A structured project evidence record",
            }
        ],
        "location": {
            "cities": ["Shanghai"],
            "remote_policy": "hybrid",
            "relocation_supported": True,
        },
        "seniority_requirement": ["senior"],
        "product_stage": "zero_to_one",
    }
    if not provider:
        value["job_id"] = "job_phase9_contract"
    return value


def _candidate() -> dict:
    return {
        "candidate_id": "cand_phase9_contract",
        "result_rank": 1,
        "target_roles": ["AI Engineer"],
        "skills": [
            {
                "evidence_id": "candidate:1:skill:0123456789abcdef0123456789abcdef",
                "name": "Python",
                "category": "backend",
            }
        ],
        "projects": [
            {
                "evidence_id": "candidate:1:project:project_001",
                "project_id": "project_001",
                "technologies": ["Python"],
                "skills_demonstrated": ["Python"],
            }
        ],
        "project_evidence": [
            {
                "evidence_id": "candidate:1:project_evidence:evidence_001",
                "source_evidence_id": "evidence_001",
                "project_id": "project_001",
                "supports_skills": ["Python"],
                "verification_status": "described",
                "evidence_type": "readme",
            }
        ],
        "ai_tools": ["structured outputs"],
        "preferred_locations": {
            "cities": ["Shanghai"],
            "remote_policy": "hybrid",
            "relocation_open": True,
        },
        "seniority": "senior",
        "team_stage_preference": ["zero_to_one"],
        "overclaim_risk": {"level": "low", "reason_count": 0},
        "facts": [
            {
                "evidence_id": "retrieval:1:retrieval_rank",
                "kind": "retrieval",
                "candidate_id": "cand_phase9_contract",
                "name": "retrieval_rank",
                "value": 1,
            },
            {
                "evidence_id": "retrieval:1:matched_channels",
                "kind": "retrieval",
                "candidate_id": "cand_phase9_contract",
                "name": "matched_channels",
                "value": ["dense", "sparse"],
            },
            {
                "evidence_id": "retrieval:1:dense_score",
                "kind": "retrieval",
                "candidate_id": "cand_phase9_contract",
                "name": "dense_score",
                "value": 0.4,
            },
            {
                "evidence_id": "retrieval:1:sparse_score",
                "kind": "retrieval",
                "candidate_id": "cand_phase9_contract",
                "name": "sparse_score",
                "value": 0.3,
            },
            {
                "evidence_id": "retrieval:1:fusion_score",
                "kind": "retrieval",
                "candidate_id": "cand_phase9_contract",
                "name": "fusion_score",
                "value": 0.2,
            },
            {
                "evidence_id": "ranking:1:result_rank",
                "kind": "ranking",
                "candidate_id": "cand_phase9_contract",
                "name": "result_rank",
                "value": 1,
            },
            {
                "evidence_id": "ranking:1:ltr_rank",
                "kind": "ranking",
                "candidate_id": "cand_phase9_contract",
                "name": "ltr_rank",
                "value": 1,
            },
            {
                "evidence_id": "ranking:1:ltr_score_raw",
                "kind": "ranking",
                "candidate_id": "cand_phase9_contract",
                "name": "ltr_score_raw",
                "value": 0.5,
            },
            {
                "evidence_id": "feature:1:skill_fit_score",
                "kind": "feature",
                "candidate_id": "cand_phase9_contract",
                "name": "skill_fit_score",
                "value": 0.8,
            },
            *[
                {
                    "evidence_id": f"feature:1:{name}",
                    "kind": "feature",
                    "candidate_id": "cand_phase9_contract",
                    "name": name,
                    "value": 0.1,
                }
                for name in (
                    "semantic_score", "sparse_score", "project_evidence_score",
                    "role_direction_score", "ai_tool_score", "location_score",
                    "seniority_score", "missing_penalty", "overclaim_penalty",
                )
            ],
        ],
    }


def _internal_bundle() -> dict:
    return {
        "contract_version": EVIDENCE_BUNDLE_VERSION,
        "source": {
            "match_run_id": "00000000-0000-0000-0000-000000000901",
            "ranking_variant": "ltr",
            "workflow_version": "match_run_workflow_v1",
            "workflow_fingerprint": "1" * 64,
            "ranking_input_fingerprint": "2" * 64,
            "result_fingerprint": "3" * 64,
        },
        "job": _job(),
        "runtime_provenance": {
            "retrieval_document_version": "retrieval_doc_v4",
            "retrieval_configuration_fingerprint": "4" * 64,
            "feature_version": "feature_schema_v1",
            "feature_fingerprint": "5" * 64,
            "ranker_version": "ltr_ranker_v1",
            "ranker_model_sha256": "6" * 64,
            "cross_encoder": None,
        },
        "workflow_trace": [
            {"sequence": 1, "step_name": "resolve_inputs", "status": "COMPLETED"}
        ],
        "candidates": [_candidate()],
    }


def _provider_evidence() -> dict:
    internal = InternalEvidenceBundleV1.model_validate(_internal_bundle())
    return project_provider_evidence(internal).model_dump(mode="json", exclude_none=False)


def _candidate_output(rank: int = 1) -> dict:
    return {
        "output_schema_version": EXPLANATION_OUTPUT_VERSION,
        "candidate_id": f"cand_phase9_{rank}",
        "result_rank": rank,
        "summary": {
            "text": "The persisted evidence supports the recorded match.",
            "evidence_refs": ["job_requirement:req_python", "ranking:1:result_rank"],
        },
        "match_reasons": [
            {
                "category": "skill_alignment",
                "text": "The required skill is present in the structured Candidate evidence.",
                    "evidence_refs": [
                        "job_requirement:req_python",
                        f"candidate:{rank}:skill:0123456789abcdef0123456789abcdef",
                ],
            },
            {
                "category": "ranking_context",
                "text": "This is the persisted result rank.",
                "evidence_refs": [f"ranking:{rank}:result_rank"],
            },
        ],
        "risk_points": [],
        "missing_skills": [],
        "interview_questions": [],
        "why_not_top1": None,
        "profile_rewrite_suggestion": {
            "operations": [
                {
                    "operation": "link_skill_to_project",
                    "skill_evidence_id": f"candidate:{rank}:skill:0123456789abcdef0123456789abcdef",
                    "project_evidence_id": f"candidate:{rank}:project:project_001",
                    "evidence_refs": [
                        f"candidate:{rank}:skill:0123456789abcdef0123456789abcdef",
                        f"candidate:{rank}:project:project_001",
                    ],
                }
            ]
        },
    }


def _run_record(status: ExplanationRunStatus) -> dict:
    base = {
        "explanation_run_id": "00000000-0000-0000-0000-000000000902",
        "match_run_id": "00000000-0000-0000-0000-000000000901",
        "request_id": "request-phase9-contract",
        "status": status,
        "requested_top_k": 5,
        "effective_top_k": None,
        "explanation_count": 0,
        "attempt_count": 0,
        "repaired": False,
    }
    if status == ExplanationRunStatus.FAILED:
        base.update(
            completed_at="2026-08-19T12:00:00Z",
            error_code="evidence_contract_invalid",
            error_detail_safe="Evidence contract validation failed",
        )
    if status == ExplanationRunStatus.COMPLETED:
        base.update(
            effective_top_k=1,
            explanation_count=1,
            evidence_bundle_version=EVIDENCE_BUNDLE_VERSION,
            evidence_bundle_fingerprint="a" * 64,
            evidence_bundle_json=_internal_bundle(),
            provider_evidence_version=PROVIDER_EVIDENCE_VERSION,
            provider_evidence_fingerprint="b" * 64,
            provider_evidence_json=_provider_evidence(),
            output_schema_version=EXPLANATION_OUTPUT_VERSION,
            provider_kind="structured_output",
            provider_name="offline_contract_provider",
            configured_model="contract-model-v1",
            provider_configuration_fingerprint="c" * 64,
            prompt_version="explanation_prompt_v1",
            prompt_fingerprint="d" * 64,
            attempt_count=1,
            result_fingerprint="e" * 64,
            completed_at="2026-08-19T12:00:00Z",
        )
    return base


def test_contract_artifacts_are_strict_versioned_and_privacy_bounded() -> None:
    expected = {
        "evidence_bundle_v1.json": EVIDENCE_BUNDLE_VERSION,
        "provider_evidence_v1.json": PROVIDER_EVIDENCE_VERSION,
        "explanation_output_v1.json": EXPLANATION_OUTPUT_VERSION,
    }
    forbidden = {
        "raw_resume",
        "raw_jd",
        "candidate_name",
        "company_name",
        "github_url",
        "artifact_ref",
        "evidence_statement",
        "hard_negative_metadata",
        "evaluation_metadata",
        "api_key",
    }
    for filename, version in expected.items():
        artifact = json.loads((ROOT / "data" / "contracts" / filename).read_text())
        assert artifact["x-contract-version"] == version
        assert artifact["additionalProperties"] is False
        assert not (forbidden & set(json.dumps(artifact).lower().split('"')))


def test_contract_artifacts_match_runtime_pydantic_schemas() -> None:
    contracts = (
        (
            "evidence_bundle_v1.json",
            EVIDENCE_BUNDLE_VERSION,
            "urn:peoplematch:evidence_bundle_v1",
            "app.schemas.explanations.InternalEvidenceBundleV1",
            InternalEvidenceBundleV1,
        ),
        (
            "provider_evidence_v1.json",
            PROVIDER_EVIDENCE_VERSION,
            "urn:peoplematch:provider_evidence_v1",
            "app.schemas.explanations.ProviderEvidenceV1",
            ProviderEvidenceV1,
        ),
        (
            "explanation_output_v1.json",
            EXPLANATION_OUTPUT_VERSION,
            "urn:peoplematch:explanation_output_v1",
            "app.schemas.explanations.ExplanationOutputV1",
            ExplanationOutputV1,
        ),
    )
    for filename, version, identifier, runtime_model, model in contracts:
        expected = model.model_json_schema()
        expected.update(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": identifier,
                "x-contract-version": version,
                "x-runtime-model": runtime_model,
            }
        )
        actual = json.loads((ROOT / "data" / "contracts" / filename).read_text())
        assert actual == expected


@pytest.mark.parametrize(
    "value",
    [
        "job_requirement:req_python",
        "candidate:1:skill:0123456789abcdef0123456789abcdef",
        "candidate:2:project:project_001",
        "candidate:2:project_evidence:evidence_001",
        "feature:2:skill_fit_score",
        "comparison:2:top1:skill_fit_score",
    ],
)
def test_evidence_id_accepts_owner_aware_ascii_forms(value: str) -> None:
    assert TypeAdapter(EvidenceId).validate_python(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "candidate_skill:python",
        "candidate:0:skill:0123456789abcdef0123456789abcdef",
        "candidate:1:skill:short_hash",
        "candidate:1:project:contains space",
        "feature:1:技能",
        "comparison:1:other:skill_fit_score",
    ],
)
def test_evidence_id_rejects_ambiguous_or_unsafe_forms(value: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(EvidenceId).validate_python(value)


def test_internal_and_provider_contracts_forbid_unknown_or_internal_fields() -> None:
    internal = _internal_bundle()
    InternalEvidenceBundleV1.model_validate(internal)
    internal["request_id"] = "must-not-be-in-bundle"
    with pytest.raises(ValidationError):
        InternalEvidenceBundleV1.model_validate(internal)

    provider = _provider_evidence()
    ProviderEvidenceV1.model_validate(provider)
    provider["workflow_trace"] = []
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(provider)


def test_evidence_ids_must_be_unique_inside_each_contract() -> None:
    bundle = _provider_evidence()
    duplicate = deepcopy(bundle["job"]["requirements"][0])
    duplicate["requirement_id"] = "req_duplicate"
    bundle["job"]["requirements"].append(duplicate)
    with pytest.raises(ValidationError, match="evidence IDs must be unique"):
        ProviderEvidenceV1.model_validate(bundle)


def test_output_contract_forbids_extra_scores_and_arbitrary_rewrite_text() -> None:
    valid = _candidate_output()
    CandidateExplanationOutput.model_validate(valid)

    with_score = dict(valid, final_match_score=0.92)
    with pytest.raises(ValidationError):
        CandidateExplanationOutput.model_validate(with_score)

    with_rewrite = _candidate_output()
    with_rewrite["profile_rewrite_suggestion"]["operations"][0]["text"] = (
        "Invented project outcome"
    )
    with pytest.raises(ValidationError):
        CandidateExplanationOutput.model_validate(with_rewrite)


def test_material_prose_requires_evidence_references() -> None:
    output = _candidate_output()
    output["summary"]["evidence_refs"] = []
    with pytest.raises(ValidationError):
        CandidateExplanationOutput.model_validate(output)

    output = _candidate_output(rank=1)
    output["profile_rewrite_suggestion"]["operations"][0]["evidence_refs"] = [
        "ranking:1:result_rank",
    ]
    with pytest.raises(ValidationError):
        CandidateExplanationOutput.model_validate(output)


def test_running_and_failed_records_allow_partial_provenance() -> None:
    running = ExplanationRunRecord.model_validate(_run_record(ExplanationRunStatus.RUNNING))
    failed = ExplanationRunRecord.model_validate(_run_record(ExplanationRunStatus.FAILED))
    assert running.evidence_bundle_json is None
    assert failed.provider_name is None


def test_failed_lifecycle_supports_each_precompletion_provenance_stage() -> None:
    before_evidence = _run_record(ExplanationRunStatus.FAILED)
    after_internal_evidence = deepcopy(before_evidence)
    after_internal_evidence.update(
        evidence_bundle_version=EVIDENCE_BUNDLE_VERSION,
        evidence_bundle_fingerprint="a" * 64,
        evidence_bundle_json=_internal_bundle(),
    )
    after_provider_projection = deepcopy(after_internal_evidence)
    after_provider_projection.update(
        provider_evidence_version=PROVIDER_EVIDENCE_VERSION,
        provider_evidence_fingerprint="b" * 64,
        provider_evidence_json=_provider_evidence(),
    )

    for payload in (
        before_evidence,
        after_internal_evidence,
        after_provider_projection,
    ):
        assert (
            ExplanationRunRecord.model_validate(payload).status
            == ExplanationRunStatus.FAILED
        )


@pytest.mark.parametrize(
    "detail",
    [
        "Traceback (most recent call last): secret",
        "postgresql://user:password@localhost/private",
        "Authorization: Bearer private-token",
        r"C:\\Users\\developer\\private.py",
    ],
)
def test_safe_error_detail_rejects_debug_or_secret_material(detail: str) -> None:
    failed = _run_record(ExplanationRunStatus.FAILED)
    failed["error_detail_safe"] = detail
    with pytest.raises(ValidationError, match="safe error detail"):
        ExplanationRunRecord.model_validate(failed)


def test_completed_record_requires_complete_contract_and_provider_provenance() -> None:
    completed = ExplanationRunRecord.model_validate(
        _run_record(ExplanationRunStatus.COMPLETED)
    )
    assert completed.explanation_count == completed.effective_top_k == 1

    incomplete = _run_record(ExplanationRunStatus.COMPLETED)
    incomplete["provider_evidence_json"] = None
    with pytest.raises(ValidationError, match="provider evidence must be absent or complete"):
        ExplanationRunRecord.model_validate(incomplete)


@pytest.mark.parametrize("requested,effective", [(0, None), (11, None), (2, 3), (5, 0)])
def test_top_k_bounds_are_enforced(requested: int, effective: int | None) -> None:
    record = _run_record(ExplanationRunStatus.RUNNING)
    record["requested_top_k"] = requested
    record["effective_top_k"] = effective
    with pytest.raises(ValidationError):
        ExplanationRunRecord.model_validate(record)


def test_fingerprints_are_canonical_versioned_and_ordered_by_rank() -> None:
    internal = InternalEvidenceBundleV1.model_validate(_internal_bundle())
    provider = ProviderEvidenceV1.model_validate(_provider_evidence())
    first = CandidateExplanationOutput.model_validate(_candidate_output(1))
    second_payload = _candidate_output(2)
    second_payload["why_not_top1"] = {
        "category": "ranking_comparison",
        "text": "The Candidate is below the persisted top-ranked result.",
        "evidence_refs": ["comparison:2:top1:skill_fit_score"],
    }
    second = CandidateExplanationOutput.model_validate(second_payload)

    assert evidence_bundle_fingerprint(internal) == evidence_bundle_fingerprint(
        InternalEvidenceBundleV1.model_validate(_internal_bundle())
    )
    assert provider_evidence_fingerprint(provider) != evidence_bundle_fingerprint(internal)
    assert candidate_output_fingerprint(first) != candidate_output_fingerprint(second)
    assert explanation_result_fingerprint([second, first]) == explanation_result_fingerprint(
        [first, second]
    )


def test_fingerprints_reject_non_finite_numbers() -> None:
    bundle = _provider_evidence()
    bundle["candidates"][0]["features"]["skill_fit_score"]["value"] = float("nan")
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(bundle)


def test_evidence_fact_text_and_list_values_are_bounded() -> None:
    text_bundle = _provider_evidence()
    text_bundle["candidates"][0]["diagnostics"]["location_relation"] = {
        "evidence_id": "diagnostic:1:location_relation",
        "value": "x" * 501,
    }
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(text_bundle)

    list_bundle = _provider_evidence()
    list_bundle["candidates"][0]["diagnostics"]["matched_capabilities"] = {
        "evidence_id": "diagnostic:1:matched_capabilities",
        "value": ["value"] * 101,
    }
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(list_bundle)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("raw_resume", "Private resume text must never reach a provider"),
        ("arbitrary_private_payload", ["unbounded semantic escape hatch"]),
    ],
)
def test_provider_evidence_rejects_generic_fact_privacy_bypass(
    name: str, value: object
) -> None:
    provider = _provider_evidence()
    provider["candidates"][0]["diagnostics"][name] = {
        "evidence_id": "diagnostic:1:private_payload",
        "value": value,
    }
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(provider)


@pytest.mark.parametrize(
    ("scope", "field"),
    [
        ("root", "request_id"),
        ("root", "workflow_trace"),
        ("root", "internal_error"),
        ("root", "labels"),
        ("root", "split"),
        ("root", "evaluation_metadata"),
        ("job", "raw_jd"),
        ("job", "company_name"),
        ("candidate", "raw_resume"),
        ("candidate", "candidate_name"),
        ("candidate", "url"),
        ("candidate", "project_outcomes"),
    ],
)
def test_provider_contract_rejects_forbidden_privacy_fields(
    scope: str, field: str
) -> None:
    provider = _provider_evidence()
    target = provider
    if scope == "job":
        target = provider["job"]
    elif scope == "candidate":
        target = provider["candidates"][0]
    target[field] = "private payload"
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(provider)


def test_candidate_evidence_rejects_rank_and_candidate_owner_mismatch() -> None:
    wrong_rank = _internal_bundle()
    wrong_rank["candidates"][0]["facts"][0]["evidence_id"] = "retrieval:2:retrieval_rank"
    with pytest.raises(ValidationError, match="rank owner"):
        InternalEvidenceBundleV1.model_validate(wrong_rank)

    wrong_candidate = _internal_bundle()
    wrong_candidate["candidates"][0]["facts"][0]["candidate_id"] = (
        "cand_other"
    )
    with pytest.raises(ValidationError, match="Candidate owner"):
        InternalEvidenceBundleV1.model_validate(wrong_candidate)


def test_evidence_fact_rejects_namespace_kind_mismatch() -> None:
    bundle = _internal_bundle()
    bundle["candidates"][0]["facts"][0].update(
        evidence_id="feature:1:semantic_score",
        kind="ranking",
        name="result_rank",
    )
    with pytest.raises(ValidationError, match="namespace"):
        InternalEvidenceBundleV1.model_validate(bundle)


@pytest.mark.parametrize(
    ("variant", "cross_encoder"),
    [
        (
            "ltr",
            {
                "reranker_version": "cross_encoder_reranker_v1",
                "model_id": "cross-encoder/ms-marco-MiniLM-L6-v2",
                "model_revision": "233902d25c440f23af6f7d6e94d2946bac0bee0a",
                "snapshot_fingerprint": "7" * 64,
                "text_schema_version": "cross_encoder_text_v1",
                "text_contract_fingerprint": "8" * 64,
                "pair_order": "job_then_candidate",
                "score_type": "raw_logit",
                "score_direction": "higher_is_better",
                "calibration": False,
            },
        ),
        ("cross_encoder_experiment", None),
    ],
)
def test_ranking_variant_requires_consistent_cross_encoder_provenance(
    variant: str, cross_encoder: object
) -> None:
    bundle = _internal_bundle()
    bundle["source"]["ranking_variant"] = variant
    bundle["runtime_provenance"]["cross_encoder"] = cross_encoder
    with pytest.raises(ValidationError, match="Cross-Encoder"):
        InternalEvidenceBundleV1.model_validate(bundle)


def _candidate_at_rank(rank: int, candidate_id: str) -> dict:
    candidate = deepcopy(_candidate())
    candidate["candidate_id"] = candidate_id
    candidate["result_rank"] = rank
    for section in ("skills", "projects", "project_evidence"):
        for item in candidate[section]:
            item["evidence_id"] = item["evidence_id"].replace(
                "candidate:1:", f"candidate:{rank}:"
            )
    for fact in candidate["facts"]:
        fact["evidence_id"] = fact["evidence_id"].replace(":1:", f":{rank}:")
        fact["candidate_id"] = candidate_id
        if fact["name"] == "result_rank":
            fact["value"] = rank
        if fact["name"] in {"retrieval_rank", "ltr_rank"}:
            fact["value"] = rank
    if rank > 1:
        candidate["facts"].append(
            {
                "evidence_id": f"comparison:{rank}:top1:result_rank",
                "kind": "comparison",
                "candidate_id": candidate_id,
                "comparison_candidate_id": "cand_phase9_contract",
                "name": "result_rank",
                "value": 1,
            }
        )
    return candidate


@pytest.mark.parametrize("duplicate", ["candidate_id", "result_rank"])
def test_evidence_bundle_rejects_duplicate_candidate_identity_or_rank(
    duplicate: str,
) -> None:
    bundle = _internal_bundle()
    second = _candidate_at_rank(2, "cand_phase9_second")
    if duplicate == "candidate_id":
        second["candidate_id"] = bundle["candidates"][0]["candidate_id"]
        for fact in second["facts"]:
            fact["candidate_id"] = second["candidate_id"]
    else:
        second["result_rank"] = 1
    bundle["candidates"].append(second)
    with pytest.raises(ValidationError, match=duplicate):
        InternalEvidenceBundleV1.model_validate(bundle)


def test_evidence_bundle_rejects_noncanonical_candidate_order() -> None:
    bundle = _internal_bundle()
    bundle["candidates"] = [
        _candidate_at_rank(2, "cand_phase9_second"),
        bundle["candidates"][0],
    ]
    with pytest.raises(ValidationError, match="ascending result_rank"):
        InternalEvidenceBundleV1.model_validate(bundle)


def test_rewrite_operations_reject_wrong_evidence_namespace() -> None:
    output = _candidate_output()
    output["profile_rewrite_suggestion"] = {
        "operations": [
            {
                "operation": "surface_existing_skill",
                "skill_evidence_id": "job_requirement:req_python",
                "evidence_refs": ["job_requirement:req_python"],
            }
        ]
    }
    with pytest.raises(ValidationError):
        CandidateExplanationOutput.model_validate(output)


def test_provider_projection_is_exact_closed_and_full_field() -> None:
    bundle = _internal_bundle()
    bundle["candidates"].append(_candidate_at_rank(2, "cand_phase9_second"))
    internal = InternalEvidenceBundleV1.model_validate(bundle)

    projected = project_provider_evidence(internal)
    payload = projected.model_dump(mode="json", exclude_none=False)

    assert [item["result_rank"] for item in payload["candidates"]] == [1, 2]
    assert payload["candidates"][1]["features"]["skill_fit_score"]["value"] == 0.8
    assert "source" not in payload
    assert "runtime_provenance" not in payload
    assert "workflow_trace" not in payload
    assert "facts" not in payload["candidates"][0]

    for field, replacement in (("skills", []), ("project_evidence", [])):
        mutated = deepcopy(payload)
        mutated["candidates"][0][field] = replacement
        actual = ProviderEvidenceV1.model_validate(mutated)
        assert actual != projected

    mutated_requirement = deepcopy(payload)
    mutated_requirement["job"]["requirements"][0]["priority"] = "nice_to_have"
    assert ProviderEvidenceV1.model_validate(mutated_requirement) != projected


def test_provider_projection_uses_provider_score_for_top1_feature_comparison() -> None:
    bundle = _internal_bundle()
    second = _candidate_at_rank(2, "cand_phase9_second")
    second["facts"].append(
        {
            "evidence_id": "comparison:2:top1:skill_fit_score",
            "kind": "comparison",
            "candidate_id": "cand_phase9_second",
            "comparison_candidate_id": "cand_phase9_contract",
            "name": "skill_fit_score",
            "value": 0.1,
        }
    )
    bundle["candidates"].append(second)
    internal = InternalEvidenceBundleV1.model_validate(bundle)

    projected = project_provider_evidence(internal)
    comparison = projected.candidates[1].top1_comparison
    assert comparison is not None
    assert comparison.skill_fit_score is not None
    assert comparison.skill_fit_score.value == 0.1


def _cross_encoder_provenance() -> dict:
    return {
        "reranker_version": "cross_encoder_reranker_v1",
        "model_id": "cross-encoder/ms-marco-MiniLM-L6-v2",
        "model_revision": "233902d25c440f23af6f7d6e94d2946bac0bee0a",
        "snapshot_fingerprint": "7" * 64,
        "text_schema_version": "cross_encoder_text_v1",
        "text_contract_fingerprint": "8" * 64,
        "pair_order": "job_then_candidate",
        "score_type": "raw_logit",
        "score_direction": "higher_is_better",
        "calibration": False,
    }


def test_ltr_bundle_rejects_candidate_cross_encoder_facts() -> None:
    bundle = _internal_bundle()
    bundle["candidates"][0]["facts"].append(
        {
            "evidence_id": "ranking:1:cross_encoder_rank",
            "kind": "ranking",
            "candidate_id": "cand_phase9_contract",
            "name": "cross_encoder_rank",
            "value": 1,
        }
    )
    with pytest.raises(ValidationError, match="LTR evidence"):
        InternalEvidenceBundleV1.model_validate(bundle)


def test_cross_encoder_bundle_requires_candidate_ce_rank_and_score() -> None:
    bundle = _internal_bundle()
    bundle["source"]["ranking_variant"] = "cross_encoder_experiment"
    bundle["runtime_provenance"]["cross_encoder"] = _cross_encoder_provenance()
    with pytest.raises(ValidationError, match="Candidate ranking facts"):
        InternalEvidenceBundleV1.model_validate(bundle)

    bundle["candidates"][0]["facts"].extend(
        [
            {
                "evidence_id": "ranking:1:cross_encoder_rank",
                "kind": "ranking",
                "candidate_id": "cand_phase9_contract",
                "name": "cross_encoder_rank",
                "value": 1,
            },
            {
                "evidence_id": "ranking:1:cross_encoder_score_raw",
                "kind": "ranking",
                "candidate_id": "cand_phase9_contract",
                "name": "cross_encoder_score_raw",
                "value": 0.125,
            },
        ]
    )
    assert (
        InternalEvidenceBundleV1.model_validate(bundle).source.ranking_variant
        == "cross_encoder_experiment"
    )


@pytest.mark.parametrize("defect", ["candidate_id", "result_rank", "order"])
def test_provider_evidence_rejects_noncanonical_candidate_identity(defect: str) -> None:
    internal = _internal_bundle()
    internal["candidates"].append(_candidate_at_rank(2, "cand_phase9_second"))
    provider = project_provider_evidence(
        InternalEvidenceBundleV1.model_validate(internal)
    ).model_dump(mode="json", exclude_none=False)
    if defect == "candidate_id":
        provider["candidates"][1]["candidate_id"] = provider["candidates"][0][
            "candidate_id"
        ]
    elif defect == "result_rank":
        provider["candidates"][1]["result_rank"] = 1
    else:
        provider["candidates"].reverse()
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(provider)


def test_provider_candidate_rank_cannot_change_while_evidence_ids_stay_fixed() -> None:
    provider = _provider_evidence()
    provider["candidates"][0]["result_rank"] = 2
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(provider)


def test_rewrite_operation_rejects_another_candidate_rank() -> None:
    output = _candidate_output(rank=1)
    operation = output["profile_rewrite_suggestion"]["operations"][0]
    operation["skill_evidence_id"] = (
        "candidate:2:skill:0123456789abcdef0123456789abcdef"
    )
    with pytest.raises(ValidationError, match="Candidate rank"):
        CandidateExplanationOutput.model_validate(output)


def test_provider_legal_fact_names_reject_private_prose_values() -> None:
    for category, name, evidence_id, private_value in (
        (
            "diagnostics",
            "location_relation",
            "diagnostic:1:location_relation",
            "RAW RESUME: private employment...",
        ),
        (
            "retrieval",
            "dense_score",
            "retrieval:1:dense_score",
            "RAW JD: private company description",
        ),
    ):
        provider = _provider_evidence()
        provider["candidates"][0][category][name] = {
            "evidence_id": evidence_id,
            "value": private_value,
        }
        with pytest.raises(ValidationError):
            ProviderEvidenceV1.model_validate(provider)


@pytest.mark.parametrize(
    ("category", "name", "evidence_id", "value"),
    [
        ("retrieval", "dense_rank", "retrieval:1:dense_rank", "1"),
        ("retrieval", "dense_rank", "retrieval:1:dense_rank", True),
        ("features", "skill_fit_score", "feature:1:skill_fit_score", "0.8"),
        ("ranking", "result_rank", "ranking:1:result_rank", 1.5),
        ("ranking", "result_rank", "ranking:1:result_rank", True),
    ],
)
def test_provider_fact_values_use_strict_name_semantics(
    category: str, name: str, evidence_id: str, value: object
) -> None:
    provider = _provider_evidence()
    provider["candidates"][0][category][name] = {
        "evidence_id": evidence_id,
        "value": value,
    }
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(provider)


def test_job_requirement_and_top1_owner_are_strictly_bound() -> None:
    wrong_requirement = _internal_bundle()
    wrong_requirement["job"]["requirements"][0]["evidence_id"] = "retrieval:1:dense_rank"
    with pytest.raises(ValidationError):
        InternalEvidenceBundleV1.model_validate(wrong_requirement)

    wrong_top1 = _internal_bundle()
    second = _candidate_at_rank(2, "cand_phase9_second")
    next(fact for fact in second["facts"] if fact["kind"] == "comparison")[
        "comparison_candidate_id"
    ] = "cand_unknown"
    wrong_top1["candidates"].append(second)
    with pytest.raises(ValidationError):
        InternalEvidenceBundleV1.model_validate(wrong_top1)


def test_fact_result_rank_value_must_match_candidate_rank() -> None:
    bundle = _internal_bundle()
    next(
        fact for fact in bundle["candidates"][0]["facts"] if fact["name"] == "result_rank"
    )["value"] = 2
    with pytest.raises(ValidationError):
        InternalEvidenceBundleV1.model_validate(bundle)


def test_cross_encoder_rank_is_strict_integer() -> None:
    bundle = _internal_bundle()
    bundle["source"]["ranking_variant"] = "cross_encoder_experiment"
    bundle["runtime_provenance"]["cross_encoder"] = _cross_encoder_provenance()
    bundle["candidates"][0]["facts"].extend(
        [
            {
                "evidence_id": "ranking:1:cross_encoder_rank",
                "kind": "ranking",
                "candidate_id": "cand_phase9_contract",
                "name": "cross_encoder_rank",
                "value": 1.5,
            },
            {
                "evidence_id": "ranking:1:cross_encoder_score_raw",
                "kind": "ranking",
                "candidate_id": "cand_phase9_contract",
                "name": "cross_encoder_score_raw",
                "value": 0.1,
            },
        ]
    )
    with pytest.raises(ValidationError):
        InternalEvidenceBundleV1.model_validate(bundle)


def test_rewrite_support_refs_must_match_output_owner_and_namespace() -> None:
    output = _candidate_output(rank=1)
    output["profile_rewrite_suggestion"]["operations"][0]["evidence_refs"] = [
        "candidate:2:skill:0123456789abcdef0123456789abcdef",
        "candidate:2:project:project_001",
    ]
    with pytest.raises(ValidationError):
        CandidateExplanationOutput.model_validate(output)


def test_rewrite_support_refs_reject_incompatible_ranking_namespace() -> None:
    output = _candidate_output(rank=1)
    operation = output["profile_rewrite_suggestion"]["operations"][0]
    operation["evidence_refs"] = ["ranking:1:ltr_rank"]
    with pytest.raises(ValidationError, match="namespace"):
        CandidateExplanationOutput.model_validate(output)


@pytest.mark.parametrize("invalid_rank", [1.5, "1", True, False])
def test_explanation_output_result_rank_is_strict_integer(invalid_rank: object) -> None:
    output = _candidate_output(rank=1)
    output["result_rank"] = invalid_rank
    with pytest.raises(ValidationError):
        CandidateExplanationOutput.model_validate(output)


def test_provider_has_no_generic_name_value_fact_channel() -> None:
    schema = ProviderEvidenceV1.model_json_schema()
    provider_definitions = {
        name: value
        for name, value in schema["$defs"].items()
        if name.startswith("Provider")
    }
    assert all(
        not {"name", "value"} <= set(definition.get("properties", {}))
        for definition in provider_definitions.values()
    )


def test_provider_schema_does_not_reuse_internal_historical_models() -> None:
    schema_text = json.dumps(ProviderEvidenceV1.model_json_schema())
    assert "Historical" not in schema_text


def test_projection_excludes_existing_internal_only_groups() -> None:
    internal = InternalEvidenceBundleV1.model_validate(_internal_bundle())
    projected = project_provider_evidence(internal).model_dump(mode="json")
    assert "source" not in projected
    assert "runtime_provenance" not in projected
    assert "workflow_trace" not in projected
    assert "job_id" not in projected["job"]
    assert "facts" not in projected["candidates"][0]


def test_every_provider_numeric_evidence_value_is_strict() -> None:
    internal = _internal_bundle()
    internal["candidates"].append(_candidate_at_rank(2, "cand_phase9_second"))
    provider = project_provider_evidence(
        InternalEvidenceBundleV1.model_validate(internal)
    ).model_dump(mode="json", exclude_none=False)
    numeric_paths = []

    def visit(value, path=()):
        if isinstance(value, dict):
            for key, item in value.items():
                visit(item, (*path, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, (*path, index))
        elif type(value) in {int, float}:
            numeric_paths.append(path)

    def assign(root, path, replacement):
        target = root
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = replacement

    visit(provider)
    assert numeric_paths
    for path in numeric_paths:
        for invalid in ("1", [], {}, True):
            mutated = deepcopy(provider)
            assign(mutated, path, invalid)
            with pytest.raises(ValidationError):
                ProviderEvidenceV1.model_validate(mutated)


def test_provider_relationship_enums_reject_arbitrary_text() -> None:
    provider = _provider_evidence()
    provider["candidates"][0]["diagnostics"]["location_relation"] = {
        "evidence_id": "diagnostic:1:location_relation",
        "value": "RAW PRIVATE RELATION PROSE",
    }
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(provider)


def test_provider_aggregate_property_requires_matching_evidence_id() -> None:
    provider = _provider_evidence()
    provider["candidates"][0]["retrieval"]["dense_score"]["evidence_id"] = (
        "feature:1:not_the_dense_score_property"
    )
    with pytest.raises(ValidationError, match="property"):
        ProviderEvidenceV1.model_validate(provider)


def test_provider_diagnostic_labels_accept_frozen_normalized_multiword_values() -> None:
    bundle = _internal_bundle()
    bundle["candidates"][0]["facts"].append(
        {
            "evidence_id": "diagnostic:1:matched_ai_tools",
            "kind": "diagnostic",
            "candidate_id": "cand_phase9_contract",
            "name": "matched_ai_tools",
            "value": ["structured outputs"],
        }
    )
    provider = project_provider_evidence(InternalEvidenceBundleV1.model_validate(bundle))
    assert not hasattr(provider.candidates[0].diagnostics, "matched_ai_tools")


def test_provider_has_no_free_form_historical_label_surface() -> None:
    provider = _provider_evidence()
    forbidden_payloads = (
        ("job", "role_title", "RAW JD: private company description"),
        ("candidates", "target_roles", ["RAW RESUME: private employment history"]),
        ("candidates", "skills", [{"evidence_id": "candidate:1:skill:0123456789abcdef0123456789abcdef", "name": "RAW RESUME: private employment history", "category": "backend"}]),
        ("candidates", "ai_tools", ["RAW RESUME: private employment history"]),
    )
    for scope, field, value in forbidden_payloads:
        mutated = deepcopy(provider)
        target = mutated[scope][0] if scope == "candidates" else mutated[scope]
        target[field] = value
        with pytest.raises(ValidationError):
            ProviderEvidenceV1.model_validate(mutated)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("job", "requirements", 0, "requirement_id"), "RAW JD: confidential company plan"),
        (("candidates", 0, "candidate_id"), "RAW RESUME: private employment history"),
        (("candidates", 0, "projects", 0, "project_id"), "RAW PROJECT OUTCOME: revenue"),
    ],
)
def test_provider_safe_identifiers_cannot_carry_private_prose(path, value) -> None:
    mutated = _provider_evidence()
    target = mutated
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        ProviderEvidenceV1.model_validate(mutated)


def test_candidate_project_evidence_must_reference_parent_project() -> None:
    bundle = _internal_bundle()
    second = _candidate_at_rank(2, "cand_phase9_second")
    second["projects"][0]["project_id"] = "project_002"
    second["projects"][0]["evidence_id"] = "candidate:2:project:project_002"
    second["project_evidence"][0].update(
        evidence_id="candidate:2:project_evidence:evidence_002",
        source_evidence_id="evidence_002",
        project_id="project_002",
    )
    bundle["candidates"][0]["project_evidence"][0]["project_id"] = "project_002"
    bundle["candidates"].append(second)
    with pytest.raises(ValidationError, match="project owner"):
        InternalEvidenceBundleV1.model_validate(bundle)


def test_output_references_must_exist_and_match_candidate_owner() -> None:
    from app.services.explanation import contracts as explanation_contracts

    validate_explanation_output_references = getattr(
        explanation_contracts, "validate_explanation_output_references", None
    )
    assert callable(validate_explanation_output_references)
    bundle = InternalEvidenceBundleV1.model_validate(_internal_bundle())
    valid_payload = _candidate_output(rank=1)
    valid_payload["candidate_id"] = bundle.candidates[0].candidate_id
    output = CandidateExplanationOutput.model_validate(valid_payload)
    validate_explanation_output_references(output, bundle)

    missing = _candidate_output(rank=1)
    missing["candidate_id"] = bundle.candidates[0].candidate_id
    missing["summary"]["evidence_refs"] = ["candidate:1:project:does_not_exist"]
    missing_output = CandidateExplanationOutput.model_validate(missing)
    with pytest.raises(ValueError, match="does not exist"):
        validate_explanation_output_references(missing_output, bundle)

    bundle_with_second = _internal_bundle()
    bundle_with_second["candidates"].append(_candidate_at_rank(2, "cand_phase9_second"))
    bundle_with_second = InternalEvidenceBundleV1.model_validate(bundle_with_second)
    wrong_owner = _candidate_output(rank=1)
    wrong_owner["candidate_id"] = bundle.candidates[0].candidate_id
    wrong_owner["summary"]["evidence_refs"] = [
        "candidate:2:skill:0123456789abcdef0123456789abcdef"
    ]
    wrong_owner_output = CandidateExplanationOutput.model_validate(wrong_owner)
    with pytest.raises(ValueError, match="owner"):
        validate_explanation_output_references(wrong_owner_output, bundle_with_second)
