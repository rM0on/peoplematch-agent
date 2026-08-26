from __future__ import annotations


BAD_CASE_CONTRACT_VERSION = "bad_case_v1"
BAD_CASE_TAXONOMY_VERSION = "bad_case_taxonomy_v1"


_CATEGORY_FAMILIES = {
    "wrong_top1": "RANKING",
    "ranking_inversion": "RANKING",
    "false_positive": "RANKING",
    "false_negative": "RANKING",
    "constraint_conflict": "RANKING",
    "uncertain_order": "RANKING",
    "expected_candidate_not_recalled": "RETRIEVAL",
    "irrelevant_candidate_recalled": "RETRIEVAL",
    "filter_exclusion_disagreement": "RETRIEVAL",
    "pool_truncation_concern": "RETRIEVAL",
    "missing_support": "EVIDENCE",
    "incorrect_support_status": "EVIDENCE",
    "project_skill_link_disagreement": "EVIDENCE",
    "requirement_coverage_disagreement": "EVIDENCE",
    "unsupported_explanation": "EXPLANATION",
    "misleading_explanation": "EXPLANATION",
    "incomplete_explanation": "EXPLANATION",
    "incorrect_gap_statement": "EXPLANATION",
    "incorrect_top1_comparison": "EXPLANATION",
    "candidate_snapshot_issue": "DATA_QUALITY",
    "job_snapshot_issue": "DATA_QUALITY",
    "requirement_issue": "DATA_QUALITY",
    "constraint_issue": "DATA_QUALITY",
    "history_integrity_failure": "INTEGRITY_OPERATIONS",
    "ownership_failure": "INTEGRITY_OPERATIONS",
    "lifecycle_failure": "INTEGRITY_OPERATIONS",
    "provider_attempt_failure": "INTEGRITY_OPERATIONS",
}

_ROOT_CAUSES = {
    "ranking": frozenset(
        {
            "ranking_wrong_top1",
            "ranking_pairwise_inversion",
            "ranking_false_positive",
            "ranking_false_negative",
            "ranking_tie_break_issue",
            "ranking_constraint_policy_issue",
        }
    ),
    "retrieval": frozenset(
        {
            "retrieval_recall_miss",
            "retrieval_filter_exclusion",
            "retrieval_dense_coverage_gap",
            "retrieval_sparse_coverage_gap",
            "retrieval_fusion_issue",
            "retrieval_pool_truncation",
            "retrieval_index_integrity",
        }
    ),
    "feature": frozenset(
        {
            "feature_semantic_score_issue",
            "feature_sparse_score_issue",
            "feature_skill_fit_issue",
            "feature_project_evidence_issue",
            "feature_role_direction_issue",
            "feature_location_issue",
            "feature_seniority_issue",
            "feature_missing_penalty_issue",
            "feature_overclaim_penalty_issue",
            "feature_availability_issue",
        }
    ),
    "evidence": frozenset(
        {
            "evidence_missing_project_support",
            "evidence_status_incorrect",
            "evidence_skill_project_link_incorrect",
            "evidence_requirement_alignment_incorrect",
            "evidence_claim_promoted_without_support",
            "evidence_owner_mismatch",
        }
    ),
    "explanation": frozenset(
        {
            "explanation_unsupported_claim",
            "explanation_misleading_template",
            "explanation_incomplete_selection",
            "explanation_incorrect_gap",
            "explanation_comparison_mismatch",
            "explanation_reference_ownership",
            "explanation_clarity_issue",
        }
    ),
    "data_quality": frozenset(
        {
            "data_candidate_skill_missing",
            "data_candidate_skill_incorrect",
            "data_project_evidence_missing",
            "data_candidate_seniority_incorrect",
            "data_candidate_location_incorrect",
            "data_job_requirement_unclear",
            "data_job_requirement_missing",
            "data_job_requirement_priority_incorrect",
            "data_job_level_incorrect",
            "data_job_expectation_missing",
        }
    ),
    "integrity": frozenset(
        {
            "integrity_snapshot_fingerprint",
            "integrity_result_fingerprint",
            "integrity_cross_owner_reference",
            "integrity_terminal_overwrite",
            "integrity_attempt_audit",
        }
    ),
}

_ACTIONS = {
    "ranking": frozenset(
        {
            "ranking_change_hypothesis",
            "ranking_contract_hypothesis",
            "constraint_policy_hypothesis",
        }
    ),
    "retrieval": frozenset(
        {
            "retrieval_change_hypothesis",
            "filter_policy_hypothesis",
            "fusion_policy_hypothesis",
            "pool_policy_hypothesis",
            "data_integrity_action",
        }
    ),
    "feature": frozenset(
        {"feature_rule_hypothesis", "feature_contract_hypothesis"}
    ),
    "evidence": frozenset(
        {
            "data_correction_proposal",
            "evidence_rule_hypothesis",
            "evidence_integrity_action",
        }
    ),
    "explanation": frozenset(
        {
            "planning_policy_hypothesis",
            "template_change_hypothesis",
            "grounding_integrity_action",
        }
    ),
    "data_quality": frozenset({"data_correction_proposal"}),
    "integrity": frozenset(
        {"integrity_repair_action", "documentation_action"}
    ),
}

