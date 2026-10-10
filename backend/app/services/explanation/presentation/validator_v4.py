"""Fail-closed validation of generated prose against deterministic recruiter claims."""

from __future__ import annotations

import re

from app.services.explanation.presentation.claims_v4 import (
    RecruiterClaimGraphV4, build_recruiter_claim_graph_v4,
)
from app.services.explanation.presentation.contracts_v4 import RecruiterNarrativeV4
from app.services.explanation.presentation.facts_v3 import _ALIASES, _concepts


class NarrativeV4ValidationError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("Recruiter narrative V4 claim validation failed")


_OWNERSHIP = re.compile(
    r"(?:候选人|其|本人|他|她)[^。；？?]{0,30}?(?:负责|主导|承担|参与了|参与过|建设|搭建|构建了|设计了|开发了|实现了|交付|上线)|"
    r"(?:led|owned|built|delivered)\s+(?:an?\s+)?(?:enterprise|production|platform|system)", re.I,
)
_SCALE = re.compile(r"企业级|生产级|大规模|百万|千万|亿级|enterprise[- ]scale|production[- ]scale", re.I)
_OUTCOME = re.compile(r"(?:提升|提高|增长|降低|节省|改善)[^。；？?]{0,18}(?:\d|%|百分之)|\d+\s*%|"
                      r"(?:improved|increased|reduced)\s+\w+\s+by\s+\d+", re.I)
_ABILITY = re.compile(r"(?:候选人|其|本人|他|她)[^。；？?]{0,32}"
                      r"(?:精通|专家|胜任|掌握|(?:具备|拥有)[^。；？?]{0,18}(?:丰富|资深|专家|能力|经验))|"
                      r"高度匹配|完全符合|一定适合|已经具备岗位所需", re.I)
_DECISION = re.compile(r"推荐录用|建议(?:直接)?录用|直接进入终面|无需面试|录用概率|匹配百分比|"
                       r"大概率通过|自动录用", re.I)
_INTERVIEW = re.compile(r"面试|下一轮|复核|确认|核实|了解|询问|验证|待确认|尚需")
_INTERVIEW_DIRECTIVE = re.compile(
    r"^(?:针对[^，。；]{1,24}[，,]\s*)?请?(?:探讨|具体描述)"
)
_REVIEW = re.compile(r"建议|可(?:优先)?安排|人工复核|人工评估")
_MATERIAL_UNKNOWN = re.compile(
    r"(?:材料|资料)[^。；？?]{0,12}(?:尚无法|尚不能|仍无法|无法|未能|未)"
    r"[^。；？?]{0,12}(?:确认|确定|说明|覆盖)"
)
_QUESTIONED_OWNERSHIP = re.compile(
    r"是否(?:曾经|实际|直接)?(?:负责|主导|建设|搭建|构建|设计|开发|实现|交付|上线)"
)
_ROLE_VERB_END = re.compile(
    r"(?:负责|主导|承担|参与了|参与过|建设|搭建|构建了|设计了|开发了|实现了|交付|上线)$"
)
_ROLE_EXISTENCE_QUESTION = re.compile(r"是否(?:具有|具备|拥有)[^，。；？?]{0,8}$")
_ROLE_ALTERNATIVE = re.compile(
    r"[^。；？?]{0,24}还是\s*(?:仅)?(?:参与|负责|承担|主导|实现|设计)"
)
_ROLE_VERIFICATION_CUE = re.compile(r"确认|核实|判断|了解")
_ROLE_SCOPE_QUESTION = re.compile(r"^(?:过)?(?:哪些|什么|哪一|哪项|哪部分)")
_FOLLOWING_ROLE_ASSERTION = re.compile(
    r"(?:，|,|但|且|并且|并|同时)[^。；？?]{0,8}(?:候选人|其)?"
    r"[^。；？?]{0,4}(?:负责了|主导了|承担了|参与了)"
)
_QUESTIONED_ABILITY = re.compile(r"是否(?:已经|真正)?(?:具备|拥有|掌握|精通|胜任)")
_ABILITY_AFTER_QUESTION = re.compile(
    r"是否(?:已经|真正)?(?:具备|拥有|掌握|精通|胜任)"
    r"[^。；？?]{0,40}(?:并且|同时|并|且)\s*(?:具备|拥有|掌握|精通|胜任)"
)
_RECRUITER_ASSESSMENT = re.compile(r"评估(?:其|候选人)是否")
_TECHNICAL_EVALUATION = re.compile(r"离线评估|模型评估|评估方法|评估体系|evaluation", re.I)
_TECH_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9.+#/-]*(?![A-Za-z0-9])")
_GENERIC = {"ai", "llm", "jd", "api", "rag", "agent", "candidate", "review", "engineer"}


def _contains_assertion(text: str, pattern: re.Pattern[str], question: re.Pattern[str]) -> bool:
    """A question about a fact is not an assertion that the fact is true."""
    return any(not question.search(match.group()) for match in pattern.finditer(text))


