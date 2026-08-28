from __future__ import annotations


_RANKING_SYMPTOMS = {
    ("wrong", "wrong_top1"): "wrong_top1",
    ("wrong", "ranking_inversion"): "ranking_inversion",
    ("wrong", "false_positive"): "false_positive",
    ("wrong", "false_negative"): "expected_candidate_not_recalled",
    ("wrong", "constraint_conflict"): "constraint_conflict",
    ("wrong", "evidence_coverage_disagreement"): "requirement_coverage_disagreement",
    ("uncertain", None): "uncertain_order",
    ("insufficient_evidence", None): "uncertain_order",
}

_EXPLANATION_SYMPTOMS = {
    "unsupported": "unsupported_explanation",
    "misleading": "misleading_explanation",
    "incomplete": "incomplete_explanation",
}

_PROFILE_SYMPTOMS = {
    "candidate_profile": "candidate_snapshot_issue",
    "job_profile": "job_snapshot_issue",
}

_SYSTEM_SIGNAL_SYMPTOMS = {
    "snapshot_fingerprint_mismatch": "history_integrity_failure",
    "result_fingerprint_mismatch": "history_integrity_failure",
    "cross_owner_reference": "ownership_failure",
    "terminal_lifecycle_violation": "lifecycle_failure",
    "explanation_grounding_failure": "history_integrity_failure",
    "attempt_audit_mismatch": "provider_attempt_failure",
}

_ROOT_CAUSE_EVIDENCE = {
    "ranking": frozenset({"ranking", "comparison"}),
    "feature": frozenset({"feature"}),
    "evidence": frozenset(
        {"job_requirement", "skill", "project", "project_evidence", "diagnostic"}
    ),
    "explanation": frozenset(
        {"job_requirement", "skill", "project", "project_evidence", "diagnostic", "comparison"}
    ),
    "data": frozenset({"field_locator"}),
    "integrity": frozenset({"diagnostic", "ranking", "comparison"}),
}


def symptom_allowed_for_feedback(
    feedback_type: str,
    value: str,
    reason_code: str | None,
    *,
    target_type: str | None = None,
) -> str | None:
    if feedback_type == "ranking":
        return _RANKING_SYMPTOMS.get((value, reason_code))
    if feedback_type == "explanation":
        return _EXPLANATION_SYMPTOMS.get(value)
    if feedback_type == "profile_data":
        return _PROFILE_SYMPTOMS.get(target_type or "")
    return None


def evidence_supports_root_cause(root_cause_code: str, evidence_kind: str) -> bool:
    # Phase 8 does not persist a complete retrieval pool. A retrieval symptom may be
    # recorded, but it cannot be promoted to supported/confirmed retrieval recall.
    if root_cause_code == "retrieval_recall_miss":
        return False
    prefix = root_cause_code.split("_", 1)[0]
    return evidence_kind in _ROOT_CAUSE_EVIDENCE.get(prefix, frozenset())


def symptom_allowed_for_signal(signal_code: str) -> str | None:
    return _SYSTEM_SIGNAL_SYMPTOMS.get(signal_code)


__all__ = [
    "evidence_supports_root_cause",
    "symptom_allowed_for_feedback",
    "symptom_allowed_for_signal",
]