_ROOT_CAUSE_ACTIONS = {
    "ranking_wrong_top1": frozenset({"ranking_change_hypothesis"}),
    "ranking_pairwise_inversion": frozenset({"ranking_change_hypothesis"}),
    "ranking_false_positive": frozenset(
        {"ranking_change_hypothesis", "constraint_policy_hypothesis"}
    ),
    "ranking_false_negative": frozenset({"ranking_change_hypothesis"}),
    "ranking_tie_break_issue": frozenset({"ranking_contract_hypothesis"}),
    "ranking_constraint_policy_issue": frozenset(
        {"constraint_policy_hypothesis"}
    ),
    "retrieval_recall_miss": frozenset({"retrieval_change_hypothesis"}),
    "retrieval_filter_exclusion": frozenset({"filter_policy_hypothesis"}),
    "retrieval_dense_coverage_gap": frozenset({"retrieval_change_hypothesis"}),
    "retrieval_sparse_coverage_gap": frozenset({"retrieval_change_hypothesis"}),
    "retrieval_fusion_issue": frozenset({"fusion_policy_hypothesis"}),
    "retrieval_pool_truncation": frozenset({"pool_policy_hypothesis"}),
    "retrieval_index_integrity": frozenset({"data_integrity_action"}),
    "feature_semantic_score_issue": frozenset({"feature_rule_hypothesis"}),
    "feature_sparse_score_issue": frozenset({"feature_rule_hypothesis"}),
    "feature_skill_fit_issue": frozenset({"feature_rule_hypothesis"}),
    "feature_project_evidence_issue": frozenset({"feature_rule_hypothesis"}),
    "feature_role_direction_issue": frozenset({"feature_rule_hypothesis"}),
    "feature_location_issue": frozenset({"feature_rule_hypothesis"}),
    "feature_seniority_issue": frozenset({"feature_rule_hypothesis"}),
    "feature_missing_penalty_issue": frozenset({"feature_rule_hypothesis"}),
    "feature_overclaim_penalty_issue": frozenset({"feature_rule_hypothesis"}),
    "feature_availability_issue": frozenset({"feature_contract_hypothesis"}),
    "evidence_missing_project_support": frozenset({"data_correction_proposal"}),
    "evidence_status_incorrect": frozenset({"evidence_rule_hypothesis"}),
    "evidence_skill_project_link_incorrect": frozenset(
        {"data_correction_proposal", "evidence_rule_hypothesis"}
    ),
    "evidence_requirement_alignment_incorrect": frozenset(
        {"evidence_rule_hypothesis"}
    ),
    "evidence_claim_promoted_without_support": frozenset(
        {"evidence_integrity_action"}
    ),
    "evidence_owner_mismatch": frozenset({"integrity_repair_action"}),
    "explanation_unsupported_claim": frozenset({"grounding_integrity_action"}),
    "explanation_misleading_template": frozenset({"template_change_hypothesis"}),
    "explanation_incomplete_selection": frozenset(
        {"planning_policy_hypothesis"}
    ),
    "explanation_incorrect_gap": frozenset({"grounding_integrity_action"}),
    "explanation_comparison_mismatch": frozenset({"grounding_integrity_action"}),
    "explanation_reference_ownership": frozenset({"integrity_repair_action"}),
    "explanation_clarity_issue": frozenset({"template_change_hypothesis"}),
}
for _code in _ROOT_CAUSES["data_quality"]:
    _ROOT_CAUSE_ACTIONS[_code] = frozenset({"data_correction_proposal"})
for _code in _ROOT_CAUSES["integrity"]:
    _ROOT_CAUSE_ACTIONS[_code] = frozenset({"integrity_repair_action"})

_TRANSITIONS = {
    "CREATED": frozenset({"REVIEWED", "DISMISSED", "DUPLICATE"}),
    "REVIEWED": frozenset(
        {"ROOT_CAUSE_IDENTIFIED", "DISMISSED", "DUPLICATE"}
    ),
    "ROOT_CAUSE_IDENTIFIED": frozenset({"ACTION_PLANNED", "DISMISSED"}),
    "ACTION_PLANNED": frozenset({"RESOLVED", "DISMISSED"}),
    "RESOLVED": frozenset({"VERIFIED", "REVIEWED"}),
    "VERIFIED": frozenset({"REVIEWED"}),
    "DISMISSED": frozenset({"REVIEWED"}),
    "DUPLICATE": frozenset({"REVIEWED"}),
}

_TRANSITION_REASONS = {
    ("CREATED", "REVIEWED"): "review_completed",
    ("REVIEWED", "ROOT_CAUSE_IDENTIFIED"): "root_cause_supported",
    ("ROOT_CAUSE_IDENTIFIED", "ACTION_PLANNED"): "action_created",
    ("ACTION_PLANNED", "RESOLVED"): "actions_completed",
    ("RESOLVED", "VERIFIED"): "verification_linked",
}


def category_family(category: str) -> str:
    return _CATEGORY_FAMILIES[category]


def root_cause_allowed(root_cause_type: str, root_cause_code: str) -> bool:
    return root_cause_code in _ROOT_CAUSES.get(root_cause_type, frozenset())


def action_allowed(root_cause_type: str, action_type: str) -> bool:
    return action_type in _ACTIONS.get(root_cause_type, frozenset())


def action_allowed_for_root_cause(root_cause_code: str, action_type: str) -> bool:
    return action_type in _ROOT_CAUSE_ACTIONS.get(root_cause_code, frozenset())


def transition_allowed(current: str, target: str) -> bool:
    return target in _TRANSITIONS.get(current, frozenset())


def transition_reason_allowed(current: str, target: str, reason: str) -> bool:
    if not transition_allowed(current, target):
        return False
    if target == "DISMISSED":
        return reason == "case_dismissed"
    if target == "DUPLICATE":
        return reason == "duplicate_linked"
    if target == "REVIEWED" and current != "CREATED":
        return reason == "case_reopened"
    return _TRANSITION_REASONS.get((current, target)) == reason


__all__ = [
    "BAD_CASE_CONTRACT_VERSION",
    "BAD_CASE_TAXONOMY_VERSION",
    "action_allowed",
    "action_allowed_for_root_cause",
    "category_family",
    "root_cause_allowed",
    "transition_allowed",
    "transition_reason_allowed",
]
