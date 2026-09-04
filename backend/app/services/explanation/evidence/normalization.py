from __future__ import annotations

import re
import unicodedata
from typing import Any


NORMALIZER_VERSION = "evidence_label_normalization_v1"
_SAFE_NORMALIZED_LABEL = re.compile(
    r"^[a-z0-9][a-z0-9_.:/+-]*(?: [a-z0-9][a-z0-9_.:/+-]*){0,11}$"
)
_SAFE_HISTORICAL_TEXT_PUNCTUATION = frozenset("._:/+()-")


def normalize_label(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a historical string label")
    normalized = " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
    if (
        not normalized
        or len(normalized) > 120
        or _SAFE_NORMALIZED_LABEL.fullmatch(normalized) is None
    ):
        raise ValueError(f"{label} must be a bounded normalized historical label")
    return normalized


def canonicalize_labels(values: Any, label: str) -> list[str]:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list of normalized labels")
    return sorted({normalize_label(value, label) for value in values})


def normalize_historical_text_label(value: Any, label: str) -> str:
    """Normalize bounded Unicode labels that never cross the provider boundary."""

    if not isinstance(value, str):
        raise ValueError(f"{label} must be a historical string label")
    normalized = " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
    tokens = normalized.split(" ") if normalized else []
    if (
        not normalized
        or len(normalized) > 120
        or len(tokens) > 12
        or any(
            not token
            or not token[0].isalnum()
            or any(
                not character.isalnum()
                and character not in _SAFE_HISTORICAL_TEXT_PUNCTUATION
                for character in token
            )
            for token in tokens
        )
    ):
        raise ValueError(f"{label} must be a bounded historical text label")
    return normalized


def canonicalize_historical_text_labels(values: Any, label: str) -> list[str]:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list of historical text labels")
    return sorted({normalize_historical_text_label(value, label) for value in values})


__all__ = [
    "NORMALIZER_VERSION",
    "canonicalize_historical_text_labels",
    "canonicalize_labels",
    "normalize_historical_text_label",
    "normalize_label",
]
