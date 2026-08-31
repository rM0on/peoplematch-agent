from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Mapping, Sequence


BROAD_RELEVANCE_GRADE = 2
GAIN_BY_GRADE = {0: 0.0, 1: 1.0, 2: 3.0, 3: 7.0}


@dataclass(frozen=True)
class MetricValue:
    value: float | None
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if self.value is None and not self.exclusion_reason:
            raise ValueError("undefined metric requires an exclusion reason")
        if self.value is not None and not math.isfinite(self.value):
            raise ValueError("metric value must be finite")


@dataclass(frozen=True)
class MacroAggregate:
    mean: float
    total_queries: int
    eligible_queries: int
    excluded_queries: int
    excluded_reasons: dict[str, int]


def _validate_grades(grades: Mapping[str, int]) -> None:
    if any(grade not in GAIN_BY_GRADE for grade in grades.values()):
        raise ValueError("relevance grade must be one of 0, 1, 2, 3")


def retrieval_recall_at_k(
    ordered_candidate_ids: Sequence[str], grades: Mapping[str, int], *, k: int
) -> MetricValue:
    _validate_grades(grades)
    relevant = {candidate_id for candidate_id, grade in grades.items() if grade >= BROAD_RELEVANCE_GRADE}
    if not relevant:
        return MetricValue(None, "no_relevant_judgment")
    retrieved = set(ordered_candidate_ids[:k])
    return MetricValue(len(retrieved & relevant) / len(relevant))


def _condensed(ordered_candidate_ids: Sequence[str], grades: Mapping[str, int]) -> list[str]:
    if len(ordered_candidate_ids) != len(set(ordered_candidate_ids)):
        raise ValueError("ranking contains duplicate candidate IDs")
    return [candidate_id for candidate_id in ordered_candidate_ids if candidate_id in grades]


def judged_condensed_ndcg_at_k(
    ordered_candidate_ids: Sequence[str], grades: Mapping[str, int], *, k: int
) -> MetricValue:
    _validate_grades(grades)
    if not any(grade >= BROAD_RELEVANCE_GRADE for grade in grades.values()):
        return MetricValue(None, "no_relevant_judgment")
    condensed = _condensed(ordered_candidate_ids, grades)
    dcg = sum(GAIN_BY_GRADE[grades[candidate_id]] / math.log2(rank + 1) for rank, candidate_id in enumerate(condensed[:k], start=1))
    ideal_grades = sorted(grades.values(), reverse=True)[:k]
    idcg = sum(GAIN_BY_GRADE[grade] / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades, start=1))
    if idcg == 0:
        return MetricValue(None, "zero_ideal_gain")
    return MetricValue(dcg / idcg)


def judged_condensed_mrr_at_k(
    ordered_candidate_ids: Sequence[str], grades: Mapping[str, int], *, k: int
) -> MetricValue:
    _validate_grades(grades)
    if not any(grade >= BROAD_RELEVANCE_GRADE for grade in grades.values()):
        return MetricValue(None, "no_relevant_judgment")
    condensed = _condensed(ordered_candidate_ids, grades)
    for rank, candidate_id in enumerate(condensed[:k], start=1):
        if grades[candidate_id] >= BROAD_RELEVANCE_GRADE:
            return MetricValue(1.0 / rank)
    return MetricValue(0.0)


def judged_count_at_k(ordered_candidate_ids: Sequence[str], grades: Mapping[str, int], *, k: int) -> int:
    return sum(candidate_id in grades for candidate_id in ordered_candidate_ids[:k])


def judged_relevant_count_at_k(ordered_candidate_ids: Sequence[str], grades: Mapping[str, int], *, k: int) -> int:
    return sum(grades.get(candidate_id, -1) >= BROAD_RELEVANCE_GRADE for candidate_id in ordered_candidate_ids[:k])


def explicit_pairwise_accuracy(scores: Mapping[str, float], pairs: Sequence[tuple[str, str]]) -> MetricValue:
    if not pairs:
        return MetricValue(None, "no_explicit_pairwise_judgment")
    points = 0.0
    for winner, loser in pairs:
        if winner not in scores or loser not in scores:
            raise ValueError("explicit pairwise candidate has a missing score")
        winner_score, loser_score = float(scores[winner]), float(scores[loser])
        if not math.isfinite(winner_score) or not math.isfinite(loser_score):
            raise ValueError("pairwise scores must be finite")
        points += 1.0 if winner_score > loser_score else 0.5 if winner_score == loser_score else 0.0
    return MetricValue(points / len(pairs))


def macro_average(per_query: Mapping[str, MetricValue]) -> MacroAggregate:
    values = [item.value for item in per_query.values() if item.value is not None]
    if not values:
        raise ValueError("metric has an empty eligible query set")
    reasons = Counter(item.exclusion_reason for item in per_query.values() if item.value is None)
    return MacroAggregate(
        mean=sum(values) / len(values),
        total_queries=len(per_query),
        eligible_queries=len(values),
        excluded_queries=len(per_query) - len(values),
        excluded_reasons={str(key): count for key, count in sorted(reasons.items())},
    )


def unsupported_standard_precision_at_k() -> None:
    raise ValueError("standard Precision@K is unsupported under incomplete judgments")
