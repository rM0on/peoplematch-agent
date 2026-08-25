from __future__ import annotations

import importlib
import json
from copy import deepcopy
from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.schemas.explanations import InternalEvidenceBundleV1
from app.services.explanation.contracts import project_provider_evidence
from app.services.explanation.evidence import build_evidence_facts


def _fact(
    *,
    evidence_id: str,
    kind: str,
    name: str,
    value,
    candidate_id: str = "candidate_001",
) -> dict:
    return {
        "evidence_id": evidence_id,
        "kind": kind,
        "candidate_id": candidate_id,
        "name": name,
        "value": value,
    }


def _bundle() -> InternalEvidenceBundleV1:
    candidate_id = "candidate_001"
    rank = 1
    facts = [
        _fact(
            evidence_id="retrieval:1:retrieval_rank",
            kind="retrieval",
            name="retrieval_rank",
            value=1,
        ),
        _fact(
            evidence_id="retrieval:1:matched_channels",
            kind="retrieval",
            name="matched_channels",
            value=["dense", "sparse"],
        ),
        _fact(
            evidence_id="retrieval:1:dense_score",
            kind="retrieval",
            name="dense_score",
            value=0.8,
        ),
        _fact(
            evidence_id="retrieval:1:sparse_score",
            kind="retrieval",
            name="sparse_score",
            value=4.0,
        ),
        _fact(
            evidence_id="retrieval:1:fusion_score",
            kind="retrieval",
            name="fusion_score",
            value=0.03,
        ),
        _fact(
            evidence_id="ranking:1:result_rank",
            kind="ranking",
            name="result_rank",
            value=1,
        ),
        _fact(
            evidence_id="ranking:1:ltr_rank",
            kind="ranking",
            name="ltr_rank",
            value=1,
        ),
        _fact(
            evidence_id="ranking:1:ltr_score_raw",
            kind="ranking",
            name="ltr_score_raw",
            value=0.4,
        ),
        _fact(
            evidence_id="diagnostic:1:matched_must_have_requirement_ids",
            kind="diagnostic",
            name="matched_must_have_requirement_ids",
            value=["job_requirement:req_python"],
        ),
        _fact(
            evidence_id="diagnostic:1:matched_capabilities",
            kind="diagnostic",
            name="matched_capabilities",
            value=["python"],
        ),
        _fact(
            evidence_id="diagnostic:1:matched_evidence_skills",
            kind="diagnostic",
            name="matched_evidence_skills",
            value=["python"],
        ),
    ]
    facts.extend(
        _fact(
            evidence_id=f"feature:{rank}:{name}",
            kind="feature",
            name=name,
            value=0.5,
        )
        for name in (
            "semantic_score",
            "sparse_score",
            "skill_fit_score",
            "project_evidence_score",
            "role_direction_score",
            "ai_tool_score",
            "location_score",
            "seniority_score",
            "missing_penalty",
            "overclaim_penalty",
        )
    )
    return InternalEvidenceBundleV1.model_validate(
        {
            "contract_version": "evidence_bundle_v1",
            "source": {
                "match_run_id": "00000000-0000-0000-0000-000000000901",
                "ranking_variant": "ltr",
                "workflow_version": "match_run_workflow_v1",
                "workflow_fingerprint": "1" * 64,
                "ranking_input_fingerprint": "2" * 64,
                "result_fingerprint": "3" * 64,
            },
            "job": {
                "job_id": "job_phase93_contract",
                "role_title": "AI Engineer",
                "role_direction": ["applied_ai"],
                "requirements": [
                    {
                        "evidence_id": "job_requirement:req_python",
                        "requirement_id": "req_python",
                        "priority": "must_have",
                        "category": "skill",
                        "text": "Private historical requirement text",
                        "evidence_expectation": "Private historical evidence expectation",
                    }
                ],
                "location": {
                    "cities": ["Shanghai"],
                    "remote_policy": "hybrid",
                    "relocation_supported": True,
                },
                "seniority_requirement": ["senior"],
                "product_stage": "zero_to_one",
            },
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
                {
                    "sequence": 1,
                    "step_name": "resolve_inputs",
                    "status": "COMPLETED",
                }
            ],
            "candidates": [
                {
                    "candidate_id": candidate_id,
                    "result_rank": rank,
                    "target_roles": ["AI Engineer"],
                    "skills": [
                        {
                            "evidence_id": (
                                "candidate:1:skill:"
                                "0123456789abcdef0123456789abcdef"
                            ),
                            "name": "python",
                            "category": "backend",
                        }
                    ],
                    "projects": [
                        {
                            "evidence_id": "candidate:1:project:project_001",
                            "project_id": "project_001",
                            "technologies": ["python"],
                            "skills_demonstrated": ["python"],
                        }
                    ],
                    "project_evidence": [
                        {
                            "evidence_id": (
                                "candidate:1:project_evidence:evidence_001"
                            ),
                            "source_evidence_id": "evidence_001",
                            "project_id": "project_001",
                            "supports_skills": ["python"],
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
                    "facts": facts,
                }
            ],
        }
    )


def _generation_modules():
    contracts = importlib.import_module(
        "app.services.explanation.generation.contracts"
    )
    projection = importlib.import_module(
        "app.services.explanation.generation.reference_projection"
    )
    return contracts, projection


def _project():
    _, projection = _generation_modules()
    bundle = _bundle()
    facts = build_evidence_facts(bundle)
    return bundle, facts, projection.ProviderReferenceProjector().project(
        bundle=bundle,
        evidence_facts=facts,
    )


def _valid_plan_candidate(candidate) -> dict:
    semantic_reason = candidate.facts.match_reasons[0]
    ranking_context = candidate.facts.ranking_context[0]
    comparison_refs = (
        []
        if candidate.facts.comparison is None
        else candidate.facts.comparison.evidence_refs
    )
    return {
        "candidate_ref": candidate.candidate_ref,
        "result_rank": candidate.result_rank,
        "summary": {
            "template_key": "recorded_match_summary",
            "evidence_refs": semantic_reason.evidence_refs,
        },
        "match_reasons": [
            {
                "category": semantic_reason.category,
                "template_key": semantic_reason.statement_key,
                "evidence_refs": semantic_reason.evidence_refs,
            },
            {
                "category": "ranking_context",
                "template_key": "ranking_context_recorded",
                "evidence_refs": ranking_context.evidence_refs,
            },
        ],
        "risk_points": [],
        "interview_question_operations": [],
        "why_not_top1": (
            None
            if candidate.result_rank == 1
            else {
                "template_key": "why_not_top1_recorded",
                "evidence_refs": comparison_refs[:6],
            }
        ),
        "rewrite_operations": [],
    }


def _valid_plan_payload(projected) -> dict:
    return {
        "contract_version": "explanation_plan_v1",
        "candidates": [
            _valid_plan_candidate(candidate)
            for candidate in projected.payload.candidates
        ],
    }


def _two_candidate_bundle() -> InternalEvidenceBundleV1:
    payload = _bundle().model_dump(mode="json")
    second = deepcopy(payload["candidates"][0])
    second["candidate_id"] = "candidate_002"
    second["result_rank"] = 2
    for group in ("skills", "projects", "project_evidence"):
        for item in second[group]:
            item["evidence_id"] = item["evidence_id"].replace(
                "candidate:1:", "candidate:2:"
            )
    for fact in second["facts"]:
        fact["candidate_id"] = "candidate_002"
        fact["evidence_id"] = fact["evidence_id"].replace(":1:", ":2:")
        if fact["name"] in {"retrieval_rank", "result_rank", "ltr_rank"}:
            fact["value"] = 2
    second["facts"].append(
        {
            "evidence_id": "comparison:2:top1:skill_fit_score",
            "kind": "comparison",
            "candidate_id": "candidate_002",
            "name": "skill_fit_score",
            "value": 0.5,
            "comparison_candidate_id": "candidate_001",
        }
    )
    payload["candidates"].append(second)
    return InternalEvidenceBundleV1.model_validate(payload)


def test_provider_reference_projection_is_deterministic_and_opaque() -> None:
    _, _, first = _project()
    _, _, second = _project()

    assert first.payload == second.payload
    assert first.reference_map.internal_to_provider == (
        second.reference_map.internal_to_provider
    )
    assert first.reference_map.candidate_to_provider == (
        second.reference_map.candidate_to_provider
    )
    assert set(first.reference_map.internal_to_provider.values()) == {
        f"ref_{index:04d}"
        for index in range(1, len(first.reference_map.internal_to_provider) + 1)
    }
    serialized = first.payload.model_dump_json()
    assert "job_requirement:" not in serialized
    assert "candidate:1:" not in serialized
    assert "feature:1:" not in serialized
    assert "ranking:1:" not in serialized
    assert "retrieval:1:" not in serialized
    assert "diagnostic:1:" not in serialized


def test_provider_prompt_projection_excludes_internal_history_and_prose() -> None:
    _, _, projected = _project()
    serialized = projected.payload.model_dump_json()

    for forbidden in (
        "workflow_fingerprint",
        "ranking_input_fingerprint",
        "result_fingerprint",
        "runtime_provenance",
        "workflow_trace",
        "Private historical requirement text",
        "Private historical evidence expectation",
        "raw_resume",
        "raw_jd",
        "candidate_001",
    ):
        assert forbidden not in serialized


def test_reference_map_contains_only_canonical_provider_safe_evidence_ids() -> None:
    _, _, projected = _project()

    # These diagnostics are intentionally retained only in the richer internal
    # audit bundle and are absent from the frozen provider-safe projection.
    assert "diagnostic:1:matched_capabilities" not in (
        projected.reference_map.internal_to_provider
    )
    assert "diagnostic:1:matched_evidence_skills" not in (
        projected.reference_map.internal_to_provider
    )
    serialized = projected.payload.model_dump_json()
    for provider_ref in projected.reference_map.provider_to_internal:
        # A mapped reference may be an operation source even when it is not a
        # displayed fact, but it must originate in the canonical provider-safe
        # projection rather than internal-only history.
        assert provider_ref.startswith("ref_")
    assert "ref_" in serialized


def test_reference_map_contains_exactly_refs_exposed_in_provider_prompt() -> None:
    _, _, projected = _project()

    def collect(value) -> set[str]:
        if isinstance(value, dict):
            return {
                ref
                for item in value.values()
                for ref in collect(item)
            }
        if isinstance(value, list):
            return {ref for item in value for ref in collect(item)}
        if isinstance(value, str) and value.startswith("ref_"):
            return {value}
        return set()

    prompt_refs = collect(projected.payload.model_dump(mode="json"))

    assert set(projected.reference_map.provider_to_internal) == prompt_refs
    assert len(prompt_refs) == len(projected.reference_map.internal_to_provider)


def test_provider_projection_rejects_semantically_forged_evidence_facts() -> None:
    _, projection = _generation_modules()
    bundle = _bundle()
    facts = build_evidence_facts(bundle)
    facts.candidates[0].ranking_context[0].dimension = "seniority_score"

    with pytest.raises(ValueError, match="ranking context|semantic|historical"):
        projection.ProviderReferenceProjector().project(
            bundle=bundle,
            evidence_facts=facts,
        )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("candidates", 0, "summary", "text"), "Strong Rust experience"),
        (("candidates", 0, "match_reasons", 0, "text"), "Guaranteed hire"),
        (("metadata",), {"raw_resume": "private"}),
    ],
)
def test_explanation_plan_rejects_provider_authored_prose_and_metadata(
    path: tuple, value,
) -> None:
    contracts, _ = _generation_modules()
    _, _, projected = _project()
    payload = _valid_plan_payload(projected)
    target = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        contracts.ExplanationPlanV1.model_validate(payload)


