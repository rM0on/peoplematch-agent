from __future__ import annotations

import re

from app.schemas.explanations import CandidateExplanationOutput, InternalEvidenceBundleV1
from app.services.explanation.presentation.adapter import NarrativeProjection, build_narrative_projection
from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
from app.services.explanation.presentation.facts_v2 import AtomicFactV2
from app.services.explanation.presentation.facts_v2_1 import _DIRECTION_TERMS, build_atomic_facts_v2_1
from app.services.explanation.presentation.validator_v2 import (
    NarrativeV2ValidationError, _GENERIC_ENGLISH, _INTERNAL, _NUMBER, _TECH_TOKEN,
    _UNSUPPORTED, _check_section, _invalid_action, _invalid_responsibility, _invalid_scale,
)


_FOREIGN_CANDIDATE = re.compile(r"另一个候选人|其他候选人|别的候选人|其他人的项目")
_PRODUCTION_ASSERTION = re.compile(
    r"高可用[^。？?]{0,30}(?:实践|经验)|(?:系统)?上线后[^。？?]{0,35}(?:取得|提升|收益|成果)|"
    r"候选人[^。？?]{0,40}(?:高可用|业务收益|线上规模)[^。？?]{0,25}(?:实践|经验|成果)"
)
_PERSONAL_WORK_ASSERTION = re.compile(
    r"(?:结合|使用|利用|基于|通过)[^。？?]{0,55}(?:构建|开发|部署|优化|实现|打包)|"
    r"(?:候选人|其)[^。？?]{0,30}(?:结合了|实践了|应用了|处理了)|"
    r"(?:掌握|熟练|精通)[^。？?]{0,35}|"
    r"(?:具备|体现|显示|展现)[^。？?]{0,40}(?:工程经验|工程能力|实战经验|部署经验|基础工程能力)"
)


def _unsupported_production_claim(text: str) -> bool:
    if not _PRODUCTION_ASSERTION.search(text):
        return False
    return not any(marker in text for marker in ("如果", "假设", "是否", "未体现", "未说明", "待确认"))


def _unsupported_personal_work(text: str) -> bool:
    if not _PERSONAL_WORK_ASSERTION.search(text):
        return False
    return not any(marker in text for marker in ("如何", "如果", "假设", "是否", "请", "？", "?"))


class NarrativeV2_1ValidationError(ValueError):
    def __init__(self) -> None:
        super().__init__("Recruiter narrative V2.1 claim validation failed")


def _sections(narrative: RecruiterNarrativeV2_1):
    yield "candidate_snapshot", (narrative.candidate_snapshot.text,), narrative.candidate_snapshot.fact_ids, True, False, False
    yield "why_consider", (narrative.why_consider.text,), narrative.why_consider.fact_ids, True, True, False
    for item in narrative.key_strengths:
        yield "key_strengths", (item.title, item.explanation), item.fact_ids, True, False, False
    for item in narrative.trade_offs:
        yield "trade_offs", (item.title, item.explanation, item.validation_question), item.fact_ids, False, False, True
    for item in narrative.interview_focus:
        yield "interview_focus", (item.topic, item.question, item.reason), item.fact_ids, False, False, True


def _unsupported_direction(texts: tuple[str, ...], selected: list[AtomicFactV2]) -> bool:
    prose = " ".join(texts)
    for direction in _DIRECTION_TERMS:
        if direction not in prose:
            continue
        if not any(f.kind == "direction_inference" and f.term == direction for f in selected):
            return True
    return False


def invalid_narrative_v2_1_sections(
    narrative: RecruiterNarrativeV2_1, *, projection: NarrativeProjection,
) -> tuple[str, ...]:
    lookup = {fact.fact_id: fact for fact in build_atomic_facts_v2_1(projection)}
    invalid = []
    for label, texts, ids, positive, alignment, cautious in _sections(narrative):
        try:
            selected = [lookup[ident] for ident in ids if ident in lookup]
            if (any(_FOREIGN_CANDIDATE.search(text) for text in texts)
                    or any(_unsupported_production_claim(text) for text in texts)
                    or any(_unsupported_personal_work(text) for text in texts)
                    or _unsupported_direction(texts, selected)):
                raise NarrativeV2_1ValidationError()
            _check_section(texts, ids, facts=lookup, positive=positive, alignment=alignment,
                           cautious=cautious, job_role=projection.role_title,
                           allow_unknown_scale=True)
        except (NarrativeV2ValidationError, NarrativeV2_1ValidationError):
            invalid.append(label)
    return tuple(dict.fromkeys(invalid))


