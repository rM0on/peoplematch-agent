class EvaluationIntegrityError(ValueError):
    """Frozen evaluation input or comparability contract is invalid."""


class EvaluationOperationalError(RuntimeError):
    """An operational dependency prevented an evaluation attempt."""
