from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services.explanation.contracts import evidence_bundle_fingerprint
from app.services.match_runs.contracts import (
    DIAGNOSTICS_CONTRACT_VERSION,
    STEP_REFS_CONTRACT_VERSION,
    WORKFLOW_FINGERPRINT,
    WORKFLOW_VERSION,
    canonical_fingerprint,
)


ROOT = Path(__file__).resolve().parents[2]

_PHASE8_RESULT_FIELDS = (
    "candidate_id",
    "result_rank",
    "candidate_input_contract_version",
    "candidate_input_fingerprint",
    "retrieval_rank",
    "matched_channels",
    "dense_rank",
    "dense_score",
    "sparse_rank",
    "sparse_score",
    "fusion_score",
    "semantic_score",
    "skill_fit_score",
    "project_evidence_score",
    "role_direction_score",
    "ai_tool_score",
    "location_score",
    "seniority_score",
    "missing_penalty",
    "overclaim_penalty",
    "feature_diagnostics_contract_version",
    "feature_diagnostics",
    "ltr_rank",
    "ltr_score_raw",
    "cross_encoder_rank",
    "cross_encoder_score_raw",
)


def _candidate_snapshot(candidate_id: str) -> dict:
    project_id = f"project_{candidate_id.rsplit('_', 1)[-1]}"
    return {
        "contract_version": "candidate_input_snapshot_v1",
        "candidate_id": candidate_id,
        "target_roles": ["AI Engineer"],
        "skills": [{"name": "Python", "category": "backend"}],
        "projects": [
            {
                "project_id": project_id,
                "technologies": ["Python"],
                "skills_demonstrated": ["Python"],
            }
        ],
        "project_evidence": [
            {
                "evidence_id": "evidence_001",
                "project_id": project_id,
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
    }


def _run(*, reverse_results: bool = False, run_id: str = "run_001"):
    results = []
    for rank, candidate_id in ((1, "candidate_001"), (2, "candidate_002")):
        results.append(
            SimpleNamespace(
                run_id=run_id,
                candidate_id=candidate_id,
                result_rank=rank,
                candidate_input_contract_version="candidate_input_snapshot_v1",
                candidate_input_fingerprint=f"{rank}" * 64,
                candidate_input_snapshot=_candidate_snapshot(candidate_id),
                retrieval_rank=rank,
                matched_channels=["dense", "sparse"],
                dense_rank=rank,
                dense_score=0.9 - rank / 10,
                sparse_rank=rank,
                sparse_score=0.8 - rank / 10,
                fusion_score=0.7 - rank / 10,
                semantic_score=0.9 - rank / 10,
                skill_fit_score=0.8 - rank / 10,
                project_evidence_score=0.7 - rank / 10,
                role_direction_score=0.6 - rank / 10,
                ai_tool_score=0.5 - rank / 10,
                location_score=1.0,
                seniority_score=1.0,
                missing_penalty=0.1 * rank,
                overclaim_penalty=0.0,
                feature_diagnostics_contract_version="selected_feature_diagnostics_v1",
                feature_diagnostics={
                    "contract_version": DIAGNOSTICS_CONTRACT_VERSION,
                    "availability": {
                        "semantic_score": True,
                        "sparse_score": True,
                        "skill_fit_score": True,
                        "project_evidence_score": True,
                        "role_direction_score": True,
                        "ai_tool_score": True,
                        "location_score": True,
                        "seniority_score": True,
                        "missing_penalty": True,
                        "overclaim_penalty": True,
                    },
                    "matched_must_have_requirement_ids": ["req_python"],
                    "weak_matched_must_have_requirement_ids": [],
                    "missing_must_have_requirement_ids": (
                        ["req_missing"] if rank == 2 else []
                    ),
                    "matched_nice_to_have_requirement_ids": [],
                    "evidence_supported_requirement_ids": ["req_python"],
                    "matched_capabilities": ["Python"],
                    "matched_evidence_skills": ["Python"],
                    "matched_ai_tools": ["structured outputs"],
                    "location_relation": "exact_match",
                    "seniority_relation": "exact_match",
                    "overclaim_level": "low",
                    "overclaim_reason_count": 0,
                    "retrieval_rank": rank,
                    "dense_rank": rank,
                    "sparse_rank": rank,
                    "fusion_score": 0.7 - rank / 10,
                },
                ltr_rank=rank,
                ltr_score_raw=0.4 - rank / 100,
                cross_encoder_rank=None,
                cross_encoder_score_raw=None,
            )
        )
    if reverse_results:
        results.reverse()
    run = SimpleNamespace(
        run_id=run_id,
        requested_job_id="job_001",
        job_id="job_001",
        request_id="request_001",
        ranking_variant="ltr",
        status="COMPLETED",
        request_parameters={"retrieval_pool_k": 20, "top_k": 10},
        workflow_version=WORKFLOW_VERSION,
        workflow_fingerprint=WORKFLOW_FINGERPRINT,
        ranking_input_contract_version="ranking_input_snapshot_v1",
        ranking_input_fingerprint="2" * 64,
        ranking_input_snapshot={
            "contract_version": "ranking_input_snapshot_v1",
            "job_id": "job_001",
            "role_title": "AI Engineer",
            "role_direction": ["applied_ai"],
            "must_have": [
                {
                    "requirement_id": "req_python",
                    "category": "skill",
                    "text": "Python",
                    "evidence_expectation": "structured evidence",
                },
                {
                    "requirement_id": "req_missing",
                    "category": "skill",
                    "text": "Go",
                    "evidence_expectation": "structured evidence",
                },
            ],
            "nice_to_have": [
                {
                    "requirement_id": "req_unknown",
                    "category": "skill",
                    "text": "Go",
                    "evidence_expectation": "structured evidence",
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
        retrieval_document_version="retrieval_doc_v4",
        retrieval_configuration_fingerprint="3" * 64,
        retrieval_provenance={"strategy": "hybrid"},
        feature_version="feature_schema_v1",
        feature_fingerprint="4" * 64,
        ranker_version="ltr_ranker_v1",
        ranker_model_sha256="5" * 64,
        ce_provenance=None,
        result_count=2,
        result_fingerprint=None,
        results=results,
        steps=[
            SimpleNamespace(
                run_id=run_id,
                sequence=1,
                step_name="resolve_inputs",
                status="COMPLETED",
                contract_version=STEP_REFS_CONTRACT_VERSION,
            ),
            SimpleNamespace(
                run_id=run_id,
                sequence=2,
                step_name="phase6_ltr_rank",
                status="COMPLETED",
                contract_version=STEP_REFS_CONTRACT_VERSION,
            ),
            SimpleNamespace(
                run_id=run_id,
                sequence=3,
                step_name="persist_results",
                status="COMPLETED",
                contract_version=STEP_REFS_CONTRACT_VERSION,
            ),
        ],
    )
    _refresh_ranking_snapshot_fingerprint(run)
    for result in run.results:
        _refresh_candidate_snapshot_fingerprint(result)
    _refresh_result_fingerprint(run)
    return run


def _refresh_ranking_snapshot_fingerprint(run) -> None:
    run.ranking_input_fingerprint = canonical_fingerprint(
        {
            "job_snapshot": run.ranking_input_snapshot,
            "ranking_variant": run.ranking_variant,
            "request_parameters": run.request_parameters,
            "workflow_version": run.workflow_version,
            "workflow_fingerprint": run.workflow_fingerprint,
            "provenance": {
                "retrieval_document_version": run.retrieval_document_version,
                "retrieval_configuration_fingerprint": (
                    run.retrieval_configuration_fingerprint
                ),
                "feature_version": run.feature_version,
                "feature_fingerprint": run.feature_fingerprint,
                "ranker_version": run.ranker_version,
                "ranker_model_sha256": run.ranker_model_sha256,
            },
        }
    )


def _refresh_candidate_snapshot_fingerprint(result) -> None:
    result.candidate_input_fingerprint = canonical_fingerprint(
        result.candidate_input_snapshot
    )


def _refresh_result_fingerprint(run) -> None:
    """Reproduce the frozen Phase 8 result fingerprint payload independently."""

    rows = [
        {name: getattr(result, name) for name in _PHASE8_RESULT_FIELDS}
        for result in sorted(run.results, key=lambda item: item.result_rank)
    ]
    run.result_fingerprint = canonical_fingerprint(
        {
            "ranking_variant": run.ranking_variant,
            "provenance": {
                "workflow_fingerprint": run.workflow_fingerprint,
                "feature_fingerprint": run.feature_fingerprint,
                "ranker_model_sha256": run.ranker_model_sha256,
                "ce": run.ce_provenance,
                "retrieval": run.retrieval_provenance,
            },
            "results": rows,
        }
    )


def _set_cross_encoder_workflow(run) -> None:
    run.steps = [
        SimpleNamespace(
            run_id=run.run_id,
            sequence=sequence,
            step_name=step_name,
            status="COMPLETED",
            contract_version=STEP_REFS_CONTRACT_VERSION,
        )
        for sequence, step_name in enumerate(
            (
                "resolve_inputs",
                "phase6_ltr_rank",
                "phase7_cross_encoder_rerank",
                "persist_results",
            ),
            start=1,
        )
    ]


def _engine_module():
    import importlib

    return importlib.import_module("app.services.explanation.evidence")


def test_same_historical_match_run_produces_same_bundle_and_fingerprint() -> None:
    module = _engine_module()
    builder = module.EvidenceBundleBuilder()
    first = builder.build(_run())
    second = builder.build(_run())
    assert first == second
    assert evidence_bundle_fingerprint(first) == evidence_bundle_fingerprint(second)
    for candidate in first.candidates:
        assert [fact.evidence_id for fact in candidate.facts] == sorted(
            fact.evidence_id for fact in candidate.facts
        )
    assert any(
        fact.name == "matched_capabilities" for fact in first.candidates[0].facts
    )


def test_bundle_accepts_authentic_phase8_ranking_input_fingerprint() -> None:
    module = _engine_module()

    bundle = module.EvidenceBundleBuilder().build(_run())

    assert bundle.source.ranking_input_fingerprint


def test_generation_pipeline_accepts_chinese_historical_labels_and_all_requirement_categories() -> None:
    from app.schemas.job import RequirementCategory
    from app.services.explanation.generation.pipeline import (
        ExplanationGenerationPipeline,
    )

    run = _run()
    run.ranking_input_snapshot["location"]["cities"] = ["上海"]
    run.ranking_input_snapshot["nice_to_have"].extend(
        {
            "requirement_id": f"req_category_{category.value}",
            "category": category.value,
            "text": f"Requirement for {category.value}",
            "evidence_expectation": "bounded historical evidence",
        }
        for category in RequirementCategory
    )
    for result in run.results:
        result.candidate_input_snapshot["target_roles"] = ["推荐算法工程师"]
        result.candidate_input_snapshot["preferred_locations"]["cities"] = ["上海"]
        _refresh_candidate_snapshot_fingerprint(result)
    _refresh_ranking_snapshot_fingerprint(run)
    _refresh_result_fingerprint(run)

    prepared = ExplanationGenerationPipeline(
        max_output_tokens=1024,
    ).prepare(run, requested_top_k=2)

    assert prepared.evidence_bundle.job.location.cities == ["上海"]
    assert prepared.evidence_bundle.candidates[0].target_roles == ["推荐算法工程师"]
    assert {item.category.value for item in prepared.evidence_bundle.job.requirements} == {
        category.value for category in RequirementCategory
    }
    assert prepared.effective_top_k == 2


def test_candidate_input_order_does_not_change_canonical_bundle() -> None:
    module = _engine_module()
    builder = module.EvidenceBundleBuilder()
    assert builder.build(_run()) == builder.build(_run(reverse_results=True))


def test_bundle_uses_historical_snapshots_not_current_profiles_or_qdrant() -> None:
    module = _engine_module()
    run = _run()
    run.current_candidate = {"raw_resume": "private"}
    run.qdrant = SimpleNamespace(search=lambda *_args: pytest.fail("Qdrant called"))
    bundle = module.EvidenceBundleBuilder().build(run)
    assert bundle.candidates[0].candidate_id == "candidate_001"


def test_requirement_builder_emits_matched_missing_and_not_assessed_facts() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.MissingRequirementBuilder().build(bundle)
    statuses = {fact.requirement_id: fact.status for fact in facts}
    assert statuses["req_python"] == "matched"
    assert statuses["req_missing"] == "missing"
    assert statuses["req_unknown"] == "not_assessed"


def test_top1_comparison_is_null_for_rank_one_and_owned_by_rank_one() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.Top1ComparisonBuilder().build(bundle)
    assert facts[0].comparison is None
    assert facts[1].comparison is not None
    assert facts[1].comparison.top1_candidate_id == "candidate_001"
    assert any(
        item.dimension == "retrieval_rank"
        for item in facts[1].comparison.comparisons
    )
    assert any(
        item.dimension == "requirement_evidence_coverage"
        for item in facts[1].comparison.comparisons
    )


def test_fact_builder_returns_complete_validated_fact_aggregate() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.EvidenceFactBuilder().build(bundle)
    assert facts[0].comparison is None
    assert facts[1].comparison is not None
    assert facts[1].match_reasons[0].evidence_refs[0].startswith("candidate:2:")
    assert any(
        item.evidence_refs == ["feature:2:skill_fit_score"]
        for item in facts[1].ranking_context
    )
    aggregate = module.build_evidence_facts(bundle)
    assert aggregate.contract_version == "evidence_facts_v1"
    assert aggregate.bundle_fingerprint == evidence_bundle_fingerprint(bundle)


def test_fact_aggregate_validation_rejects_cross_candidate_reference() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    aggregate = module.build_evidence_facts(bundle)
    aggregate.candidates[1].match_reasons[0].evidence_refs = [
        next(
            fact.evidence_id
            for fact in bundle.candidates[0].facts
            if fact.kind.value == "feature"
        )
    ]
    with pytest.raises(ValueError, match="owner"):
        module.validate_evidence_facts(bundle, aggregate)


def test_fact_aggregate_validation_rejects_semantically_incompatible_reference() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    aggregate = module.build_evidence_facts(bundle)
    aggregate.candidates[0].missing_requirements[0].evidence_refs = [
        bundle.candidates[0].skills[0].evidence_id
    ]
    with pytest.raises(ValueError, match="incompatible"):
        module.validate_evidence_facts(bundle, aggregate)


def test_fact_aggregate_validation_rejects_bundle_fingerprint_mismatch() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    aggregate = module.build_evidence_facts(bundle)
    aggregate.bundle_fingerprint = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        module.validate_evidence_facts(bundle, aggregate)


def test_cross_match_run_comparison_is_rejected() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    with pytest.raises(ValueError, match="Evidence Bundle"):
        module.validate_fact_references(
            bundle,
            candidate_id="candidate_002",
            result_rank=2,
            evidence_refs=["comparison:2:top1:skill_fit_score"],
            expected_run_id="other_run",
        )


@pytest.mark.parametrize("field", ["raw_resume", "raw_jd", "project_prose"])
def test_fact_contract_rejects_private_or_prose_escape_hatches(field: str) -> None:
    module = _engine_module()
    with pytest.raises(ValidationError):
        module.MatchReasonFact.model_validate(
            {
                "category": "skill_fit",
                "statement_key": "skill_fit_recorded",
                "evidence_refs": ["feature:1:skill_fit_score"],
                field: "private",
            }
        )


def test_fact_reference_validation_rejects_unknown_and_cross_candidate_ids() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    with pytest.raises(ValueError, match="does not exist"):
        module.validate_fact_references(
            bundle,
            candidate_id="candidate_001",
            result_rank=1,
            evidence_refs=["candidate:1:skill:does_not_exist"],
        )
    with pytest.raises(ValueError, match="owner"):
        module.validate_fact_references(
            bundle,
            candidate_id="candidate_001",
            result_rank=1,
            evidence_refs=[bundle.candidates[1].skills[0].evidence_id],
        )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("results", 0, "dense_score"), "RAW RESUME: private employment"),
        (("results", 0, "matched_channels", 0), "RAW JD: private company description"),
        (("ranking_input_snapshot", "must_have", 0, "requirement_id"), "retrieval:1:skill_fit_score"),
        (("results", 0, "feature_diagnostics", "matched_ai_tools"), "RAW RESUME: private employment"),
    ],
)
def test_bundle_rejects_private_text_or_non_numeric_historical_values(path, value) -> None:
    module = _engine_module()
    run = _run()
    target = run
    for part in path[:-1]:
        target = target[part] if isinstance(part, int) else getattr(target, part) if not isinstance(target, dict) else target[part]
    final = path[-1]
    if isinstance(target, dict):
        target[final] = value
    elif isinstance(final, int):
        target[final] = value
    else:
        setattr(target, final, value)
    _refresh_result_fingerprint(run)
    with pytest.raises((ValueError, ValidationError)):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_does_not_copy_raw_resume_jd_or_project_prose_fields() -> None:
    module = _engine_module()
    run = _run()
    run.ranking_input_snapshot["raw_jd"] = "RAW JD: private company description"
    run.results[0].candidate_input_snapshot["raw_resume"] = "RAW RESUME: private employment"
    run.results[0].candidate_input_snapshot["project_prose"] = "private project outcome"
    _refresh_ranking_snapshot_fingerprint(run)
    _refresh_candidate_snapshot_fingerprint(run.results[0])
    _refresh_result_fingerprint(run)
    bundle = module.EvidenceBundleBuilder().build(run)
    payload = bundle.model_dump(mode="json")
    assert "raw_jd" not in payload["job"]
    assert "raw_resume" not in payload["candidates"][0]
    assert "project_prose" not in payload["candidates"][0]


def test_bundle_rejects_project_evidence_owned_by_unknown_project() -> None:
    module = _engine_module()
    run = _run()
    run.results[1].candidate_input_snapshot["project_evidence"][0]["project_id"] = "project_other"
    _refresh_candidate_snapshot_fingerprint(run.results[1])
    _refresh_result_fingerprint(run)
    with pytest.raises((ValueError, ValidationError), match="project"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_project_evidence_owned_by_another_candidate() -> None:
    module = _engine_module()
    run = _run()
    run.results[1].candidate_input_snapshot["project_evidence"][0]["project_id"] = "project_001"
    _refresh_candidate_snapshot_fingerprint(run.results[1])
    _refresh_result_fingerprint(run)
    with pytest.raises((ValueError, ValidationError), match="project"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_result_from_another_match_run() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].run_id = "run_other"
    with pytest.raises(ValueError, match="MatchRun"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_omits_comparison_for_unavailable_optional_score() -> None:
    module = _engine_module()
    run = _run()
    run.results[1].skill_fit_score = None
    _refresh_result_fingerprint(run)
    bundle = module.EvidenceBundleBuilder().build(run)
    assert not any(
        fact.name == "skill_fit_score" and fact.kind.value == "comparison"
        for fact in bundle.candidates[1].facts
    )


def test_cross_encoder_variant_preserves_ce_provenance_and_facts() -> None:
    module = _engine_module()
    run = _run()
    run.ranking_variant = "cross_encoder_experiment"
    _set_cross_encoder_workflow(run)
    _refresh_ranking_snapshot_fingerprint(run)
    run.ce_provenance = {
        "reranker_version": "ce_v1",
        "model_id": "model_1",
        "model_revision": "revision_1",
        "snapshot_fingerprint": "7" * 64,
        "text_schema_version": "ce_text_v1",
        "text_contract_fingerprint": "8" * 64,
        "pair_order": "job_candidate",
        "score_type": "raw",
        "score_direction": "higher_is_better",
        "calibration": False,
    }
    for result in run.results:
        result.cross_encoder_rank = result.result_rank
        result.cross_encoder_score_raw = 0.2 + result.result_rank / 100
    _refresh_result_fingerprint(run)
    bundle = module.EvidenceBundleBuilder().build(run)
    assert bundle.runtime_provenance.cross_encoder is not None
    assert any(
        fact.name == "cross_encoder_rank" and fact.kind.value == "comparison"
        for fact in bundle.candidates[1].facts
    )


def test_cross_encoder_variant_requires_provenance() -> None:
    module = _engine_module()
    run = _run()
    run.ranking_variant = "cross_encoder_experiment"
    _set_cross_encoder_workflow(run)
    _refresh_ranking_snapshot_fingerprint(run)
    for result in run.results:
        result.cross_encoder_rank = result.result_rank
        result.cross_encoder_score_raw = 0.2 + result.result_rank / 100
    _refresh_result_fingerprint(run)
    with pytest.raises((ValueError, ValidationError), match="Cross-Encoder"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_job_snapshot_identity_mismatch() -> None:
    module = _engine_module()
    run = _run()
    run.ranking_input_snapshot["job_id"] = "job_other"
    _refresh_ranking_snapshot_fingerprint(run)
    with pytest.raises(ValueError, match="Job identity"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_requested_resolved_job_lineage_mismatch() -> None:
    module = _engine_module()
    run = _run()
    run.requested_job_id = "job_other"

    with pytest.raises(ValueError, match="Job identities"):
        module.EvidenceBundleBuilder().build(run)


@pytest.mark.parametrize(
    "mutation",
    [
        "renamed",
        "missing",
        "reordered",
        "sequence",
        "extra",
        "contract_version",
        "owner",
    ],
)
def test_bundle_rejects_noncanonical_historical_workflow(mutation: str) -> None:
    module = _engine_module()
    run = _run()
    if mutation == "renamed":
        run.steps[1].step_name = "renamed_phase"
    elif mutation == "missing":
        run.steps.pop(1)
    elif mutation == "reordered":
        run.steps.reverse()
    elif mutation == "sequence":
        run.steps[0].sequence = 2
        run.steps[1].sequence = 1
    elif mutation == "extra":
        run.steps.append(
            SimpleNamespace(
                run_id=run.run_id,
                sequence=4,
                step_name="unexpected_phase",
                status="COMPLETED",
                contract_version=STEP_REFS_CONTRACT_VERSION,
            )
        )
    elif mutation == "contract_version":
        run.steps[0].contract_version = "match_run_step_refs_v2"
    else:
        run.steps[0].run_id = "run_other"

    with pytest.raises(ValueError, match="workflow|RunStep"):
        module.EvidenceBundleBuilder().build(run)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workflow_version", "match_run_workflow_v2"),
        ("workflow_fingerprint", "f" * 64),
    ],
)
def test_bundle_rejects_self_consistent_unsupported_workflow_commitment(
    field: str, value: str
) -> None:
    module = _engine_module()
    run = _run()
    setattr(run, field, value)
    _refresh_ranking_snapshot_fingerprint(run)
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="workflow"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_unsupported_historical_ranking_variant() -> None:
    module = _engine_module()
    run = _run()
    run.ranking_variant = "future_ranker"
    _refresh_ranking_snapshot_fingerprint(run)
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="unsupported historical ranking variant"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_tampered_ranking_snapshot() -> None:
    module = _engine_module()
    run = _run()
    run.ranking_input_snapshot["role_title"] = "tampered role"

    with pytest.raises(ValueError, match="ranking input snapshot fingerprint"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_tampered_candidate_snapshot() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].candidate_input_snapshot["target_roles"] = ["tampered role"]

    with pytest.raises(ValueError, match="Candidate snapshot fingerprint"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_tampered_persisted_result_field() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].skill_fit_score = 0.123456

    with pytest.raises(ValueError, match="result fingerprint"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_tampered_persisted_diagnostics() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].feature_diagnostics["location_relation"] = "mismatch"

    with pytest.raises(ValueError, match="result fingerprint"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_unsupported_diagnostics_contract_version() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].feature_diagnostics_contract_version = (
        "selected_feature_diagnostics_v2"
    )
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="diagnostics contract version"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_unsupported_embedded_diagnostics_contract_version() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].feature_diagnostics["contract_version"] = (
        "selected_feature_diagnostics_v2"
    )
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="diagnostics contract version"):
        module.EvidenceBundleBuilder().build(run)


@pytest.mark.parametrize(
    "field",
    [
        "contract_version",
        "availability",
        "matched_must_have_requirement_ids",
        "weak_matched_must_have_requirement_ids",
        "missing_must_have_requirement_ids",
        "matched_nice_to_have_requirement_ids",
        "evidence_supported_requirement_ids",
        "matched_capabilities",
        "matched_evidence_skills",
        "matched_ai_tools",
        "location_relation",
        "seniority_relation",
        "overclaim_level",
        "overclaim_reason_count",
        "retrieval_rank",
        "dense_rank",
        "sparse_rank",
        "fusion_score",
    ],
)
def test_bundle_rejects_missing_frozen_diagnostics_field(field: str) -> None:
    module = _engine_module()
    run = _run()
    run.results[0].feature_diagnostics.pop(field)
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="diagnostics payload"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_extra_frozen_diagnostics_field() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].feature_diagnostics["future_metadata"] = "not approved"
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="diagnostics payload"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_contradictory_requirement_status_diagnostics() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].feature_diagnostics["missing_must_have_requirement_ids"] = [
        "req_python"
    ]
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="contradictory"):
        module.EvidenceBundleBuilder().build(run)


