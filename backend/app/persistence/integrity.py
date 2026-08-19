from __future__ import annotations

from sqlalchemy.exc import IntegrityError


_HISTORICAL_PROFILE_CONSTRAINTS = {
    "match_runs_job_id_fkey",
    "match_results_candidate_id_fkey",
}


def is_historical_profile_fk_violation(error: IntegrityError) -> bool:
    """Return True only for PostgreSQL FK errors protecting match history."""

    original = error.orig
    code = getattr(original, "pgcode", None) or getattr(original, "sqlstate", None)
    if code != "23503":
        return False

    diagnostic = getattr(original, "diag", None)
    constraint = (
        getattr(diagnostic, "constraint_name", None)
        if diagnostic is not None
        else None
    ) or getattr(original, "constraint_name", None)
    return constraint is None or constraint in _HISTORICAL_PROFILE_CONSTRAINTS
