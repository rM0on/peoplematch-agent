from __future__ import annotations

from app.exceptions import DomainError


class ExplanationPlanParseError(ValueError):
    category = "invalid_output"

    def __init__(self, _detail: str | None = None) -> None:
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
