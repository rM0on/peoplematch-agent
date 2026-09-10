from __future__ import annotations

from copy import deepcopy
from typing import Any


_KNOWN_TECHNICAL_REQUIREMENT_EXPANSIONS = {
    "CV": "CV（Computer Vision）",
    "LLM": "LLM（Large Language Model）",
    "NLP": "NLP（Natural Language Processing）",
    "RAG": "RAG（Retrieval-Augmented Generation）",
}


def normalize_job_extraction_payload(payload: Any) -> Any:
    """Expand only exact, known short technical requirement labels.

    The provider response string remains untouched. A copied decoded payload is
    normalized immediately before schema validation so provider provenance and
    retry behavior remain authoritative.
    """

    if not isinstance(payload, dict):
        return payload

    normalized = deepcopy(payload)
    for field_name in ("must_have", "nice_to_have"):
        requirements = normalized.get(field_name)
        if not isinstance(requirements, list):
            continue
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            text = requirement.get("text")
            if not isinstance(text, str):
                continue
            expanded = _KNOWN_TECHNICAL_REQUIREMENT_EXPANSIONS.get(
                text.strip().upper()
            )
            if expanded is not None:
                requirement["text"] = expanded
    return normalized


__all__ = ["normalize_job_extraction_payload"]
