from __future__ import annotations

import re

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts_v2_2 import RecruiterNarrativeV2_2
from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
from app.services.explanation.presentation.validator_v2 import (
    NarrativeV2ValidationError, _GENERIC_ENGLISH, _INTERNAL, _NUMBER, _TECH_TOKEN,
    _UNSUPPORTED, _check_section, _invalid_action, _invalid_responsibility, _invalid_scale,
)
from app.services.explanation.presentation.validator_v2_1 import (
    _unsupported_personal_work, _unsupported_production_claim,
)


_OTHER_CANDIDATE = re.compile(r"另一个候选人|另一位候选人|其他候选人|别的候选人|其他人的项目")
_UNSUPPORTED_PERSONAL = re.compile(
    r"候选人[^。；？?]{0,45}(?:主导|负责|建设|搭建|部署|上线|开发了|实现了|提升了|降低了)|"
    r"(?:亲自|独立)[^。；？?]{0,20}(?:设计|开发|构建|部署)"
)


class NarrativeV2_2ValidationError(ValueError):
    def __init__(self) -> None:
        super().__init__("Recruiter narrative V2.2 claim validation failed")


def _sections(narrative: RecruiterNarrativeV2_2):
    yield "candidate_snapshot", (narrative.candidate_snapshot.text,), narrative.candidate_snapshot.fact_ids, True, False, False
    yield "why_consider", (narrative.why_consider.text,), narrative.why_consider.fact_ids, True, True, False
    for item in narrative.key_strengths:
        yield "key_strengths", (item.title, item.explanation), item.fact_ids, True, False, False
    for item in narrative.trade_offs:
        yield "trade_offs", (item.title, item.explanation, item.validation_question), item.fact_ids, False, False, True
    for item in narrative.interview_focus:
        yield "interview_focus", (item.topic, item.question, item.reason), item.fact_ids, False, False, True


def invalid_narrative_v2_2_sections(
    narrative: RecruiterNarrativeV2_2, *, projection: NarrativeProjection,
) -> tuple[str, ...]:
    package = build_evidence_package_v2_2(projection)
    lookup = {fact.fact_id: fact for fact in package.all_facts}
    invalid = []
    for section, texts, ids, positive, alignment, cautious in _sections(narrative):
        selected = [lookup[ident] for ident in ids if ident in lookup]
        try:
            if (any(_OTHER_CANDIDATE.search(text) or _UNSUPPORTED_PERSONAL.search(text)
                    or _unsupported_personal_work(text) or _unsupported_production_claim(text)
                    for text in texts)
                    or (positive and not any(f.kind in {"candidate_skill", "project_practice", "technical_scope",
                                                        "requirement_alignment"} for f in selected))
                    or (alignment and not any(f.kind == "requirement_alignment" for f in selected))):
                raise NarrativeV2_2ValidationError()
            _check_section(texts, ids, facts=lookup, cautious=cautious,
                           job_role=projection.role_title if alignment else None,
                           allow_unknown_scale=True)
        except (NarrativeV2ValidationError, NarrativeV2_2ValidationError):
            invalid.append(section)
    return tuple(dict.fromkeys(invalid))


def validate_narrative_v2_2_projection(
    narrative: RecruiterNarrativeV2_2, *, projection: NarrativeProjection,
) -> None:
    if (narrative.candidate_id != projection.candidate_id
            or narrative.result_rank != projection.result_rank
            or invalid_narrative_v2_2_sections(narrative, projection=projection)):
        raise NarrativeV2_2ValidationError()


def validation_error_summary_v2_2(
    narrative: RecruiterNarrativeV2_2, *, projection: NarrativeProjection,
) -> dict[str, object]:
    """Return bounded categories, never the original provider prose."""
    lookup = {fact.fact_id: fact for fact in build_evidence_package_v2_2(projection).all_facts}
    bad = set(invalid_narrative_v2_2_sections(narrative, projection=projection))
    details = []
    for section, texts, ids, positive, alignment, cautious in _sections(narrative):
        if section not in bad:
            continue
        selected = [lookup[ident] for ident in ids if ident in lookup]
        permitted = {token.casefold() for fact in selected for token in _TECH_TOKEN.findall(fact.term)} | _GENERIC_ENGLISH
        if alignment and any(projection.role_title.casefold() in text.casefold() for text in texts):
            permitted |= {token.casefold() for token in _TECH_TOKEN.findall(projection.role_title)}
        details.append({
            "section": section,
            "unsupported_terms": sorted({token.casefold() for text in texts
                                         for token in _TECH_TOKEN.findall(text)} - permitted),
            "unsupported_numbers": sorted({number for text in texts for number in _NUMBER.findall(text)}
                                          - {number for fact in selected for number in _NUMBER.findall(fact.term)}),
            "unknown_fact_id": any(ident not in lookup for ident in ids),
            "missing_alignment": alignment and not any(f.kind == "requirement_alignment" for f in selected),
            "missing_candidate_fact": positive and not any(f.kind in {
                "candidate_skill", "project_practice", "technical_scope", "requirement_alignment"
            } for f in selected),
            "unsafe_claim": any(_UNSUPPORTED.search(text) or _INTERNAL.search(text) for text in texts),
            "personal_action": any(_UNSUPPORTED_PERSONAL.search(text) or _unsupported_personal_work(text)
                                   or _invalid_action(text) or _invalid_responsibility(text, cautious=cautious)
                                   for text in texts),
            "unsupported_scale": any(_invalid_scale(text, cautious=cautious, allow_unknown_scale=True)
                                     or _unsupported_production_claim(text) for text in texts),
            "cross_candidate": any(_OTHER_CANDIDATE.search(text) for text in texts),
        })
    return {"category": "claim_validation_failed", "invalid_sections": details}


__all__ = ["NarrativeV2_2ValidationError", "invalid_narrative_v2_2_sections",
           "validate_narrative_v2_2_projection", "validation_error_summary_v2_2"]
