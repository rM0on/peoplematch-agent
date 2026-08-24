from __future__ import annotations

import re
import unicodedata
from typing import Any


NORMALIZER_VERSION = "evidence_label_normalization_v1"
_SAFE_NORMALIZED_LABEL = re.compile(
    r"^[a-z0-9][a-z0-9_.:/+-]*(?: [a-z0-9][a-z0-9_.:/+-]*){0,11}$"
)


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


__all__ = ["NORMALIZER_VERSION", "canonicalize_labels", "normalize_label"]
