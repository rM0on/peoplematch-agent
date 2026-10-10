from __future__ import annotations

import re

from app.schemas.explanations import CandidateExplanationOutput, InternalEvidenceBundleV1
from app.services.explanation.presentation.contracts_v2 import RecruiterNarrativeV2
from app.services.explanation.presentation.facts_v2 import AtomicFactV2, build_atomic_facts
from app.services.explanation.presentation.adapter import NarrativeProjection, build_narrative_projection


_TECH_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]*")
_GENERIC_ENGLISH = {"project", "candidate", "role", "interview"}
_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")
_UNSUPPORTED = re.compile(
    r"建议(?:直接)?录用|强烈推荐录用|一定适合|完全匹配|无需(?:再|进一步)验证|"
    r"已(?:经)?证明(?:适合|胜任)|百分之百|100%|"
    r"(?:提升|提高|降低).{0,12}(?:准确率|效率|成本|性能)|"
    r"高级专家|资深专家|技术负责人|架构师|总监|主管|首席|"
    r"候选人(?:缺少|没有|不具备|无法胜任)|"
    r"扎实的?[^。]{0,12}(?:基础|能力)|精通|完全胜任|足以支撑|能够支撑|"
    r"有助于(?:保障|提升|改进)|"
    r"具备[^。]{0,25}(?:构建|部署|优化|开发)[^。]{0,20}(?:能力|经验|实践|基础)"
)
_UNSUPPORTED_ACTION = re.compile(
    r"(?:候选人|其|在项目中|项目中)[^，,；。]{0,40}(?:使用|利用|基于)[^，,；。]{0,30}"
    r"(?:构建|实现|部署|优化|搭建|开发|完成部署)"
)
_SCALE = re.compile(r"百万|千万|亿级|企业级|大规模|生产级")
_ASSERTED_SCALE = re.compile(
    r"(?:候选人|其).{0,20}(?:具备|拥有|有|支撑|负责|建设).{0,15}(?:百万|千万|亿级|企业级|大规模|生产级)"
)
_UNKNOWN_SCALE = re.compile(r"未体现|未提供|未说明|尚未覆盖|需.{0,8}确认|待.{0,8}确认")
_RESPONSIBILITY = re.compile(r"(?:候选人|其|本人)(?:曾|已|在[^，,；。]{0,30})?(?:主导|负责|领导|建设|搭建)")
_UNKNOWN_SCOPE = re.compile(r"(?:负责的?(?:具体)?(?:模块|范围|职责)|负责范围|具体职责|实际职责).{0,12}(?:需|待|未|确认|核实|了解)")
_ASSERTED_RESPONSIBILITY = re.compile(r"(?:曾负责|已负责|负责了|主导了|建设了|搭建了)")
_INTERNAL = re.compile(r"evidence\s*ref|schema\s*validation|grounding|fingerprint|证据引用|校验通过|Evidence支持|缺少Evidence", re.I)
_CAUTIOUS = re.compile(r"建议|请|是否|如何|什么|怎样|需|待|进一步|确认|核实|了解|验证|未体现|尚未覆盖|[？?]")


class NarrativeV2ValidationError(ValueError):
    def __init__(self) -> None:
        super().__init__("Recruiter narrative claim validation failed")


def _invalid_scale(text: str, *, cautious: bool, allow_unknown_scale: bool = False) -> bool:
    if (allow_unknown_scale and cautious and _UNKNOWN_SCALE.search(text)
            and not _ASSERTED_SCALE.search(text)):
        return False
    return bool(_SCALE.search(text) and not (
        cautious and (text.startswith("请") or "是否" in text)
        and not _ASSERTED_SCALE.search(text)
    ))


def _invalid_action(text: str) -> bool:
    return bool(_UNSUPPORTED_ACTION.search(text) and not (
        text.startswith("请") or "如何" in text or "是否" in text or "？" in text or "?" in text
    ))


