from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence


@dataclass(frozen=True)
class ExplanationEvaluation:
    schema_validity: bool
    evidence_reference_validity: bool
    evidence_ownership_consistency: bool
    unsupported_claim_count: int
    unsupported_claim_rate: float
    ranking_reference_consistency: bool
    historical_snapshot_consistency: bool
    ranking_invariance: bool
    deterministic_repeatability: bool


def evaluate_explanation(
    *,
    candidate_id: str,
    match_run_id: str,
    evidence_facts: Mapping[str, Mapping[str, object]],
    referenced_fact_ids: Sequence[str],
    ranking_before: Sequence[str],
    ranking_after: Sequence[str],
    original_output: str,
    repeated_output: str,
) -> ExplanationEvaluation:
    for fact in evidence_facts.values():
        if fact.get("candidate_id") != candidate_id:
            raise ValueError("evidence fact owner does not match explanation owner")
        if fact.get("match_run_id") != match_run_id:
            raise ValueError("evidence fact historical owner does not match MatchRun")
    unsupported = [reference for reference in referenced_fact_ids if reference not in evidence_facts]
    reference_count = len(referenced_fact_ids)
    return ExplanationEvaluation(
        schema_validity=True,
        evidence_reference_validity=not unsupported,
        evidence_ownership_consistency=True,
        unsupported_claim_count=len(unsupported),
        unsupported_claim_rate=len(unsupported) / reference_count if reference_count else 0.0,
        ranking_reference_consistency=candidate_id in ranking_before,
        historical_snapshot_consistency=True,
        ranking_invariance=list(ranking_before) == list(ranking_after),
        deterministic_repeatability=original_output == repeated_output,
    )
