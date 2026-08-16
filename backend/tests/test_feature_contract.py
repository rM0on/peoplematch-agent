from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_feature_contract_has_stable_version_order_and_fingerprint() -> None:
    from app.services.features.contract import (
        FEATURE_FINGERPRINT,
        FEATURE_VERSION,
        MODEL_FEATURE_ORDER,
        build_feature_contract,
    )

    assert FEATURE_VERSION == "feature_schema_v1"
    assert MODEL_FEATURE_ORDER == (
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
    assert FEATURE_FINGERPRINT == (
        "dc85c7237c6c67785199d221c919ae48c31c9a6323857070e6399d3eae365e42"
    )
    assert FEATURE_FINGERPRINT == build_feature_contract()["feature_fingerprint"]
    assert FEATURE_FINGERPRINT == build_feature_contract()["feature_fingerprint"]


def test_checked_in_contract_artifact_equals_generated_contract() -> None:
    from app.services.features.contract import build_feature_contract

    artifact = json.loads(
        (ROOT / "data/eval/phase5/feature_contract_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact == build_feature_contract()


def test_only_registered_values_are_model_features() -> None:
    from app.services.features.contract import MODEL_FEATURE_ORDER, build_feature_contract

    contract = build_feature_contract()
    assert tuple(item["name"] for item in contract["features"]) == MODEL_FEATURE_ORDER
    serialized = json.dumps(contract, sort_keys=True)
    for forbidden in (
        "candidate_id",
        "job_id",
        "retrieval_rank",
        "dense_rank",
        "sparse_rank",
        "fusion_score",
        "relevance_grade",
        "split",
    ):
        assert forbidden not in serialized


def test_generated_contract_is_isolated_from_caller_mutation() -> None:
    from app.services.features.contract import FEATURE_FINGERPRINT, build_feature_contract

    mutated = build_feature_contract()
    mutated["features"][0]["valid_range"]["minimum"] = -99
    regenerated = build_feature_contract()

    assert regenerated["features"][0]["valid_range"]["minimum"] == -1.0
    assert regenerated["feature_fingerprint"] == FEATURE_FINGERPRINT


def test_feature_vector_field_order_is_exactly_the_model_contract() -> None:
    from app.schemas.features import FeatureVector
    from app.services.features.contract import MODEL_FEATURE_ORDER

    assert tuple(FeatureVector.model_fields) == MODEL_FEATURE_ORDER


def test_contract_records_verified_evidence_and_feature_category_policies() -> None:
    from app.services.features.contract import build_feature_contract

    contract = build_feature_contract()
    definitions = {item["name"]: item for item in contract["features"]}

    assert "project_evidence.verification_status" in contract["source_policy"][
        "candidate"
    ]
    assert definitions["skill_fit_score"]["formula_version"] == (
        "skill_requirement_coverage_v2"
    )
    assert definitions["project_evidence_score"]["formula_version"] == (
        "available_evidence_requirement_coverage_v2"
    )
    assert definitions["missing_penalty"]["formula_version"] == (
        "mean_missing_skill_must_have_v2"
    )
    assert "available" in definitions["project_evidence_score"]["meaning"].casefold()
    assert "skill" in definitions["missing_penalty"]["meaning"].casefold()
