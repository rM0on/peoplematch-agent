from __future__ import annotations

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.facts_v2 import AtomicFactV2, _fact, build_atomic_facts


_DIRECTION_TERMS = {
    "AI应用": frozenset({"ai agent", "rag", "llm application", "qdrant", "vector database"}),
    "推荐系统": frozenset({"lambdamart", "retrieval", "evaluation", "ranking", "feature engineering"}),
    "后端工程": frozenset({"fastapi", "postgresql", "docker", "python"}),
}


def build_atomic_facts_v2_1(projection: NarrativeProjection) -> tuple[AtomicFactV2, ...]:
    """Add narrow technical-direction relations; never infer ownership or impact."""
    facts = list(build_atomic_facts(projection))
    projects = [fact for fact in facts if fact.kind == "project_practice"]
    by_term = {fact.term.casefold(): fact for fact in projects}
    for direction, terms in _DIRECTION_TERMS.items():
        matching = [by_term[term] for term in sorted(terms & by_term.keys())]
        if len(matching) < 2 or (direction == "后端工程" and not any(
            fact.term.casefold() in {"fastapi", "postgresql"} for fact in matching
        )):
            continue
        refs = tuple(sorted({ref for fact in matching for ref in fact.evidence_refs}))
        facts.append(_fact("direction_inference", direction, refs))
    return tuple(sorted(facts, key=lambda fact: fact.fact_id))


__all__ = ["build_atomic_facts_v2_1"]