def _invalid_responsibility(text: str, *, cautious: bool) -> bool:
    return bool(_RESPONSIBILITY.search(text) and not (
        text.startswith("请") or "是否" in text
        or (cautious and _UNKNOWN_SCOPE.search(text)
            and not _ASSERTED_RESPONSIBILITY.search(text))
    ))


def _check_section(
    texts: tuple[str, ...], ids: list[str], *, facts: dict[str, AtomicFactV2],
    positive: bool = False, alignment: bool = False, cautious: bool = False,
    job_role: str | None = None, allow_unknown_scale: bool = False,
) -> None:
    if len(ids) != len(set(ids)) or not ids or any(fact_id not in facts for fact_id in ids):
        raise NarrativeV2ValidationError()
    selected = [facts[fact_id] for fact_id in ids]
    if positive and not any(f.kind in {"candidate_skill", "project_practice", "requirement_alignment"} for f in selected):
        raise NarrativeV2ValidationError()
    if alignment and not any(f.kind == "requirement_alignment" for f in selected):
        raise NarrativeV2ValidationError()
    terms = {f.term.casefold() for f in selected}
    permitted_tokens = {token.casefold() for term in terms for token in _TECH_TOKEN.findall(term)}
    permitted_numbers = {number for term in terms for number in _NUMBER.findall(term)}
    for text in texts:
        role_tokens = (
            {token.casefold() for token in _TECH_TOKEN.findall(job_role)}
            if job_role and job_role.casefold() in text.casefold() else set()
        )
        if (_UNSUPPORTED.search(text) or _INTERNAL.search(text)
                or _invalid_scale(text, cautious=cautious, allow_unknown_scale=allow_unknown_scale)
                or _invalid_action(text)
                or _invalid_responsibility(text, cautious=cautious)):
            raise NarrativeV2ValidationError()
        if any(token.casefold() not in permitted_tokens | _GENERIC_ENGLISH | role_tokens
               for token in _TECH_TOKEN.findall(text)):
            raise NarrativeV2ValidationError()
        if any(number not in permitted_numbers for number in _NUMBER.findall(text)):
            raise NarrativeV2ValidationError()
    if cautious and not any(_CAUTIOUS.search(text) for text in texts):
        raise NarrativeV2ValidationError()
    if positive and not any(term in " ".join(texts).casefold() for term in terms):
        raise NarrativeV2ValidationError()


def validate_narrative_v2(
    narrative: RecruiterNarrativeV2, *, facts: tuple[AtomicFactV2, ...],
    bundle: InternalEvidenceBundleV1, source: CandidateExplanationOutput,
) -> None:
    """Validate source provenance, structured claims and factual surface markers.

    This is intentionally not a claim of complete semantic entailment for
    arbitrary prose. Unknown relations and unsafe assertions fail closed.
    """
    projection = build_narrative_projection(bundle=bundle, source=source)
    expected = build_atomic_facts(projection)
    if (narrative.candidate_id != source.candidate_id or narrative.result_rank != source.result_rank
            or facts != expected):
        raise NarrativeV2ValidationError()
    validate_narrative_v2_projection(narrative, projection=projection)


def validate_narrative_v2_projection(
    narrative: RecruiterNarrativeV2, *, projection: NarrativeProjection,
) -> None:
    if narrative.candidate_id != projection.candidate_id or narrative.result_rank != projection.result_rank:
        raise NarrativeV2ValidationError()
    lookup = {fact.fact_id: fact for fact in build_atomic_facts(projection)}
    _check_section((narrative.decision_summary.text,), narrative.decision_summary.fact_ids,
                   facts=lookup, positive=True, alignment=True, job_role=projection.role_title)
    _check_section((narrative.why_review.text,), narrative.why_review.fact_ids,
                   facts=lookup, positive=True, alignment=True, job_role=projection.role_title)
    for item in narrative.strengths:
        _check_section((item.title, item.explanation), item.fact_ids, facts=lookup, positive=True)
    for item in narrative.concerns:
        _check_section((item.title, item.explanation, item.validation_question), item.fact_ids,
                       facts=lookup, cautious=True)
    for item in narrative.interview_focus:
        _check_section((item.topic, item.question, item.reason), item.fact_ids,
                       facts=lookup, cautious=True)