@pytest.mark.parametrize("target", ["ranking_record", "ranking_snapshot", "candidate_record", "candidate_snapshot"])
def test_bundle_rejects_unsupported_snapshot_contract_version(target: str) -> None:
    module = _engine_module()
    run = _run()
    if target == "ranking_record":
        run.ranking_input_contract_version = "ranking_input_snapshot_v2"
    elif target == "ranking_snapshot":
        run.ranking_input_snapshot["contract_version"] = "ranking_input_snapshot_v2"
        _refresh_ranking_snapshot_fingerprint(run)
    elif target == "candidate_record":
        run.results[0].candidate_input_contract_version = "candidate_input_snapshot_v2"
    else:
        run.results[0].candidate_input_snapshot["contract_version"] = "candidate_input_snapshot_v2"
        _refresh_candidate_snapshot_fingerprint(run.results[0])
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="contract version"):
        module.EvidenceBundleBuilder().build(run)


def test_normalized_skill_variants_have_one_evidence_identity_and_fingerprint() -> None:
    module = _engine_module()
    evidence_ids = set()
    audit_fingerprints = set()
    normalized_content_fingerprints = set()
    for label in ("Python", "python", "PYTHON", " python "):
        run = _run()
        snapshot = run.results[0].candidate_input_snapshot
        snapshot["skills"][0]["name"] = label
        snapshot["projects"][0]["technologies"] = [label]
        snapshot["projects"][0]["skills_demonstrated"] = [label]
        snapshot["project_evidence"][0]["supports_skills"] = [label]
        _refresh_candidate_snapshot_fingerprint(run.results[0])
        _refresh_result_fingerprint(run)

        bundle = module.EvidenceBundleBuilder().build(run)
        evidence_ids.add(bundle.candidates[0].skills[0].evidence_id)
        audit_fingerprints.add(evidence_bundle_fingerprint(bundle))
        normalized_content_fingerprints.add(
            module.evidence_content_fingerprint(bundle)
        )
        assert (
            module.build_evidence_facts(bundle).normalized_content_fingerprint
            == module.evidence_content_fingerprint(bundle)
        )

    assert len(evidence_ids) == 1
    assert len(audit_fingerprints) == 4
    assert len(normalized_content_fingerprints) == 1


