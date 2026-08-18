from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


TEXT_SCHEMA_VERSION = "cross_encoder_text_v1"
MODEL_CONTRACT_VERSION = "cross_encoder_model_manifest_v1"
MODEL_ID = "cross-encoder/ms-marco-MiniLM-L6-v2"
MODEL_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
MODEL_LICENSE = "apache-2.0"
MODEL_TYPE = "bert"
RERANKER_VERSION = "cross_encoder_reranker_v1"
PAIR_ORDER = "job_then_candidate"
SCORE_TYPE = "raw_logit"
SCORE_DIRECTION = "higher_is_better"
MAX_LENGTH = 512
DEFAULT_BATCH_SIZE = 10


# This is the source-of-truth description for the serialized text contract.
# It intentionally contains no dataset rows, labels, IDs, or model scores.
TEXT_CONTRACT_POLICY: dict[str, Any] = {
    "text_schema_version": TEXT_SCHEMA_VERSION,
    "pair_order": PAIR_ORDER,
    "normalization": {
        "unicode": "NFKC",
        "strip": True,
        "collapse_internal_whitespace": True,
        "value_order": "canonical_source_order",
        "deduplication": "first_occurrence_within_section",
    },
    "section_separator": "\\n",
    "value_separator": " | ",
    "candidate_sections": [
        {"label": "TARGET ROLES", "source": ["target_roles"]},
        {"label": "SKILLS", "source": ["skills.name"]},
        {"label": "PROJECT TECHNOLOGIES", "source": ["projects.technologies"]},
        {
            "label": "PROJECT-CLAIMED SKILLS",
            "source": ["projects.skills_demonstrated"],
        },
        {
            "label": "VERIFIED EVIDENCE SKILLS",
            "source": [
                "project_evidence.supports_skills",
                "verification_status=available",
            ],
        },
        {"label": "AI TOOLS", "source": ["ai_tools"]},
        {
            "label": "LOCATION",
            "source": [
                "preferred_locations.cities",
                "preferred_locations.remote_policy",
                "preferred_locations.relocation_open",
            ],
        },
        {"label": "SENIORITY", "source": ["seniority"]},
        {
            "label": "WORK STYLE",
            "source": ["work_style.team_stage_preference"],
        },
    ],
    "job_sections": [
        {"label": "ROLE TITLE", "source": ["role_title"]},
        {"label": "ROLE DIRECTION", "source": ["role_direction"]},
        {
            "label": "MUST HAVE",
            "source": ["must_have.category", "must_have.text"],
            "category_policy": "canonical_requirement_category_value",
        },
        {
            "label": "NICE TO HAVE",
            "source": ["nice_to_have.category", "nice_to_have.text"],
            "category_policy": "canonical_requirement_category_value",
        },
        {
            "label": "LOCATION",
            "source": [
                "location.cities",
                "location.remote_policy",
                "location.relocation_supported",
            ],
        },
        {"label": "SENIORITY", "source": ["seniority_requirement"]},
        {"label": "PRODUCT STAGE", "source": ["product_stage"]},
    ],
    "excluded_candidate_fields": [
        "candidate_id",
        "name",
        "archetype",
        "raw_text",
        "github_url",
        "project_id",
        "project.name",
        "project.summary",
        "project.role",
        "project.outcomes",
        "project_evidence.evidence_id",
        "project_evidence.statement",
        "project_evidence.project_id",
        "project_evidence.artifact_ref",
        "project_evidence.evidence_type",
        "project_evidence.verification_status",
        "described_evidence",
        "missing_evidence",
        "missing_fields",
        "overclaim_risk",
        "data_origin",
        "schema_version",
        "dataset_version",
        "split",
        "labels",
        "pairwise_preferences",
        "hard_negative_metadata",
    ],
    "excluded_job_fields": [
        "job_id",
        "company_name",
        "archetype",
        "raw_jd",
        "requirement_id",
        "evidence_expectation",
        "team_tags",
        "evaluation_focus",
        "data_origin",
        "schema_version",
        "dataset_version",
        "split",
        "labels",
        "pairwise_preferences",
        "hard_negative_metadata",
    ],
    "score_policy": {
        "score_type": SCORE_TYPE,
        "score_direction": SCORE_DIRECTION,
        "activation": "identity",
        "calibration": False,
    },
}


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def text_contract_fingerprint(payload: dict[str, Any] | None = None) -> str:
    value = TEXT_CONTRACT_POLICY if payload is None else payload
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


TEXT_CONTRACT_FINGERPRINT = text_contract_fingerprint()


def text_contract_payload() -> dict[str, Any]:
    payload = deepcopy(TEXT_CONTRACT_POLICY)
    payload["text_contract_fingerprint"] = TEXT_CONTRACT_FINGERPRINT
    return payload
