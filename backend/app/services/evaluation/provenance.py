from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.services.evaluation.errors import EvaluationIntegrityError
from app.services.match_runs.contracts import canonical_fingerprint


class PoolProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str
    candidate_universe: str
    expected_candidate_ids: tuple[str, ...]
    source_retrieval_strategy: str
    retrieval_config_fingerprint: str
    requested_pool_depth: int
    ordered_candidate_ids: tuple[str, ...]
    sorted_unique_candidate_ids: tuple[str, ...]
    returned_count: int
    eligible_count: int
    filters: tuple[str, ...]
    index_state: str
    index_fingerprint: str
    ranking_strategy: str
    rerank_depth: int
    score_semantics: str
    dataset_fingerprint: str
    feature_fingerprint: Optional[str] = None
    model_fingerprint: Optional[str] = None
    ce_fingerprint: Optional[str] = None
    pool_fingerprint: str
    order_fingerprint: str


def build_pool_provenance(
    query_id: str,
    expected_candidate_ids: Sequence[str],
    ordered_candidate_ids: Sequence[str],
    *,
    source_retrieval_strategy: str = "hybrid_rrf_v4",
    retrieval_config_fingerprint: str = "unspecified_test_fixture",
    requested_pool_depth: Optional[int] = None,
    eligible_count: Optional[int] = None,
    filters: Sequence[str] = (),
    index_state: str = "fixture",
    index_fingerprint: str = "unspecified_test_fixture",
    ranking_strategy: str = "fixture",
    rerank_depth: Optional[int] = None,
    score_semantics: str = "fixture_score",
    dataset_fingerprint: str = "unspecified_test_fixture",
    feature_fingerprint: Optional[str] = None,
    model_fingerprint: Optional[str] = None,
    ce_fingerprint: Optional[str] = None,
) -> PoolProvenance:
    expected = tuple(sorted(expected_candidate_ids))
    ordered = tuple(ordered_candidate_ids)
    if len(expected) != len(set(expected)):
        raise EvaluationIntegrityError("expected pool contains duplicate Candidate IDs")
    if len(ordered) != len(set(ordered)):
        raise EvaluationIntegrityError("returned pool contains duplicate Candidate IDs")
    unknown = sorted(set(ordered) - set(expected))
    missing = sorted(set(expected) - set(ordered))
    if unknown:
        raise EvaluationIntegrityError("returned pool contains unknown Candidate IDs")
    if missing:
        raise EvaluationIntegrityError("returned pool is missing Candidate IDs")
    sorted_unique = tuple(sorted(set(ordered)))
    requested = requested_pool_depth if requested_pool_depth is not None else len(expected)
    eligible = eligible_count if eligible_count is not None else len(expected)
    rerank = rerank_depth if rerank_depth is not None else len(ordered)
    pool_contract = {
        "kind": "candidate_pool_set_v1", "query_id": query_id,
        "candidate_universe": "all_frozen_candidates", "candidate_ids": sorted_unique,
        "source_retrieval_strategy": source_retrieval_strategy,
        "retrieval_config_fingerprint": retrieval_config_fingerprint,
        "requested_pool_depth": requested, "returned_count": len(ordered),
        "eligible_count": eligible, "filters": list(filters),
        "index_state": index_state, "index_fingerprint": index_fingerprint,
        "dataset_fingerprint": dataset_fingerprint,
    }
    return PoolProvenance(
        query_id=query_id, candidate_universe="all_frozen_candidates",
        expected_candidate_ids=expected, source_retrieval_strategy=source_retrieval_strategy,
        retrieval_config_fingerprint=retrieval_config_fingerprint,
        requested_pool_depth=requested, ordered_candidate_ids=ordered,
        sorted_unique_candidate_ids=sorted_unique, returned_count=len(ordered),
        eligible_count=eligible, filters=tuple(filters), index_state=index_state,
        index_fingerprint=index_fingerprint, ranking_strategy=ranking_strategy,
        rerank_depth=rerank, score_semantics=score_semantics,
        dataset_fingerprint=dataset_fingerprint, feature_fingerprint=feature_fingerprint,
        model_fingerprint=model_fingerprint, ce_fingerprint=ce_fingerprint,
        pool_fingerprint=canonical_fingerprint(pool_contract),
        order_fingerprint=canonical_fingerprint({"kind": "candidate_order_v1", "query_id": query_id, "ranking_strategy": ranking_strategy, "candidate_ids": ordered}),
    )


def assert_comparable_orders(provenance_by_strategy: Mapping[str, PoolProvenance]) -> None:
    fingerprints = {item.pool_fingerprint for item in provenance_by_strategy.values()}
    if len(fingerprints) != 1:
        raise EvaluationIntegrityError("strategy pool fingerprint mismatch")


def condense_to_judged(ordered_candidate_ids: Sequence[str], judged_candidate_ids: set[str]) -> list[str]:
    if len(ordered_candidate_ids) != len(set(ordered_candidate_ids)):
        raise EvaluationIntegrityError("ranking contains duplicate Candidate IDs")
    condensed = [candidate_id for candidate_id in ordered_candidate_ids if candidate_id in judged_candidate_ids]
    missing = judged_candidate_ids - set(condensed)
    if missing:
        raise EvaluationIntegrityError("ranking is missing judged Candidate IDs")
    return condensed