def test_bundle_rejects_unknown_diagnostic_requirement_reference() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].feature_diagnostics["matched_must_have_requirement_ids"] = [
        "req_not_in_job"
    ]
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="unknown historical Job requirement"):
        module.EvidenceBundleBuilder().build(run)


def test_bundle_rejects_duplicate_diagnostic_requirement_reference() -> None:
    module = _engine_module()
    run = _run()
    run.results[0].feature_diagnostics["matched_must_have_requirement_ids"] = [
        "req_python",
        "req_python",
    ]
    _refresh_result_fingerprint(run)

    with pytest.raises(ValueError, match="duplicate requirement"):
        module.EvidenceBundleBuilder().build(run)


def test_diagnostic_requirement_order_does_not_change_normalized_content() -> None:
    module = _engine_module()
    first = _run()
    second = _run()
    first.results[0].feature_diagnostics["matched_must_have_requirement_ids"] = [
        "req_python",
        "req_missing",
    ]
    second.results[0].feature_diagnostics["matched_must_have_requirement_ids"] = [
        "req_missing",
        "req_python",
    ]
    _refresh_result_fingerprint(first)
    _refresh_result_fingerprint(second)

    first_bundle = module.EvidenceBundleBuilder().build(first)
    second_bundle = module.EvidenceBundleBuilder().build(second)
    assert first_bundle.job == second_bundle.job
    assert first_bundle.candidates == second_bundle.candidates
    assert module.evidence_content_fingerprint(
        first_bundle
    ) == module.evidence_content_fingerprint(
        second_bundle
    )


