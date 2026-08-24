from __future__ import annotations

import re
from typing import Any

from app.schemas.explanations import EvidenceFactKind
from app.services.explanation.evidence.normalization import canonicalize_labels


_REQUIREMENT_LIST_NAMES = (
    "matched_must_have_requirement_ids",
    "weak_matched_must_have_requirement_ids",
    "missing_must_have_requirement_ids",
    "matched_nice_to_have_requirement_ids",
    "evidence_supported_requirement_ids",
)
_RELATION_NAMES = ("location_relation", "seniority_relation")
_LABEL_LIST_NAMES = (
    "matched_capabilities",
    "matched_evidence_skills",
    "matched_ai_tools",
)
_REQUIREMENT_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def requirement_evidence_id(requirement_id: str) -> str:
    return f"job_requirement:{requirement_id}"


def _fact(evidence_id: str, candidate_id: str, name: str, value: Any) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "kind": EvidenceFactKind.DIAGNOSTIC.value,
        "candidate_id": candidate_id,
        "name": name,
        "value": value,
    }


def build_diagnostic_facts(
    result, *, historical_requirement_ids: set[str]
) -> list[dict[str, Any]]:
    diagnostics = result.feature_diagnostics or {}
    candidate_id = result.candidate_id
    rank = result.result_rank
    facts: list[dict[str, Any]] = []
    for name in _REQUIREMENT_LIST_NAMES:
        values = diagnostics.get(name)
        if values is None:
            continue
        if not isinstance(values, list):
            raise ValueError(f"{name} diagnostic must be a list")
        if any(
            not isinstance(value, str) or _REQUIREMENT_ID.fullmatch(value) is None
            for value in values
        ):
            raise ValueError(f"{name} contains an invalid requirement namespace")
        if len(values) != len(set(values)):
            raise ValueError(f"{name} contains a duplicate requirement reference")
        unknown = set(values) - historical_requirement_ids
        if unknown:
            raise ValueError(
                f"{name} references an unknown historical Job requirement"
            )
        facts.append(
            _fact(
                f"diagnostic:{rank}:{name}",
                candidate_id,
                name,
                sorted(requirement_evidence_id(value) for value in values),
            )
        )
    for name in _RELATION_NAMES:
        value = diagnostics.get(name)
        if value is not None:
            facts.append(_fact(f"diagnostic:{rank}:{name}", candidate_id, name, value))
    for name in _LABEL_LIST_NAMES:
        values = diagnostics.get(name)
        if values is not None:
            if not isinstance(values, list):
                raise ValueError(f"{name} diagnostic must be a list")
            facts.append(
                _fact(
                    f"diagnostic:{rank}:{name}",
                    candidate_id,
                    name,
                    canonicalize_labels(values, name),
                )
            )
    if diagnostics.get("overclaim_level") is not None:
        facts.append(
            _fact(
                f"diagnostic:{rank}:overclaim_level",
                candidate_id,
                "overclaim_level",
                diagnostics["overclaim_level"],
            )
        )
    if diagnostics.get("overclaim_reason_count") is not None:
        facts.append(
            _fact(
                f"diagnostic:{rank}:overclaim_reason_count",
                candidate_id,
                "overclaim_reason_count",
                diagnostics["overclaim_reason_count"],
            )
        )
    return facts


__all__ = ["build_diagnostic_facts", "requirement_evidence_id"]