def invalid_narrative_v2_sections(
    narrative: RecruiterNarrativeV2, *, projection: NarrativeProjection,
) -> tuple[str, ...]:
    """Return only safe field labels for one constrained provider repair."""
    lookup = {fact.fact_id: fact for fact in build_atomic_facts(projection)}
    checks = [
        ("decision_summary", (narrative.decision_summary.text,), narrative.decision_summary.fact_ids, True, True, False),
        ("why_review", (narrative.why_review.text,), narrative.why_review.fact_ids, True, True, False),
        *(("strength", (item.title, item.explanation), item.fact_ids, True, False, False)
          for item in narrative.strengths),
        *(("concern", (item.title, item.explanation, item.validation_question), item.fact_ids, False, False, True)
          for item in narrative.concerns),
        *(("interview_focus", (item.topic, item.question, item.reason), item.fact_ids, False, False, True)
          for item in narrative.interview_focus),
    ]
    invalid = []
    for label, texts, ids, positive, alignment, cautious in checks:
        try:
            _check_section(texts, ids, facts=lookup, positive=positive,
                           alignment=alignment, cautious=cautious,
                           job_role=projection.role_title if alignment else None)
        except NarrativeV2ValidationError:
            invalid.append(label)
    return tuple(invalid)


def validation_error_summary_v2(
    narrative: RecruiterNarrativeV2, *, projection: NarrativeProjection,
) -> dict[str, object]:
    """In-memory, bounded diagnostics for Qwen; never log model prose."""
    lookup = {fact.fact_id: fact for fact in build_atomic_facts(projection)}
    sections = [
        ("decision_summary", (narrative.decision_summary.text,), narrative.decision_summary.fact_ids),
        ("why_review", (narrative.why_review.text,), narrative.why_review.fact_ids),
        *(("strength", (item.title, item.explanation), item.fact_ids) for item in narrative.strengths),
        *(("concern", (item.title, item.explanation, item.validation_question), item.fact_ids)
          for item in narrative.concerns),
        *(("interview_focus", (item.topic, item.question, item.reason), item.fact_ids)
          for item in narrative.interview_focus),
    ]
    invalid = set(invalid_narrative_v2_sections(narrative, projection=projection))
    diagnostics = []
    for label, texts, ids in sections:
        if label not in invalid:
            continue
        selected = [lookup[ident] for ident in ids if ident in lookup]
        permitted = {token.casefold() for fact in selected for token in _TECH_TOKEN.findall(fact.term)} | _GENERIC_ENGLISH
        if label in {"decision_summary", "why_review"} and any(
            projection.role_title.casefold() in text.casefold() for text in texts
        ):
            permitted |= {token.casefold() for token in _TECH_TOKEN.findall(projection.role_title)}
        observed = {token.casefold() for text in texts for token in _TECH_TOKEN.findall(text)}
        diagnostics.append({
            "section": label,
            "unsupported_terms": sorted(observed - permitted),
            "unsafe_claim": any(_UNSUPPORTED.search(text) for text in texts),
            "unsupported_scale": any(_invalid_scale(text, cautious=label in {"concern", "interview_focus"}) for text in texts),
            "unsupported_action": any(_invalid_action(text) for text in texts),
            "responsibility_violation": any(_invalid_responsibility(text, cautious=label in {"concern", "interview_focus"}) for text in texts),
            "unknown_fact_id": any(ident not in lookup for ident in ids),
        })
    return {"category": "claim_validation_failed", "invalid_sections": diagnostics}


__all__ = ["NarrativeV2ValidationError", "invalid_narrative_v2_sections", "validation_error_summary_v2", "validate_narrative_v2", "validate_narrative_v2_projection"]