@pytest.mark.parametrize("invalid_rank", ["1", 1.0, 1.5, True])
def test_evidence_fact_candidate_rank_is_strict_integer(invalid_rank) -> None:
    module = _engine_module()
    with pytest.raises(ValidationError):
        module.CandidateFactSet.model_validate(
            {
                "candidate_id": "candidate_001",
                "result_rank": invalid_rank,
                "match_reasons": [],
                "ranking_context": [],
                "risks": [],
                "missing_requirements": [],
                "comparison": None,
            }
        )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered"])
def test_evidence_fact_candidates_must_exactly_match_bundle(mutation: str) -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    payload = module.build_evidence_facts(bundle).model_dump(mode="json")
    if mutation == "missing":
        payload["candidates"] = payload["candidates"][:1]
    elif mutation == "duplicate":
        payload["candidates"] = [
            payload["candidates"][0],
            deepcopy(payload["candidates"][0]),
        ]
    else:
        payload["candidates"].reverse()

    with pytest.raises((ValueError, ValidationError), match="Candidate|candidate|rank"):
        facts = module.EvidenceFactsV1.model_validate(payload)
        module.validate_evidence_facts(bundle, facts)


def test_reason_contract_rejects_unapproved_statement_key() -> None:
    module = _engine_module()
    with pytest.raises(ValidationError):
        module.MatchReasonFact.model_validate(
            {
                "category": "skill_fit",
                "statement_key": "personality_verified",
                "evidence_refs": ["feature:1:skill_fit_score"],
            }
        )