def validation_error_summary_v2_1(
    narrative: RecruiterNarrativeV2_1, *, projection: NarrativeProjection,
) -> dict[str, object]:
    """Expose bounded failure categories and technical terms, never model prose."""
    lookup = {fact.fact_id: fact for fact in build_atomic_facts_v2_1(projection)}
    invalid = set(invalid_narrative_v2_1_sections(narrative, projection=projection))
    diagnostics = []
    for label, texts, ids, _positive, _alignment, cautious in _sections(narrative):
        if label not in invalid:
            continue
        selected = [lookup[ident] for ident in ids if ident in lookup]
        permitted = {token.casefold() for fact in selected for token in _TECH_TOKEN.findall(fact.term)} | _GENERIC_ENGLISH
        unsupported_terms = set()
        for text in texts:
            role_tokens = (
                {token.casefold() for token in _TECH_TOKEN.findall(projection.role_title)}
                if projection.role_title.casefold() in text.casefold() else set()
            )
            unsupported_terms |= {
                token.casefold() for token in _TECH_TOKEN.findall(text)
            } - permitted - role_tokens
        missing_direction_terms = sorted(
            direction for direction in _DIRECTION_TERMS
            if direction in " ".join(texts)
            and not any(f.kind == "direction_inference" and f.term == direction for f in selected)
        )
        diagnostics.append({
            "section": label,
            "unsupported_terms": sorted(unsupported_terms),
            "supported_terms": sorted({fact.term for fact in selected})[:8],
            "missing_direction_terms": missing_direction_terms,
            "unsupported_numbers": sorted({number for text in texts for number in _NUMBER.findall(text)} -
                                          {number for fact in selected for number in _NUMBER.findall(fact.term)}),
            "unsafe_claim": any(_UNSUPPORTED.search(text) or _INTERNAL.search(text) for text in texts),
            "unsupported_scale": any(_invalid_scale(text, cautious=cautious, allow_unknown_scale=True) for text in texts),
            "unsupported_action": any(_invalid_action(text) for text in texts),
            "responsibility_violation": any(_invalid_responsibility(text, cautious=cautious) for text in texts),
            "foreign_candidate": any(_FOREIGN_CANDIDATE.search(text) for text in texts),
            "missing_direction_support": _unsupported_direction(texts, selected),
            "unsupported_production_claim": any(_unsupported_production_claim(text) for text in texts),
            "unsupported_personal_work": any(_unsupported_personal_work(text) for text in texts),
            "unknown_fact_id": any(ident not in lookup for ident in ids),
            "duplicate_fact_id": len(ids) != len(set(ids)),
            "missing_positive_fact": _positive and not any(
                f.kind in {"candidate_skill", "project_practice", "requirement_alignment"} for f in selected
            ),
            "missing_mentioned_fact_term": _positive and not any(
                f.term.casefold() in " ".join(texts).casefold() for f in selected
            ),
        })
    return {"category": "claim_validation_failed", "invalid_sections": diagnostics}


def validate_narrative_v2_1_projection(
    narrative: RecruiterNarrativeV2_1, *, projection: NarrativeProjection,
) -> None:
    if (narrative.candidate_id != projection.candidate_id
            or narrative.result_rank != projection.result_rank
            or invalid_narrative_v2_1_sections(narrative, projection=projection)):
        raise NarrativeV2_1ValidationError()


def validate_narrative_v2_1(
    narrative: RecruiterNarrativeV2_1, *, facts: tuple[AtomicFactV2, ...],
    bundle: InternalEvidenceBundleV1, source: CandidateExplanationOutput,
) -> None:
    """Validate source binding and bounded factual claims, not prose style.

    Natural-language entailment remains heuristic; unsupported personal actions,
    scale and results are rejected, not inferred from a technology token.
    """
    projection = build_narrative_projection(bundle=bundle, source=source)
    if facts != build_atomic_facts_v2_1(projection):
        raise NarrativeV2_1ValidationError()
    validate_narrative_v2_1_projection(narrative, projection=projection)


__all__ = [
    "NarrativeV2_1ValidationError", "invalid_narrative_v2_1_sections",
    "validation_error_summary_v2_1", "validate_narrative_v2_1",
    "validate_narrative_v2_1_projection",
]
