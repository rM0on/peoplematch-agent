from __future__ import annotations

import re

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.contracts import NarrativeStatement


def _requirement_mentions(term: str, requirement: str) -> bool:
    return re.search(
        rf"(?<![A-Za-z0-9]){re.escape(term.casefold())}(?![A-Za-z0-9])",
        requirement.casefold(),
    ) is not None


def approved_copy(projection: NarrativeProjection) -> dict[str, list[NarrativeStatement]]:
    """Closed, source-derived Chinese copy choices for the LLM to select and order.

    This intentionally limits free-form prose. A syntactically valid citation alone
    cannot prove an arbitrary Chinese assertion; unknown sentences fail closed.
    """

    sections: dict[str, list[NarrativeStatement]] = {
        "candidate_summary": [],
        "recommendation_summary": [],
        "strengths": [],
        "risks": [],
        "interview_focus": [],
    }
    seen: dict[str, set[tuple[str, tuple[str, ...]]]] = {key: set() for key in sections}

    def add(section: str, text: str, refs: list[str]) -> None:
        links = sorted(set(refs))
        key = (text, tuple(links))
        if key not in seen[section] and len(text) <= 280:
            sections[section].append(NarrativeStatement(text=text, evidence_links=links))
            seen[section].add(key)

    candidates = sorted(ref for ref in projection.positive_refs if ref.startswith("candidate:"))[:8]
    requirements = sorted(ref for ref in projection.positive_refs if ref.startswith("job_requirement:"))[:6]
    requirement_terms = [
        item for ref in requirements for item in projection.facts[ref][:3]
    ]
    def display_term(raw_term: str) -> str:
        return next(
            (item for item in requirement_terms if item.casefold() == raw_term.casefold()),
            raw_term,
        )

    for ref in candidates:
        kind = ref.split(":", 3)[2]
        if kind == "project_evidence" and projection.verification_status.get(ref) not in {"available", "described"}:
            continue
        if kind == "project" and {"ai agent", "rag"} <= {term.casefold() for term in projection.facts[ref]}:
            add(
                "candidate_summary",
                "候选人在 AI Agent 与 RAG 应用方向已有项目实践，可进一步验证系统设计能力。",
                [ref],
            )
        for raw_term in projection.facts[ref][:4]:
            term = display_term(raw_term)
            if kind == "skill":
                add("candidate_summary", f"候选人资料列有 {term} 技能。", [ref])
                add("strengths", f"候选人资料列有 {term} 技能。", [ref])
            elif kind == "project":
                add("candidate_summary", f"候选人有 {term} 项目实践。", [ref])
                add("strengths", f"项目记录涉及 {term}。", [ref])
                add("strengths", f"候选人有 {term} 项目实践。", [ref])
                matching_skill = next(
                    (skill_ref for skill_ref in candidates
                     if skill_ref.split(":", 3)[2] == "skill"
                     and any(term.casefold() == skill_term.casefold()
                             for skill_term in projection.facts[skill_ref])),
                    None,
                )
                if matching_skill:
                    add("candidate_summary", f"候选人有 {term} 项目实践。", [matching_skill, ref])
            elif kind == "project_evidence":
                status = projection.verification_status.get(ref)
                if status == "available":
                    add("strengths", f"已记录的项目证据支持 {term}。", [ref])
                elif status == "described":
                    add("strengths", f"材料描述的项目证据涉及 {term}。", [ref])
            for requirement_ref in requirements:
                for requirement in projection.facts[requirement_ref][:3]:
                    if _requirement_mentions(term, requirement):
                        add(
                            "recommendation_summary",
                            f"{term} 与岗位要求有关，建议进一步技术复核。",
                            [ref, requirement_ref],
                        )
                        add(
                            "recommendation_summary",
                            f"资料中的 {term} 与岗位要求中的 {requirement} 直接对应，建议在技术面进一步复核实践深度。",
                            [ref, requirement_ref],
                        )

    for ref in sorted(projection.risk_refs)[:8]:
        for raw_term in projection.facts[ref][:4]:
            term = display_term(raw_term)
            if ref.startswith("job_requirement:"):
                add("risks", f"关于 {term} 的经历仍需进一步确认。", [ref])
            elif ref.startswith("candidate:"):
                add("risks", f"关于 {term} 的实践深度，建议面试进一步核实。", [ref])
    for ref in sorted(projection.interview_refs)[:12]:
        for raw_term in projection.facts[ref][:4]:
            term = display_term(raw_term)
            if ":project:" in ref or ":project_evidence:" in ref:
                add("interview_focus", f"建议面试确认 {term} 项目设计过程。", [ref])
                add("interview_focus", f"建议面试了解 {term} 的实际使用经历。", [ref])
            elif ":skill:" in ref or ref.startswith("job_requirement:"):
                add("interview_focus", f"建议面试确认 {term} 的实践情况。", [ref])
    return sections


__all__ = ["approved_copy"]
