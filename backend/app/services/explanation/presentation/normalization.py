from __future__ import annotations

import json


class NarrativeOutputNormalizationError(ValueError):
    """The Provider output cannot be repaired without changing its meaning."""


def normalize_narrative_output(content: str) -> dict:
    """Canonicalize only the redundant top-level reference union.

    Sentence text and sentence-level references are never modified. An extra
    top-level reference not cited by a sentence remains a hard failure.
    """

    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        raise NarrativeOutputNormalizationError() from None
    if not isinstance(payload, dict):
        raise NarrativeOutputNormalizationError()

    statements = [payload.get("candidate_summary"), payload.get("recommendation_summary")]
    for section in ("strengths", "risks", "interview_focus"):
        items = payload.get(section)
        if not isinstance(items, list):
            raise NarrativeOutputNormalizationError()
        statements.extend(items)

    sentence_refs: list[str] = []
    for statement in statements:
        if not isinstance(statement, dict):
            raise NarrativeOutputNormalizationError()
        refs = statement.get("evidence_links")
        if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
            raise NarrativeOutputNormalizationError()
        sentence_refs.extend(refs)

    top_refs = payload.get("evidence_links")
    if not isinstance(top_refs, list) or not all(isinstance(ref, str) for ref in top_refs):
        raise NarrativeOutputNormalizationError()
    cited = set(sentence_refs)
    if not set(top_refs) <= cited:
        raise NarrativeOutputNormalizationError()
    payload["evidence_links"] = sorted(cited)
    return payload


__all__ = ["NarrativeOutputNormalizationError", "normalize_narrative_output"]
