from __future__ import annotations

import re

from app.schemas.explanations import CandidateExplanationOutput, InternalEvidenceBundleV1
from app.services.explanation.presentation.contracts import NarrativeStatement, RecruiterNarrativeV1
from app.services.explanation.presentation.copy_catalog import approved_copy


_LATIN_TERM = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]*")
_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")
_SCALE_OR_IMPACT = re.compile(r"百万|千万|亿级|大规模|生产级|提升.{0,12}(?:效率|性能)|丰富经验|多年经验")
_UNSUPPORTED_DECISION = re.compile(r"建议录用|直接录用|保证录用|100%|一定适合|完全匹配")
_INTERNAL_LANGUAGE = re.compile(r"evidence\s*ref|schema\s*validation|grounding|fingerprint|证据引用|校验通过", re.I)
_GAP_LANGUAGE = re.compile(r"建议|待确认|进一步|未体现|尚未覆盖|需要确认|可核实")
_UNSUPPORTED_NEGATIVE = re.compile(r"候选人(?:缺少|没有|不具备|不擅长)|完全没有|无法胜任")
_UNSUPPORTED_SENIORITY = re.compile(r"高级专家|资深专家|技术负责人|架构师|总监|主管|首席")


class NarrativeValidationError(ValueError):
    """Safe failure category: never include provider text or private facts."""

    def __init__(self) -> None:
        super().__init__("Recruiter narrative failed evidence validation")


def _validate_statement(
    statement: NarrativeStatement,
    *,
    allowed_refs: frozenset[str],
    facts: dict[str, tuple[str, ...]],
    role_title: str,
    approved: list[NarrativeStatement],
    require_candidate: bool = False,
    require_job: bool = False,
    require_gap_language: bool = False,
) -> None:
    refs = set(statement.evidence_links)
    if statement not in approved:
        raise NarrativeValidationError()
    if not refs <= allowed_refs or not refs <= facts.keys():
        raise NarrativeValidationError()
    if require_candidate and not any(ref.startswith("candidate:") for ref in refs):
        raise NarrativeValidationError()
    if require_job and not any(ref.startswith("job_requirement:") for ref in refs):
        raise NarrativeValidationError()
    if require_gap_language and not _GAP_LANGUAGE.search(statement.text):
        raise NarrativeValidationError()
    terms = {term for ref in refs for term in facts[ref] if term}
    if not any(term.casefold() in statement.text.casefold() for term in terms):
        raise NarrativeValidationError()
    if (_SCALE_OR_IMPACT.search(statement.text) or _UNSUPPORTED_DECISION.search(statement.text)
            or _INTERNAL_LANGUAGE.search(statement.text) or _UNSUPPORTED_NEGATIVE.search(statement.text)
            or _UNSUPPORTED_SENIORITY.search(statement.text)):
        raise NarrativeValidationError()
    permitted_latin = {
        token.casefold()
        for term in (*terms, role_title)
        for token in _LATIN_TERM.findall(term)
    }
    if any(token.casefold() not in permitted_latin for token in _LATIN_TERM.findall(statement.text)):
        raise NarrativeValidationError()
    source_numbers = {number for term in terms for number in _NUMBER.findall(term)}
    if any(number not in source_numbers for number in _NUMBER.findall(statement.text)):
        raise NarrativeValidationError()


def validate_recruiter_narrative(
    narrative: RecruiterNarrativeV1,
    *,
    bundle: InternalEvidenceBundleV1,
    source: CandidateExplanationOutput,
) -> None:
    from app.services.explanation.presentation.adapter import build_narrative_projection

    projection = build_narrative_projection(bundle=bundle, source=source)
    if (narrative.candidate_id != source.candidate_id
            or narrative.result_rank != source.result_rank):
        raise NarrativeValidationError()
    catalog = approved_copy(projection)
    if len({(item.text, tuple(item.evidence_links)) for item in narrative.strengths}) != len(narrative.strengths):
        raise NarrativeValidationError()
    for section, statement in (
        ("candidate_summary", narrative.candidate_summary),
        ("recommendation_summary", narrative.recommendation_summary),
        *(("strengths", item) for item in narrative.strengths),
    ):
        _validate_statement(
            statement,
            allowed_refs=projection.positive_refs,
            facts=projection.facts,
            role_title=projection.role_title,
            approved=catalog[section],
            require_candidate=True,
            require_job=section == "recommendation_summary",
        )
    for statement in narrative.risks:
        _validate_statement(
            statement,
            allowed_refs=projection.risk_refs,
            facts=projection.facts,
            role_title=projection.role_title,
            approved=catalog["risks"],
            require_gap_language=True,
        )
    for statement in narrative.interview_focus:
        _validate_statement(
            statement,
            allowed_refs=projection.interview_refs,
            facts=projection.facts,
            role_title=projection.role_title,
            approved=catalog["interview_focus"],
            require_gap_language=True,
        )


__all__ = ["NarrativeValidationError", "validate_recruiter_narrative"]
