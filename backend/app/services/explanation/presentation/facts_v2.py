from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.match_runs.contracts import canonical_fingerprint


FactKind = Literal["candidate_skill", "project_practice", "requirement_alignment", "open_requirement", "direction_inference"]


@dataclass(frozen=True)
class AtomicFactV2:
    fact_id: str
    kind: FactKind
    term: str
    evidence_refs: tuple[str, ...]
    allowed_inference: str


def _fact(kind: FactKind, term: str, refs: tuple[str, ...]) -> AtomicFactV2:
    return AtomicFactV2(
        fact_id="fact:" + canonical_fingerprint({"kind": kind, "term": term, "refs": refs})[:32],
        kind=kind,
        term=term,
        evidence_refs=refs,
        allowed_inference={
            "candidate_skill": "资料列出该技能；可归纳为相关技术方向并建议面试了解实践深度；不能推断能力深度、个人职责或项目结果",
            "project_practice": "项目记录涉及该技术；可归纳为相关应用实践，并建议面试询问设计与工程取舍；不能推断个人构建、开发、部署、优化等动作，也不能推断主导、规模或业绩",
            "requirement_alignment": "候选事实与岗位要求有直接技术词对应；可说明这一方向值得人工复核，不能断言完全胜任或直接录用",
            "open_requirement": "该岗位要求需要人工核实；可提出具体面试问题，不能断言候选人缺少这项能力",
            "direction_inference": "由多项已记录项目技术归纳出的技术方向；只允许方向关联，不允许推断个人职责、能力深度、规模或结果",
        }[kind],
    )


def _mentions(term: str, requirement: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(term.casefold())}(?![A-Za-z0-9])", requirement.casefold()) is not None


def build_atomic_facts(projection: NarrativeProjection) -> tuple[AtomicFactV2, ...]:
    """Create bounded claims from the already validated historical projection.

    A listed skill is not project ownership. A project technology means only
    project involvement, not personal responsibility, scale or outcome.
    """
    facts: dict[str, AtomicFactV2] = {}
    requirements = sorted(ref for ref in projection.positive_refs if ref.startswith("job_requirement:"))
    for ref in sorted(projection.positive_refs):
        if not ref.startswith("candidate:"):
            continue
        kind = ref.split(":", 3)[2]
        if kind == "project_evidence" and projection.verification_status.get(ref) not in {"available", "described"}:
            continue
        if kind not in {"skill", "project", "project_evidence"}:
            continue
        fact_kind: FactKind = "candidate_skill" if kind == "skill" else "project_practice"
        for term in projection.facts.get(ref, ())[:8]:
            if not term.strip():
                continue
            candidate_fact = _fact(fact_kind, term, (ref,))
            facts[candidate_fact.fact_id] = candidate_fact
            for requirement_ref in requirements:
                if any(_mentions(term, requirement) for requirement in projection.facts[requirement_ref]):
                    alignment = _fact("requirement_alignment", term, tuple(sorted((ref, requirement_ref))))
                    facts[alignment.fact_id] = alignment
    for ref in sorted(projection.risk_refs):
        if not ref.startswith("job_requirement:"):
            continue
        for term in projection.facts.get(ref, ())[:4]:
            gap = _fact("open_requirement", term, (ref,))
            facts[gap.fact_id] = gap
    return tuple(sorted(facts.values(), key=lambda fact: fact.fact_id))


def build_selected_requirement_verification_facts(projection: NarrativeProjection) -> tuple[AtomicFactV2, ...]:
    """Reuse V2's fact identity for selected JD requirements, without changing V2 output.

    Whether a requirement is still open is candidate-relative and is decided by
    the Proposition builder's observed alignments, not by this source helper.
    """
    facts = {
        fact.fact_id: fact
        for ref in projection.positive_refs
        if ref.startswith("job_requirement:") and ref in projection.facts
        for term in projection.facts[ref]
        if term.strip()
        for fact in (_fact("open_requirement", term, (ref,)),)
    }
    return tuple(sorted(facts.values(), key=lambda fact: fact.fact_id))


__all__ = ["AtomicFactV2", "build_atomic_facts", "build_selected_requirement_verification_facts"]
