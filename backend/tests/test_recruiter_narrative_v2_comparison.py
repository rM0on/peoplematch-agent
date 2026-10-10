from __future__ import annotations

import pytest


@pytest.mark.parametrize("group", (1, 2, 3))
def test_synthetic_comparison_pairs_have_distinct_evidence_and_unchanged_ranking(group):
    from narrative_v2_comparison_fixture import build_comparison_group

    case = build_comparison_group(group)
    first, second = case["projections"]
    assert first.candidate_id != second.candidate_id
    assert first.facts != second.facts
    assert case["run"].result_fingerprint == case["ranking_before"]["fingerprint"]
    assert [item.candidate_id for item in case["run"].results] == case["ranking_before"]["order"]
    assert [item.ltr_score_raw for item in case["run"].results] == case["ranking_before"]["ltr_scores"]
