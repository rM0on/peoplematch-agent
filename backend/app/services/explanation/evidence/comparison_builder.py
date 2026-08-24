from __future__ import annotations

from app.services.explanation.evidence.contracts import (
    CandidateFactSet,
    ComparisonItem,
    Top1ComparisonFact,
)


_COMPARISON_NAMES = (
    "retrieval_rank",
    "skill_fit_score",
    "project_evidence_score",
    "role_direction_score",
    "ai_tool_score",
    "location_score",
    "seniority_score",
    "ltr_rank",
    "ltr_score_raw",
    "cross_encoder_rank",
    "cross_encoder_score_raw",
    "requirement_evidence_coverage",
)


def _direction(value, top1_value) -> str:
    if value is None or top1_value is None:
        return "unavailable"
    if value > top1_value:
        return "higher"
    if value < top1_value:
        return "lower"
    return "equal"


class Top1ComparisonBuilder:
    def build(self, bundle) -> list[CandidateFactSet]:
        top1 = bundle.candidates[0]
        top1_facts = {
            fact.name: fact
            for fact in top1.facts
            if fact.kind.value == "ranking" or fact.kind.value == "feature" or fact.kind.value == "retrieval"
        }
        output: list[CandidateFactSet] = []
        for candidate in bundle.candidates:
            comparison = None
            if candidate.result_rank > 1:
                candidate_facts = {
                    fact.name: fact
                    for fact in candidate.facts
                    if fact.kind.value == "ranking" or fact.kind.value == "feature" or fact.kind.value == "retrieval"
                }
                comparison_facts = {
                    fact.name: fact
                    for fact in candidate.facts
                    if fact.kind.value == "comparison"
                }
                diagnostic_facts = {
                    fact.name: fact
                    for fact in candidate.facts
                    if fact.kind.value == "diagnostic"
                }
                items: list[ComparisonItem] = []
                for name in _COMPARISON_NAMES:
                    # ``retrieval_rank`` is an allowed Phase 9.2 comparison
                    # dimension, but the frozen Phase 9.1 internal EvidenceFact
                    # allowlist does not define a separate comparison fact for
                    # it. Reuse the persisted retrieval fact directly; all
                    # other dimensions use the explicit generated comparison
                    # fact.
                    if name == "retrieval_rank":
                        source = candidate_facts.get(name)
                    elif name == "requirement_evidence_coverage":
                        source = diagnostic_facts.get("evidence_supported_requirement_ids")
                    else:
                        source = comparison_facts.get(name)
                    if source is None:
                        continue
                    value = source.value
                    top_value = top1_facts.get(name)
                    if name == "requirement_evidence_coverage":
                        value = len(value or [])
                        top_diagnostic = next(
                            (
                                fact
                                for fact in top1.facts
                                if fact.kind.value == "diagnostic"
                                and fact.name == "evidence_supported_requirement_ids"
                            ),
                            None,
                        )
                        top_value = len(top_diagnostic.value or []) if top_diagnostic else None
                    else:
                        top_value = top_value.value if top_value is not None else None
                    items.append(
                        ComparisonItem(
                            dimension=name,
                            direction=_direction(
                                value,
                                top_value,
                            ),
                            evidence_refs=[source.evidence_id],
                        )
                    )
                comparison = Top1ComparisonFact(
                    candidate_id=candidate.candidate_id,
                    result_rank=candidate.result_rank,
                    top1_candidate_id=top1.candidate_id,
                    comparisons=items,
                )
            output.append(
                CandidateFactSet(
                    candidate_id=candidate.candidate_id,
                    result_rank=candidate.result_rank,
                    match_reasons=[],
                    ranking_context=[],
                    risks=[],
                    missing_requirements=[],
                    comparison=comparison,
                )
            )
        return output


__all__ = ["Top1ComparisonBuilder"]