def test_comparison_contract_rejects_unapproved_dimension() -> None:
    from app.services.explanation.evidence.contracts import ComparisonItem

    with pytest.raises(ValidationError):
        ComparisonItem.model_validate(
            {
                "dimension": "hiring_probability",
                "direction": "higher",
                "evidence_refs": ["ranking:2:ltr_rank"],
            }
        )


def test_fact_validation_rejects_skill_reason_using_seniority_feature() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.build_evidence_facts(bundle)
    skill_reason = next(
        item for item in facts.candidates[0].match_reasons if item.category == "skill_fit"
    )
    skill_reason.evidence_refs = ["feature:1:seniority_score"]

    with pytest.raises(ValueError, match="incompatible|semantic evidence mapping"):
        module.validate_evidence_facts(bundle, facts)


def test_fact_validation_rejects_skill_reason_using_skill_fit_feature() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.build_evidence_facts(bundle)
    skill_reason = next(
        item for item in facts.candidates[0].match_reasons if item.category == "skill_fit"
    )
    skill_reason.evidence_refs = ["feature:1:skill_fit_score"]

    with pytest.raises(ValueError, match="incompatible|semantic evidence mapping"):
        module.validate_evidence_facts(bundle, facts)


def test_ranking_context_accepts_recorded_feature_reference() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.build_evidence_facts(bundle)

    context = next(
        item
        for item in facts.candidates[0].ranking_context
        if item.dimension == "skill_fit_score"
    )
    assert context.evidence_refs == ["feature:1:skill_fit_score"]
    module.validate_evidence_facts(bundle, facts)