def _responsibility_is_verification(text: str, section: str, match: re.Match[str]) -> bool:
    """Only an explicit question or unresolved role alternative can suspend a duty claim."""
    if not (section.startswith("risks") or section.startswith("interview_focus")):
        return False
    action = _ROLE_VERB_END.search(match.group())
    if action is None:  # English ownership and unrecognized syntax remain assertions.
        return False
    action_start = match.start() + action.start()
    clause_start = max(text.rfind(char, 0, action_start) for char in "。；！？?") + 1
    clause_end_candidates = [text.find(char, match.end()) for char in "。；！？?"]
    clause_end = min((end for end in clause_end_candidates if end >= 0), default=len(text))
    before = text[clause_start:action_start]
    after = text[match.end():clause_end]
    if _QUESTIONED_OWNERSHIP.search(match.group()) or _ROLE_EXISTENCE_QUESTION.search(before):
        return True
    if not _ROLE_VERIFICATION_CUE.search(before):
        return False
    if action.group() == "主导" and before.endswith("是") and _ROLE_ALTERNATIVE.search(after):
        return True
    if action.group() == "承担" and after.startswith("的是") and _ROLE_ALTERNATIVE.search(after):
        return True
    if action.group() == "负责" and _ROLE_SCOPE_QUESTION.search(after):
        return True
    return False


def _narrative_concepts(text: str) -> set[str]:
    concepts = set(_concepts((text,)))
    # "评估其是否..." describes the recruiter's action, not offline evaluation evidence.
    if (_RECRUITER_ASSESSMENT.search(text) and not _TECHNICAL_EVALUATION.search(text)):
        concepts.discard("evaluation")
    return concepts


def diagnose_narrative_v4(narrative: RecruiterNarrativeV4, *, graph: RecruiterClaimGraphV4) -> dict[str, str]:
    """Validate claim provenance first, then reject prose outside its semantic scope.

    This does not compare generated sentences with raw evidence strings. Unknown
    technical terms and unscoped factual conclusions fail closed.
    """
    if graph != build_recruiter_claim_graph_v4(graph.fact_graph):
        return {"graph": "noncanonical_claim_graph"}
    if narrative.candidate_id != graph.candidate_id or narrative.result_rank != graph.result_rank:
        return {"identity": "candidate_mismatch"}
    lookup = {claim.claim_id: claim for claim in graph.claims}
    sections = [
        ("summary", narrative.summary, {"review_recommendation"}),
        *((f"strengths[{i}]", item, {"technical_alignment", "skill_requirement_match"})
          for i, item in enumerate(narrative.strengths)),
        *((f"risks[{i}]", item, {"project_depth_validation", "interview_focus"})
          for i, item in enumerate(narrative.risks)),
        *((f"interview_focus[{i}]", item, {"interview_focus", "project_depth_validation"})
          for i, item in enumerate(narrative.interview_focus)),
    ]
    invalid: dict[str, str] = {}
    for section, paragraph, allowed_types in sections:
        refs = paragraph.claim_refs
        if len(refs) != len(set(refs)) or any(ref not in lookup for ref in refs):
            invalid[section] = "unknown_or_duplicate_claim_ref"
            continue
        selected = [lookup[ref] for ref in refs]
        if any(claim.candidate_id != graph.candidate_id or claim.claim_type not in allowed_types
               for claim in selected):
            invalid[section] = "claim_type_or_owner_mismatch"
            continue
        text = paragraph.text
        responsibility_matches = tuple(_OWNERSHIP.finditer(text))
        responsibility_verification = bool(responsibility_matches) and all(
            _responsibility_is_verification(text, section, match)
            for match in responsibility_matches
        )
        if (_DECISION.search(text) or _FOLLOWING_ROLE_ASSERTION.search(text)
                or (responsibility_matches and not responsibility_verification)
                or _SCALE.search(text) or _OUTCOME.search(text)):
            invalid[section] = "forbidden_responsibility_scale_outcome_or_hiring_decision"
            continue
        if (_contains_assertion(text, _ABILITY, _QUESTIONED_ABILITY)
                or _ABILITY_AFTER_QUESTION.search(text)):
            invalid[section] = "unsupported_ability_conclusion"
            continue
        if section == "summary" and not _REVIEW.search(text):
            invalid[section] = "review_action_missing"
            continue
        if ((section.startswith("risks") and not (
                _INTERVIEW.search(text) or _MATERIAL_UNKNOWN.search(text)
                or responsibility_verification))
                or (section.startswith("interview_focus")
                    and not (_INTERVIEW.search(text) or _INTERVIEW_DIRECTIVE.search(text)))):
            invalid[section] = "verification_modality_missing"
            continue
        if section.startswith("strengths") and not _narrative_concepts(text):
            invalid[section] = "technical_observation_missing"
            continue
        allowed_concepts = {concept for claim in selected for concept in claim.concepts}
        mentioned = _narrative_concepts(text)
        if mentioned - allowed_concepts:
            invalid[section] = "technical_concept_outside_claim_scope"
            continue
        known_aliases = {alias.casefold() for aliases in _ALIASES.values() for alias in aliases}
        allowed_tokens = {token.casefold() for concept in allowed_concepts
                          for token in _TECH_TOKEN.findall(concept)} | _GENERIC
        allowed_tokens |= {token.casefold() for alias in known_aliases
                           if alias in text.casefold() for token in _TECH_TOKEN.findall(alias)}
        tokens = {token.casefold() for token in _TECH_TOKEN.findall(text)}
        if tokens - allowed_tokens:
            invalid[section] = "unrecognized_technical_surface"
            continue
        if section.startswith("strengths") and not (mentioned & allowed_concepts):
            invalid[section] = "missing_cited_technical_direction"
    return invalid


def validate_narrative_v4(narrative: RecruiterNarrativeV4, *, graph: RecruiterClaimGraphV4) -> None:
    invalid = diagnose_narrative_v4(narrative, graph=graph)
    if invalid:
        raise NarrativeV4ValidationError(next(iter(invalid.values())))


__all__ = ["NarrativeV4ValidationError", "diagnose_narrative_v4", "validate_narrative_v4"]
