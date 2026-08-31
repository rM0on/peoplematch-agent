from __future__ import annotations

from types import SimpleNamespace


def _label(label_id: str, job: str, candidate: str, *, hard: bool = False, reasons=()):
    return SimpleNamespace(
        label_id=label_id, job_id=job, candidate_id=candidate, hard_negative=hard,
        mismatch_reasons=[SimpleNamespace(value=value) for value in reasons],
    )


def test_frozen_slice_registry_enforces_small_n_and_never_emits_ndcg() -> None:
    from app.services.evaluation.slices import evaluate_predeclared_slices

    labels = [
        _label("l1", "j1", "a", hard=True, reasons=("DIRECTION_MISMATCH",)),
        _label("l2", "j1", "b", reasons=()),
        _label("l3", "j2", "c", hard=True, reasons=("DIRECTION_MISMATCH",)),
    ]
    result = evaluate_predeclared_slices(
        labels=labels,
        query_ids=["j1", "j2"],
        orders_by_strategy={"hybrid_rrf_v4": {"j1": ["a", "b"], "j2": ["c"]}},
        high_overclaim_candidate_ids=set(),
    )
    hard = result["hard_negative_v1"]
    assert hard["member_count"] == 2
    assert hard["job_count"] == 2
    assert hard["aggregate_status"] == "SMALL_N"
    assert "ndcg" not in str(result).casefold()
