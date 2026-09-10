"""Narrow formatting compatibility for bounded explanation repair output."""

from __future__ import annotations

import json
import re
from typing import Any


_PROVIDER_REFERENCE = re.compile(r"^ref_[0-9]{4}$")
_SELECTION_LIST_FIELDS = (
    "match_reasons",
    "risk_points",
    "interview_question_operations",
    "rewrite_operations",
)


def _canonicalize_reference_list(selection: Any) -> bool:
    if not isinstance(selection, dict):
        return False
    references = selection.get("evidence_refs")
    if (
        not isinstance(references, list)
        or not all(
            isinstance(reference, str)
            and _PROVIDER_REFERENCE.fullmatch(reference) is not None
            for reference in references
        )
    ):
        return False
    canonical = sorted(set(references))
    if canonical == references:
        return False
    selection["evidence_refs"] = canonical
    return True


def normalize_explanation_repair_output(content: str) -> str:
    """Canonicalize only existing opaque reference lists on repair attempt two.

    The function never adds fields, replaces references, or interprets evidence.
    Unknown but syntactically valid references remain unknown so the unchanged
    grounding validator can reject them.
    """

    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return content
    if not isinstance(payload, dict):
        return content
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return content

    changed = False
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        changed = _canonicalize_reference_list(candidate.get("summary")) or changed
        changed = (
            _canonicalize_reference_list(candidate.get("why_not_top1")) or changed
        )
        for field in _SELECTION_LIST_FIELDS:
            selections = candidate.get(field)
            if not isinstance(selections, list):
                continue
            for selection in selections:
                changed = _canonicalize_reference_list(selection) or changed

    if not changed:
        return content
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


__all__ = ["normalize_explanation_repair_output"]
