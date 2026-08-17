from __future__ import annotations

import lightgbm


EXPECTED_FEATURE_ORDER = (
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


def test_ranker_contract_is_bound_to_frozen_phase5_and_lightgbm() -> None:
    from app.services.ranking.contract import (
        LABEL_GAIN,
        LIGHTGBM_VERSION,
        OBJECTIVE,
        RANKER_VERSION,
        TRAINING_PARAMETERS,
        build_ranker_contract,
    )

    contract = build_ranker_contract("dataset-fingerprint")

    assert RANKER_VERSION == "ltr_ranker_v1"
    assert LIGHTGBM_VERSION == "4.6.0" == lightgbm.__version__
    assert OBJECTIVE == "lambdarank"
    assert LABEL_GAIN == (0, 1, 3, 7)
    assert tuple(contract["model_feature_order"]) == EXPECTED_FEATURE_ORDER
    assert contract["feature_version"] == "feature_schema_v1"
    assert contract["feature_fingerprint"] == (
        "dc85c7237c6c67785199d221c919ae48c31c9a6323857070e6399d3eae365e42"
    )
    assert contract["ltr_dataset_fingerprint"] == "dataset-fingerprint"
    assert TRAINING_PARAMETERS["objective"] == "lambdarank"
    assert TRAINING_PARAMETERS["label_gain"] == [0, 1, 3, 7]
    assert TRAINING_PARAMETERS["deterministic"] is True
    assert TRAINING_PARAMETERS["force_row_wise"] is True
    assert TRAINING_PARAMETERS["num_threads"] == 1


def test_ranker_contract_state_is_not_mutated_by_callers() -> None:
    from app.services.ranking.contract import build_ranker_contract

    first = build_ranker_contract("first")
    first["model_feature_order"].reverse()
    first["training_parameters"]["seed"] = 999
    second = build_ranker_contract("second")

    assert tuple(second["model_feature_order"]) == EXPECTED_FEATURE_ORDER
    assert second["training_parameters"]["seed"] == 42


def test_ranking_request_enforces_pool_contract_and_is_hybrid_only() -> None:
    from pydantic import ValidationError
    import pytest

    from app.schemas.ranking import RankingRequest

    request = RankingRequest(candidate_pool_k=20, top_k=10)
    assert request.candidate_pool_k == 20
    assert request.top_k == 10
    assert not hasattr(request, "strategy")

    for payload in (
        {"candidate_pool_k": 0, "top_k": 1},
        {"candidate_pool_k": 51, "top_k": 1},
        {"candidate_pool_k": 10, "top_k": 11},
        {"strategy": "dense"},
    ):
        with pytest.raises(ValidationError):
            RankingRequest.model_validate(payload)