def test_skill_reason_uses_only_source_evidence_kinds() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.build_evidence_facts(bundle)
    skill_reason = next(
        item for item in facts.candidates[0].match_reasons if item.category == "skill_fit"
    )

    assert skill_reason.evidence_refs
    assert all(
        ref.startswith(("candidate:1:skill:", "candidate:1:project:", "job_requirement:"))
        for ref in skill_reason.evidence_refs
    )
    assert any(ref.startswith("candidate:1:") for ref in skill_reason.evidence_refs)
    assert any(ref.startswith("job_requirement:") for ref in skill_reason.evidence_refs)


def test_job_requirement_only_cannot_create_skill_fit_reason() -> None:
    module = _engine_module()
    run = _run()
    snapshot = run.results[0].candidate_input_snapshot
    snapshot["skills"] = []
    snapshot["projects"] = []
    snapshot["project_evidence"] = []
    diagnostics = run.results[0].feature_diagnostics
    diagnostics["matched_capabilities"] = []
    diagnostics["matched_evidence_skills"] = []
    _refresh_candidate_snapshot_fingerprint(run.results[0])
    _refresh_result_fingerprint(run)

    facts = module.build_evidence_facts(module.EvidenceBundleBuilder().build(run))

    assert not any(
        item.category == "skill_fit" for item in facts.candidates[0].match_reasons
    )