def test_explanation_plan_rejects_internal_evidence_id_as_provider_ref() -> None:
    contracts, _ = _generation_modules()
    _, _, projected = _project()
    payload = _valid_plan_payload(projected)
    payload["candidates"][0]["summary"]["evidence_refs"] = [
        "job_requirement:req_python"
    ]

    with pytest.raises(ValidationError):
        contracts.ExplanationPlanV1.model_validate(payload)


def test_reference_resolution_restores_internal_ids_without_persisting_refs() -> None:
    contracts, projection = _generation_modules()
    bundle, facts, projected = _project()
    plan = contracts.ExplanationPlanV1.model_validate(_valid_plan_payload(projected))

    resolved = projection.resolve_explanation_plan(
        plan,
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    )

    serialized = json.dumps(resolved.model_dump(mode="json"), sort_keys=True)
    assert "ref_" not in serialized
    assert "candidate_0001" not in serialized
    assert resolved.candidates[0].candidate_id == "candidate_001"
    assert any(
        ref.startswith(("candidate:1:", "job_requirement:", "feature:1:"))
        for ref in resolved.candidates[0].summary.evidence_refs
    )


def test_reference_resolution_rejects_unknown_and_cross_candidate_refs() -> None:
    contracts, projection = _generation_modules()
    bundle, facts, projected = _project()
    payload = _valid_plan_payload(projected)
    payload["candidates"][0]["summary"]["evidence_refs"] = ["ref_9999"]
    plan = contracts.ExplanationPlanV1.model_validate(payload)

    with pytest.raises(ValueError, match="unknown provider reference"):
        projection.resolve_explanation_plan(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_reference_resolution_rejects_known_cross_candidate_reference() -> None:
    contracts, projection = _generation_modules()
    bundle = _two_candidate_bundle()
    facts = build_evidence_facts(bundle)
    projected = projection.ProviderReferenceProjector().project(
        bundle=bundle,
        evidence_facts=facts,
    )
    payload = _valid_plan_payload(projected)
    rank_two_internal = next(
        evidence_id
        for evidence_id in projected.reference_map.internal_to_provider
        if ":2:" in evidence_id
    )
    payload["candidates"][0]["summary"]["evidence_refs"] = [
        projected.reference_map.internal_to_provider[rank_two_internal]
    ]
    plan = contracts.ExplanationPlanV1.model_validate(payload)

    with pytest.raises(ValueError, match="owner"):
        projection.resolve_explanation_plan(
            plan,
            reference_map=projected.reference_map,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_reference_map_is_immutable_and_bound_to_projection() -> None:
    contracts, projection = _generation_modules()
    bundle, facts, projected = _project()
    first_provider_ref = next(iter(projected.reference_map.provider_to_internal))

    with pytest.raises(TypeError):
        projected.reference_map.provider_to_internal[first_provider_ref] = (
            "ranking:1:ltr_rank"
        )

    forged_reverse = dict(projected.reference_map.provider_to_internal)
    forged_reverse[first_provider_ref] = "ranking:1:ltr_rank"
    forged = replace(
        projected.reference_map,
        provider_to_internal=forged_reverse,
    )
    plan = contracts.ExplanationPlanV1.model_validate(
        _valid_plan_payload(projected)
    )
    with pytest.raises(ValueError, match="mapping|projection|binding"):
        projection.resolve_explanation_plan(
            plan,
            reference_map=forged,
            bundle=bundle,
            evidence_facts=facts,
        )


def test_plan_rejects_duplicate_or_noncanonical_selections() -> None:
    contracts, _ = _generation_modules()
    _, _, projected = _project()
    duplicate_ref = _valid_plan_payload(projected)
    refs = duplicate_ref["candidates"][0]["summary"]["evidence_refs"]
    duplicate_ref["candidates"][0]["summary"]["evidence_refs"] = [
        refs[0],
        refs[0],
    ]
    with pytest.raises(ValidationError, match="unique|canonical"):
        contracts.ExplanationPlanV1.model_validate(duplicate_ref)

    reversed_reasons = _valid_plan_payload(projected)
    reversed_reasons["candidates"][0]["match_reasons"].reverse()
    with pytest.raises(ValidationError, match="unique|canonical"):
        contracts.ExplanationPlanV1.model_validate(reversed_reasons)


def test_provider_prompt_and_plan_are_closed_contracts() -> None:
    contracts, _ = _generation_modules()
    _, _, projected = _project()

    prompt_payload = projected.payload.model_dump(mode="json")
    prompt_payload["extra"] = {"raw_jd": "private"}
    with pytest.raises(ValidationError):
        contracts.ProviderPromptEvidenceV1.model_validate(prompt_payload)

    plan_payload = deepcopy(_valid_plan_payload(projected))
    plan_payload["candidates"][0]["match_reasons"][0]["category"] = (
        "personality_verified"
    )
    with pytest.raises(ValidationError):
        contracts.ExplanationPlanV1.model_validate(plan_payload)


def test_plan_allows_ranking_context_without_a_semantic_reason() -> None:
    contracts, _ = _generation_modules()
    _, _, projected = _project()
    payload = _valid_plan_payload(projected)
    ranking = projected.payload.candidates[0].facts.ranking_context[0]
    payload["candidates"][0]["match_reasons"] = [
        {
            "category": "ranking_context",
            "template_key": "ranking_context_recorded",
            "evidence_refs": ranking.evidence_refs,
        }
    ]

    plan = contracts.ExplanationPlanV1.model_validate(payload)

    assert plan.candidates[0].match_reasons[0].category == "ranking_context"


@pytest.mark.parametrize("section", ["risk_points", "interview_question_operations", "rewrite_operations"])
def test_plan_rejects_duplicate_operation_selections(section: str) -> None:
    contracts, _ = _generation_modules()
    _, _, projected = _project()
    payload = _valid_plan_payload(projected)
    refs = projected.payload.candidates[0].facts.match_reasons[0].evidence_refs
    if section == "risk_points":
        selection = {
            "category": "missing_requirement",
            "template_key": "missing_requirement",
            "evidence_refs": refs,
        }
    elif section == "interview_question_operations":
        selection = {
            "operation": "ask_evidence_clarification",
            "evidence_refs": refs,
        }
    else:
        selection = {
            "operation": "surface_existing_skill",
            "evidence_refs": refs,
        }
    payload["candidates"][0][section] = [selection, deepcopy(selection)]

    with pytest.raises(ValidationError, match="unique|canonical"):
        contracts.ExplanationPlanV1.model_validate(payload)


def test_plan_rejects_noncanonical_risk_selection_order() -> None:
    contracts, _ = _generation_modules()
    _, _, projected = _project()
    payload = _valid_plan_payload(projected)
    refs = projected.payload.candidates[0].facts.match_reasons[0].evidence_refs
    payload["candidates"][0]["risk_points"] = [
        {
            "category": "weak_evidence",
            "template_key": "partial_requirement_evidence",
            "evidence_refs": refs,
        },
        {
            "category": "missing_requirement",
            "template_key": "missing_requirement",
            "evidence_refs": refs,
        },
    ]

    with pytest.raises(ValidationError, match="unique|canonical"):
        contracts.ExplanationPlanV1.model_validate(payload)


def test_plan_rejects_reason_count_that_frozen_output_cannot_render() -> None:
    contracts, _ = _generation_modules()
    _, _, projected = _project()
    payload = _valid_plan_payload(projected)
    ref = projected.payload.candidates[0].facts.ranking_context[0].evidence_refs
    payload["candidates"][0]["match_reasons"] = [
        {
            "category": category,
            "template_key": template_key,
            "evidence_refs": ref,
        }
        for category, template_key in (
            ("skill_fit", "skill_fit_recorded"),
            ("project_evidence", "project_evidence_recorded"),
            ("location", "location_recorded"),
            ("seniority", "seniority_recorded"),
            ("ranking_context", "ranking_context_recorded"),
        )
    ]

    with pytest.raises(ValidationError):
        contracts.ExplanationPlanV1.model_validate(payload)


def test_plan_rejects_rewrite_count_that_frozen_output_cannot_render() -> None:
    contracts, _ = _generation_modules()
    bundle, _, projected = _project()
    payload = _valid_plan_payload(projected)
    skill_ref = projected.reference_map.internal_to_provider[
        bundle.candidates[0].skills[0].evidence_id
    ]
    project_ref = projected.reference_map.internal_to_provider[
        bundle.candidates[0].projects[0].evidence_id
    ]
    record_ref = projected.reference_map.internal_to_provider[
        bundle.candidates[0].project_evidence[0].evidence_id
    ]
    operations = [
        contracts.PlanRewriteOperation(
            operation="surface_existing_skill", evidence_refs=[skill_ref]
        ),
        contracts.PlanRewriteOperation(
            operation="link_skill_to_project",
            evidence_refs=sorted([skill_ref, project_ref]),
        ),
        contracts.PlanRewriteOperation(
            operation="clarify_evidence_status", evidence_refs=[record_ref]
        ),
        contracts.PlanRewriteOperation(
            operation="reorder_existing_claim", evidence_refs=[project_ref]
        ),
    ]
    payload["candidates"][0]["rewrite_operations"] = [
        item.model_dump(mode="json")
        for item in sorted(operations, key=lambda item: item.model_dump_json())
    ]

    with pytest.raises(ValidationError):
        contracts.ExplanationPlanV1.model_validate(payload)


@pytest.mark.parametrize(
    ("section", "count", "selection"),
    [
        (
            "risk_points",
            5,
            {
                "category": "missing_requirement",
                "template_key": "missing_requirement",
            },
        ),
        (
            "interview_question_operations",
            4,
            {"operation": "ask_evidence_clarification"},
        ),
    ],
)
def test_plan_rejects_all_list_counts_above_frozen_output_limits(
    section: str, count: int, selection: dict
) -> None:
    contracts, _ = _generation_modules()
    _, _, projected = _project()
    payload = _valid_plan_payload(projected)
    refs = projected.payload.candidates[0].facts.ranking_context[0].evidence_refs
    payload["candidates"][0][section] = [
        {**selection, "evidence_refs": refs}
        for _ in range(count)
    ]

    with pytest.raises(ValidationError):
        contracts.ExplanationPlanV1.model_validate(payload)


@pytest.mark.parametrize(("section", "count"), [("match_reasons", 5), ("rewrite_operations", 4)])
def test_resolved_plan_cannot_bypass_frozen_output_cardinality(
    section: str, count: int
) -> None:
    contracts, projection = _generation_modules()
    bundle, facts, projected = _project()
    plan = contracts.ExplanationPlanV1.model_validate(_valid_plan_payload(projected))
    resolved = projection.resolve_explanation_plan(
        plan,
        reference_map=projected.reference_map,
        bundle=bundle,
        evidence_facts=facts,
    ).model_dump(mode="json")
    source = (
        resolved["candidates"][0][section][0]
        if section == "match_reasons"
        else {
            "operation": "surface_existing_skill",
            "evidence_refs": [bundle.candidates[0].skills[0].evidence_id],
        }
    )
    resolved["candidates"][0][section] = [deepcopy(source) for _ in range(count)]

    with pytest.raises(ValidationError):
        contracts.ResolvedExplanationPlanV1.model_validate(resolved)
