from __future__ import annotations

import unicodedata

from app.services.features.contract import NORMALIZER_VERSION


_TECHNICAL_SUFFIX_SYMBOLS = frozenset({"+", "#"})


def _is_technical_suffix_symbol(value: str, index: int) -> bool:
    if value[index] not in _TECHNICAL_SUFFIX_SYMBOLS or index == 0:
        return False
    previous = value[index - 1]
    return previous.isalnum() or previous in _TECHNICAL_SUFFIX_SYMBOLS


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    characters: list[str] = []
    for index, character in enumerate(normalized):
        if _is_technical_suffix_symbol(normalized, index):
            characters.append(character)
        elif (
            character == "."
            and index + 1 < len(normalized)
            and normalized[index + 1].isalnum()
        ):
            previous = normalized[index - 1] if index else ""
            following = normalized[index + 1]
            if not (previous.isalpha() and following.isalpha()):
                characters.append(character)
        elif unicodedata.category(character).startswith(("P", "S")):
            characters.append(" ")
        else:
            characters.append(character)
    return " ".join("".join(characters).split())


def normalized_tokens(value: str) -> tuple[str, ...]:
    normalized = normalize_text(value)
    return tuple(normalized.split()) if normalized else ()


__all__ = ["NORMALIZER_VERSION", "normalize_text", "normalized_tokens"]
