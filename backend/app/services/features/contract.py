from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Final


FEATURE_VERSION: Final = "feature_schema_v1"
NORMALIZER_VERSION: Final = "text_nfkc_casefold_technical_tokens_v2"
MODEL_FEATURE_ORDER: Final = (
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


_FEATURES: Final = (
    {
        "name": "semantic_score",
        "type": "nullable_float",
        "meaning": "Unchanged Phase 4 dense retrieval channel score.",
        "source": "retrieval_result.dense_score",
        "direction": "higher_is_better",
        "valid_range": {"minimum": -1.0, "maximum": 1.0},
        "missing_policy": "null_when_dense_channel_unavailable",
        "formula_version": "phase4_dense_score_passthrough_v1",
        "model_feature": True,
    },
    {
        "name": "sparse_score",
        "type": "nullable_float",
        "meaning": "Unchanged Phase 4 BM25 retrieval channel score.",
        "source": "retrieval_result.sparse_score",
        "direction": "higher_is_better",
        "valid_range": {"minimum": 0.0, "maximum": None},
        "missing_policy": "null_when_sparse_channel_unavailable",
        "formula_version": "phase4_bm25_score_passthrough_v1",
        "model_feature": True,
    },
    {
        "name": "skill_fit_score",
        "type": "nullable_float",
        "meaning": (
            "Fixed-weight coverage of Job skill requirements by Candidate "
            "structured capabilities."
        ),
        "source": "candidate_structured_capabilities_and_job_skill_requirements",
        "direction": "higher_is_better",
        "valid_range": {"minimum": 0.0, "maximum": 1.0},
        "missing_policy": "null_when_job_has_no_skill_requirements",
        "formula_version": "skill_requirement_coverage_v2",
        "model_feature": True,
    },
    {
        "name": "project_evidence_score",
        "type": "nullable_float",
        "meaning": (
            "Fixed-weight coverage of Job skill and project-evidence requirements "
            "by available structured project evidence skills."
        ),
        "source": (
            "candidate_project_evidence.supports_skills_verification_status_and_"
            "job_skill_project_evidence_requirements"
        ),
        "direction": "higher_is_better",
        "valid_range": {"minimum": 0.0, "maximum": 1.0},
        "missing_policy": "null_when_job_has_no_skill_or_project_evidence_requirements",
        "formula_version": "available_evidence_requirement_coverage_v2",
        "model_feature": True,
    },
    {
        "name": "role_direction_score",
        "type": "nullable_float",
        "meaning": "Maximum token-set Jaccard for target role and Job role direction/title.",
        "source": "candidate.target_roles_and_job.role_title_role_direction",
        "direction": "higher_is_better",
        "valid_range": {"minimum": 0.0, "maximum": 1.0},
        "missing_policy": "null_when_either_role_side_unavailable",
        "formula_version": "role_token_jaccard_v1",
        "model_feature": True,
    },
    {
        "name": "ai_tool_score",
        "type": "nullable_float",
        "meaning": "Explicit Candidate AI-tool phrase overlap with Job AI-tooling requirements.",
        "source": "candidate.ai_tools_and_job.ai_tooling_requirements",
        "direction": "higher_is_better",
        "valid_range": {"minimum": 0.0, "maximum": 1.0},
        "missing_policy": "null_when_job_has_no_explicit_ai_tooling_requirement",
        "formula_version": "explicit_ai_tool_overlap_v1",
        "model_feature": True,
    },
    {
        "name": "location_score",
        "type": "nullable_float",
        "meaning": "Exact normalized overlap between preferred and Job cities.",
        "source": "candidate.preferred_locations.cities_and_job.location.cities",
        "direction": "higher_is_better",
        "valid_range": {"minimum": 0.0, "maximum": 1.0},
        "missing_policy": "null_when_either_location_side_unavailable",
        "formula_version": "exact_city_overlap_v1",
        "model_feature": True,
    },
    {
        "name": "seniority_score",
        "type": "nullable_float",
        "meaning": "Exact canonical Candidate seniority membership in Job requirements.",
        "source": "candidate.seniority_and_job.seniority_requirement",
        "direction": "higher_is_better",
        "valid_range": {"minimum": 0.0, "maximum": 1.0},
        "missing_policy": "null_when_either_seniority_side_unavailable",
        "formula_version": "exact_seniority_match_v1",
        "model_feature": True,
    },
    {
        "name": "missing_penalty",
        "type": "nullable_float",
        "meaning": "Mean uncovered share of Job must-have skill requirements.",
        "source": "candidate_structured_capabilities_and_job.must_have_skill_requirements",
        "direction": "higher_is_worse",
        "valid_range": {"minimum": 0.0, "maximum": 1.0},
        "missing_policy": "null_when_job_has_no_must_have_skill_requirements",
        "formula_version": "mean_missing_skill_must_have_v2",
        "model_feature": True,
    },
    {
        "name": "overclaim_penalty",
        "type": "nullable_float",
        "meaning": "Deterministic normalization of the existing ordered overclaim level.",
        "source": "candidate.overclaim_risk.level",
        "direction": "higher_is_worse",
        "valid_range": {"minimum": 0.0, "maximum": 1.0},
        "missing_policy": "null_when_overclaim_level_unavailable_or_invalid",
        "formula_version": "ordered_risk_level_low0_medium05_high1_v1",
        "model_feature": True,
    },
)


def _payload() -> dict[str, Any]:
    return {
        "feature_version": FEATURE_VERSION,
        "model_feature_order": list(MODEL_FEATURE_ORDER),
        "normalizer_version": NORMALIZER_VERSION,
        "source_policy": {
            "candidate": [
                "skills.name",
                "skills.category",
                "projects.technologies",
                "projects.skills_demonstrated",
                "project_evidence.supports_skills",
                "project_evidence.verification_status",
                "project_evidence.evidence_type",
                "target_roles",
                "ai_tools",
                "preferred_locations.cities",
                "seniority",
                "overclaim_risk.level",
            ],
            "job": [
                "role_title",
                "role_direction",
                "must_have.text_category_evidence_expectation",
                "nice_to_have.text_category_evidence_expectation",
                "evaluation_focus",
                "location.cities",
                "seniority_requirement",
            ],
            "retrieval": ["dense_score", "sparse_score"],
        },
        "features": deepcopy(list(_FEATURES)),
    }


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_feature_contract() -> dict[str, Any]:
    payload = _payload()
    fingerprint = hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    return {**payload, "feature_fingerprint": fingerprint}


FEATURE_FINGERPRINT: Final = build_feature_contract()["feature_fingerprint"]