def test_candidate_evidence_only_cannot_create_skill_fit_reason() -> None:
    module = _engine_module()
    run = _run()
    diagnostics = run.results[0].feature_diagnostics
    diagnostics["matched_must_have_requirement_ids"] = []
    diagnostics["matched_nice_to_have_requirement_ids"] = []
    diagnostics["missing_must_have_requirement_ids"] = ["req_python"]
    _refresh_result_fingerprint(run)

    facts = module.build_evidence_facts(module.EvidenceBundleBuilder().build(run))

    assert not any(
        item.category == "skill_fit" for item in facts.candidates[0].match_reasons
    )


@pytest.mark.parametrize("side", ["candidate", "job"])
def test_skill_fit_validation_requires_candidate_and_job_evidence(side: str) -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.build_evidence_facts(bundle)
    reason = next(
        item for item in facts.candidates[0].match_reasons if item.category == "skill_fit"
    )
    if side == "candidate":
        reason.evidence_refs = [
            ref for ref in reason.evidence_refs if ref.startswith("candidate:1:")
        ]
    else:
        reason.evidence_refs = [
            ref for ref in reason.evidence_refs if ref.startswith("job_requirement:")
        ]

    with pytest.raises(ValueError, match="both Candidate and Job"):
        module.validate_evidence_facts(bundle, facts)


