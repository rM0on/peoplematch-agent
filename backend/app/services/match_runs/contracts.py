from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import Any

from app.schemas.match_runs import RankingVariant
from app.schemas.persistence import CandidateRecord, JobRecord
from app.services.cross_encoder.contract import (
    PAIR_ORDER,
    RERANKER_VERSION,
    SCORE_DIRECTION,
    SCORE_TYPE,
    TEXT_CONTRACT_FINGERPRINT,
    TEXT_SCHEMA_VERSION,
)
from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION
from app.services.ranking.contract import RANKER_VERSION
from app.services.retrieval.documents import RETRIEVAL_DOCUMENT_VERSION


WORKFLOW_VERSION = "match_run_workflow_v1"
RANKING_INPUT_CONTRACT_VERSION = "ranking_input_snapshot_v1"
CANDIDATE_INPUT_CONTRACT_VERSION = "candidate_input_snapshot_v1"
DIAGNOSTICS_CONTRACT_VERSION = "selected_feature_diagnostics_v1"
STEP_REFS_CONTRACT_VERSION = "match_run_step_refs_v1"
RETRIEVAL_CONFIGURATION_FINGERPRINT = (
    "b004bc52c33f3e15bf38dba1777305039909bb5229261dcf1851b289e7c8f2e7"
)
RANKER_MODEL_SHA256 = (
    "c8f235ebd95dce611f892394859f9f0251f43f8822a39bd316c404d9ff75a000"
)
CE_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L6-v2"
CE_MODEL_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
CE_SNAPSHOT_FINGERPRINT = (
    "013355448b38f6190a4d7250b1d062f76caddd8a5f1cabc47bdc716490a60236"
)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return _canonicalize(value.value)
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("fingerprint values must be finite")
        normalized = 0.0 if value == 0 else value
        return {"$float64": format(normalized, ".17g")}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported fingerprint value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _load_workflow_contract() -> tuple[dict[str, Any], str]:
    source = Path(__file__).resolve()
    candidates = (
        source.parents[4] / "data" / "contracts" / "match_run_workflow_v1.json",
        source.parents[3] / "data" / "contracts" / "match_run_workflow_v1.json",
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Phase 8 workflow contract is unavailable") from error
    if not isinstance(artifact, dict):
        raise RuntimeError("Phase 8 workflow contract must be an object")
    declared = artifact.pop("workflow_fingerprint", None)
    if not isinstance(declared, str) or canonical_fingerprint(artifact) != declared:
        raise RuntimeError("Phase 8 workflow contract fingerprint mismatch")
    if artifact.get("workflow_version") != WORKFLOW_VERSION:
        raise RuntimeError("Phase 8 workflow version mismatch")
    expected_required = {
        "retrieval_document_version": RETRIEVAL_DOCUMENT_VERSION,
        "retrieval_configuration_fingerprint": RETRIEVAL_CONFIGURATION_FINGERPRINT,
        "feature_version": FEATURE_VERSION,
        "feature_fingerprint": FEATURE_FINGERPRINT,
        "ranker_version": RANKER_VERSION,
    }
    expected_ce = {
        "reranker_version": RERANKER_VERSION,
        "text_schema_version": TEXT_SCHEMA_VERSION,
        "text_contract_fingerprint": TEXT_CONTRACT_FINGERPRINT,
        "pair_order": PAIR_ORDER,
        "score_type": SCORE_TYPE,
        "score_direction": SCORE_DIRECTION,
        "calibration": False,
    }
    if artifact.get("required_provenance") != expected_required:
        raise RuntimeError("Phase 8 required provenance contract mismatch")
    if artifact.get("cross_encoder_provenance") != expected_ce:
        raise RuntimeError("Phase 8 CE provenance contract mismatch")
    return artifact, declared


WORKFLOW_CONTRACT, WORKFLOW_FINGERPRINT = _load_workflow_contract()


def workflow_contract() -> dict[str, Any]:
    payload = deepcopy(WORKFLOW_CONTRACT)
    payload["workflow_fingerprint"] = WORKFLOW_FINGERPRINT
    return payload


def workflow_steps(variant: RankingVariant) -> tuple[str, ...]:
    return tuple(WORKFLOW_CONTRACT["variants"][variant.value]["steps"])


def _enum(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def build_candidate_input_snapshot(record: CandidateRecord) -> dict[str, Any]:
    return {
        "contract_version": CANDIDATE_INPUT_CONTRACT_VERSION,
        "candidate_id": record.candidate_id,
        "target_roles": list(record.target_roles),
        "skills": [
            {"name": skill.name, "category": _enum(skill.category)}
            for skill in record.skills
        ],
        "projects": [
            {
                "project_id": project.project_id,
                "technologies": list(project.technologies),
                "skills_demonstrated": list(project.skills_demonstrated),
            }
            for project in record.projects
        ],
        "project_evidence": [
            {
                "evidence_id": evidence.evidence_id,
                "project_id": evidence.project_id,
                "supports_skills": list(evidence.supports_skills),
                "verification_status": _enum(evidence.verification_status),
                "evidence_type": _enum(evidence.evidence_type),
            }
            for evidence in record.project_evidence
        ],
        "ai_tools": list(record.ai_tools),
        "preferred_locations": {
            "cities": list(record.preferred_locations.cities),
            "remote_policy": _enum(record.preferred_locations.remote_policy),
            "relocation_open": record.preferred_locations.relocation_open,
        },
        "seniority": _enum(record.seniority),
        "team_stage_preference": list(record.work_style.team_stage_preference),
        "overclaim_risk": {
            "level": _enum(record.overclaim_risk.level),
            "reason_count": len(record.overclaim_risk.reasons),
        },
    }


def build_job_input_snapshot(record: JobRecord) -> dict[str, Any]:
    def requirement(item: Any) -> dict[str, Any]:
        return {
            "requirement_id": item.requirement_id,
            "category": _enum(item.category),
            "text": item.text,
            "evidence_expectation": item.evidence_expectation,
        }

    return {
        "contract_version": RANKING_INPUT_CONTRACT_VERSION,
        "job_id": record.job_id,
        "role_title": record.role_title,
        "role_direction": list(record.role_direction),
        "must_have": [requirement(item) for item in record.must_have],
        "nice_to_have": [requirement(item) for item in record.nice_to_have],
        "location": {
            "cities": list(record.location.cities),
            "remote_policy": _enum(record.location.remote_policy),
            "relocation_supported": record.location.relocation_supported,
        },
        "seniority_requirement": [_enum(item) for item in record.seniority_requirement],
        "product_stage": _enum(record.product_stage),
    }


def selected_feature_diagnostics(value: Any) -> dict[str, Any]:
    return {
        "contract_version": DIAGNOSTICS_CONTRACT_VERSION,
        "availability": value.availability.model_dump(mode="json"),
        "matched_must_have_requirement_ids": list(
            value.matched_must_have_requirement_ids
        ),
        "weak_matched_must_have_requirement_ids": list(
            value.weak_matched_must_have_requirement_ids
        ),
        "missing_must_have_requirement_ids": list(
            value.missing_must_have_requirement_ids
        ),
        "matched_nice_to_have_requirement_ids": list(
            value.matched_nice_to_have_requirement_ids
        ),
        "evidence_supported_requirement_ids": list(
            value.evidence_supported_requirement_ids
        ),
        "matched_capabilities": list(value.matched_capabilities),
        "matched_evidence_skills": list(value.matched_evidence_skills),
        "matched_ai_tools": list(value.matched_ai_tools),
        "location_relation": value.location_relation,
        "seniority_relation": value.seniority_relation,
        "overclaim_level": value.overclaim_level,
        "overclaim_reason_count": value.overclaim_reason_count,
        "retrieval_rank": value.retrieval_rank,
        "dense_rank": value.dense_rank,
        "sparse_rank": value.sparse_rank,
        "fusion_score": value.fusion_score,
    }
