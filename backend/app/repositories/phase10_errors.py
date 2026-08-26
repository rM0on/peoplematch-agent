from __future__ import annotations


class Phase10RepositoryError(RuntimeError):
    """Base error for Phase 10 repository boundaries."""


class Phase10NotFoundError(Phase10RepositoryError):
    """A requested Phase 10 or historical source record does not exist."""


class Phase10ConflictError(Phase10RepositoryError):
    """Persisted history or requested ownership is inconsistent."""


class Phase10TransactionError(Phase10ConflictError):
    """A repository operation lacks the transaction ownership it requires."""


class FeedbackNotFoundError(Phase10NotFoundError):
    pass


class BadCaseNotFoundError(Phase10NotFoundError):
    pass


class HistoricalOwnerNotFoundError(Phase10NotFoundError):
    pass


class FeedbackConflictError(Phase10ConflictError):
    pass


class BadCaseConflictError(Phase10ConflictError):
    pass


class BadCaseConcurrencyError(BadCaseConflictError):
    pass


class HistoricalOwnershipError(Phase10ConflictError):
    pass


class HistoricalIntegrityError(Phase10ConflictError):
    pass


__all__ = [
    "BadCaseConcurrencyError",
    "BadCaseConflictError",
    "BadCaseNotFoundError",
    "FeedbackConflictError",
    "FeedbackNotFoundError",
    "HistoricalIntegrityError",
    "HistoricalOwnerNotFoundError",
    "HistoricalOwnershipError",
    "Phase10ConflictError",
    "Phase10NotFoundError",
    "Phase10RepositoryError",
    "Phase10TransactionError",
]
