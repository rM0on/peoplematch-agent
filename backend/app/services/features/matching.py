from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Iterable, Sequence

from app.schemas.job import JobRequirement, RequirementCategory
from app.services.features.normalization import normalize_text, normalized_tokens


SKILL_REQUIREMENT_CATEGORIES = frozenset({RequirementCategory.SKILL})
EVIDENCE_REQUIREMENT_CATEGORIES = frozenset(
    {RequirementCategory.SKILL, RequirementCategory.PROJECT_EVIDENCE}
)


@dataclass(frozen=True)
class RequirementMatch:
    requirement_id: str
    value: float
    matched_atoms: tuple[str, ...]


def _contains_phrase(text_tokens: Sequence[str], phrase_tokens: Sequence[str]) -> bool:
    if not phrase_tokens or len(phrase_tokens) > len(text_tokens):
        return False
    width = len(phrase_tokens)
    return any(
        tuple(text_tokens[index : index + width]) == tuple(phrase_tokens)
        for index in range(len(text_tokens) - width + 1)
    )


def normalized_atoms(values: Iterable[str]) -> dict[str, str]:
    atoms: dict[str, str] = {}
    for value in values:
        normalized = normalize_text(value)
        if normalized:
            atoms.setdefault(normalized, value)
    return atoms


def match_requirement(
    requirement: JobRequirement, atoms: dict[str, str]
) -> RequirementMatch:
    text_tokens = normalized_tokens(requirement.text)
    matched = tuple(
        sorted(
            original
            for normalized, original in atoms.items()
            if _contains_phrase(text_tokens, normalized.split())
        )
    )
    return RequirementMatch(
        requirement_id=requirement.requirement_id,
        value=1.0 if matched else 0.0,
        matched_atoms=matched,
    )


def applicable_requirements(
    requirements: Iterable[JobRequirement],
    allowed_categories: Collection[RequirementCategory],
) -> list[JobRequirement]:
    return [item for item in requirements if item.category in allowed_categories]
