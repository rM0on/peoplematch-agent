from __future__ import annotations

from app.exceptions import DomainError


class Phase10ServiceError(DomainError):
    code = "phase10_service_error"
    status_code = 422


class Phase10NotFoundError(Phase10ServiceError):
    code = "phase10_not_found"
    status_code = 404


class HistoricalTargetError(Phase10ServiceError):
    code = "historical_target_invalid"
    status_code = 422


class ReviewEligibilityError(Phase10ServiceError):
    code = "review_not_eligible"
    status_code = 422


class ReviewConflictError(Phase10ServiceError):
    code = "review_conflict"
    status_code = 409


class ReviewConcurrencyError(ReviewConflictError):
    code = "review_concurrency_conflict"


__all__ = [
    "HistoricalTargetError",
    "Phase10NotFoundError",
    "Phase10ServiceError",
    "ReviewConflictError",
    "ReviewConcurrencyError",
    "ReviewEligibilityError",
]
