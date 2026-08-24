from __future__ import annotations

from app.services.explanation.contracts import (
    project_provider_evidence,
    provider_evidence_fingerprint,
)


def evidence_content_fingerprint(bundle) -> str:
    """Fingerprint normalized, provider-safe content without MatchRun audit identity."""

    return provider_evidence_fingerprint(project_provider_evidence(bundle))


__all__ = ["evidence_content_fingerprint"]
