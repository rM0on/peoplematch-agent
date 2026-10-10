from __future__ import annotations

from app.exceptions import DomainError


class ExplanationPlanParseError(ValueError):
    category = "invalid_output"

    _SAFE_STAGES = frozenset({"json_decode", "schema_validation", "unknown"})
    _SAFE_REASONS = frozenset({
        "json_invalid", "missing", "extra_forbidden", "literal_error",
        "list_type", "string_type", "int_type", "dict_type", "model_type",
        "value_error", "too_short", "too_long", "string_pattern_mismatch",
        "greater_than_equal", "less_than_equal", "other_schema_error",
        "candidate_comparison_forbidden", "candidate_comparison_required",
        "candidate_reason_order_invalid", "candidate_risk_order_invalid",
        "candidate_interview_order_invalid", "candidate_rewrite_order_invalid",
        "candidate_summary_reason_index_invalid",
        "selection_duplicate_candidate", "selection_candidate_coverage",
        "selection_duplicate_handle", "selection_unknown_or_cross_candidate_handle",
        "selection_wrong_option_type", "selection_summary_reason_not_selected",
        "selection_incompatible_reasons",
    })
    _SAFE_FIELDS = frozenset({
        "contract_version", "candidates", "candidate_ref", "result_rank",
        "summary", "template_key", "evidence_refs", "match_reasons",
        "risk_points", "interview_question_operations", "why_not_top1",
        "rewrite_operations", "category", "operation",
        "match_reason_handles", "risk_handles", "interview_handles",
        "rewrite_handles", "summary_primary_reason_handle",
    })
    _SAFE_INDICES = frozenset(str(n) for n in range(10))

    def __init__(
        self,
        _detail: str | None = None,
        *,
        stage: str = "unknown",
        reason_code: str = "other_schema_error",
        field_path: str = "root",
    ) -> None:
        self.stage = stage if stage in self._SAFE_STAGES else "unknown"
        self.reason_code = (
            reason_code if reason_code in self._SAFE_REASONS else "other_schema_error"
        )
        components = field_path.split(".") if isinstance(field_path, str) else []
        self.field_path = (
            field_path
            if field_path == "root" or (
                components
                and len(field_path) <= 120
                and all(part in self._SAFE_FIELDS or part in self._SAFE_INDICES
                        for part in components)
            )
            else "unknown_field"
        )
        super().__init__("Provider output did not match explanation_plan_v1")


class ExplanationGroundingError(ValueError):
    category = "grounding_failure"

    def __init__(self, _detail: str | None = None) -> None:
        super().__init__("Explanation plan failed deterministic grounding")


class ExplanationGenerationFailedError(DomainError):
    code = "explanation_generation_failed"
    status_code = 502

    def __init__(self, *, explanation_run_id: str, failure_code: str) -> None:
        super().__init__(
            "Explanation generation failed",
            details={
                "explanation_run_id": explanation_run_id,
                "failure_code": failure_code,
            },
        )


class ExplanationPersistenceIntegrityError(DomainError):
    code = "explanation_persistence_integrity_error"
    status_code = 500

    def __init__(self) -> None:
        super().__init__("Persisted explanation failed an integrity check")


__all__ = [
    "ExplanationGenerationFailedError",
    "ExplanationGroundingError",
    "ExplanationPlanParseError",
    "ExplanationPersistenceIntegrityError",
]