def test_skill_fit_reference_limit_deterministically_preserves_both_sides() -> None:
    module = _engine_module()
    labels = ["Python", "Rust", "Go", "Java", "Kotlin", "Scala", "Ruby"]
    observed = []
    for ordered_labels in (labels, list(reversed(labels))):
        run = _run()
        snapshot = run.results[0].candidate_input_snapshot
        snapshot["skills"] = [
            {"name": label, "category": "backend"} for label in ordered_labels
        ]
        diagnostics = run.results[0].feature_diagnostics
        diagnostics["matched_capabilities"] = list(ordered_labels)
        diagnostics["matched_evidence_skills"] = list(ordered_labels)
        _refresh_candidate_snapshot_fingerprint(run.results[0])
        _refresh_result_fingerprint(run)
        facts = module.build_evidence_facts(module.EvidenceBundleBuilder().build(run))
        reason = next(
            item
            for item in facts.candidates[0].match_reasons
            if item.category == "skill_fit"
        )
        observed.append(reason.evidence_refs)

    assert observed[0] == observed[1]
    assert len(observed[0]) == 6
    assert any(ref.startswith("candidate:1:") for ref in observed[0])
    assert any(ref.startswith("job_requirement:") for ref in observed[0])


def test_missing_skill_source_evidence_omits_reason_without_inference() -> None:
    module = _engine_module()
    run = _run()
    snapshot = run.results[0].candidate_input_snapshot
    snapshot["skills"] = []
    snapshot["projects"] = []
    snapshot["project_evidence"] = []
    diagnostics = run.results[0].feature_diagnostics
    diagnostics["matched_must_have_requirement_ids"] = []
    diagnostics["matched_nice_to_have_requirement_ids"] = []
    diagnostics["evidence_supported_requirement_ids"] = []
    diagnostics["matched_capabilities"] = []
    diagnostics["matched_evidence_skills"] = []
    _refresh_candidate_snapshot_fingerprint(run.results[0])
    _refresh_result_fingerprint(run)

    bundle = module.EvidenceBundleBuilder().build(run)
    facts = module.build_evidence_facts(bundle)

    assert not any(
        item.category == "skill_fit" for item in facts.candidates[0].match_reasons
    )
    assert any(
        item.dimension == "skill_fit_score"
        for item in facts.candidates[0].ranking_context
    )


def test_fact_validation_rejects_missing_requirement_status_mutation() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.build_evidence_facts(bundle)
    item = next(
        requirement
        for requirement in facts.candidates[1].missing_requirements
        if requirement.requirement_id == "req_missing"
    )
    item.status = "matched"
    item.evidence_status = "available"

    with pytest.raises(ValueError, match="requirement semantics"):
        module.validate_evidence_facts(bundle, facts)


def test_fact_validation_rejects_missing_risk_using_matched_requirement() -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.build_evidence_facts(bundle)
    risk = next(
        item
        for item in facts.candidates[1].risks
        if item.category == "missing_requirement"
    )
    risk.evidence_refs = ["job_requirement:req_python"]

    with pytest.raises(ValueError, match="risk semantics"):
        module.validate_evidence_facts(bundle, facts)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered"])
def test_fact_validation_requires_exact_canonical_match_reasons(mutation: str) -> None:
    module = _engine_module()
    bundle = module.EvidenceBundleBuilder().build(_run())
    facts = module.build_evidence_facts(bundle)
    reasons = facts.candidates[0].match_reasons
    if mutation == "missing":
        reasons.pop()
    elif mutation == "duplicate":
        reasons.append(deepcopy(reasons[0]))
    else:
        reasons.reverse()

    with pytest.raises(ValueError, match="match reason semantics"):
        module.validate_evidence_facts(bundle, facts)


def test_evidence_facts_artifact_matches_runtime_schema() -> None:
    module = _engine_module()
    expected = module.EvidenceFactsV1.model_json_schema()
    expected.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:peoplematch:evidence_facts_v1",
            "x-contract-version": "evidence_facts_v1",
            "x-runtime-model": (
                "app.services.explanation.evidence.contracts.EvidenceFactsV1"
            ),
        }
    )
    actual = json.loads(
        (ROOT / "data" / "contracts" / "evidence_facts_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected
    assert actual["additionalProperties"] is False
