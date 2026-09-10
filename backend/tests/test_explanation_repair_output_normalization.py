from __future__ import annotations

import asyncio
import json

import pytest

from app.services.explanation.generation.mock_provider import (
    DeterministicExplanationProvider,
)
from test_explanation_evidence_engine import _run


def _pipeline():
    from app.services.explanation.generation.pipeline import ExplanationGenerationPipeline

    return ExplanationGenerationPipeline(max_output_tokens=512)


def _prepared_and_payload():
    pipeline = _pipeline()
    run = _run()
    prepared = pipeline.prepare(run, requested_top_k=1)
    response = asyncio.run(
        DeterministicExplanationProvider().generate(prepared.initial_request)
    )
    return pipeline, run, prepared, json.loads(response.content)


def _normalize(payload: dict) -> str:
    from app.services.explanation.generation.output_normalization import (
        normalize_explanation_repair_output,
    )

    return normalize_explanation_repair_output(json.dumps(payload))


def test_repair_normalizer_canonicalizes_only_existing_evidence_reference_lists() -> None:
    payload = {
        "contract_version": "explanation_plan_v1",
        "candidates": [
            {
                "candidate_ref": "candidate_0001",
                "result_rank": 1,
                "summary": {
                    "template_key": "recorded_match_summary",
                    "evidence_refs": ["ref_0002", "ref_0001", "ref_0002"],
                },
                "match_reasons": [
                    {
                        "category": "skill_fit",
                        "template_key": "skill_fit_recorded",
                        "evidence_refs": ["ref_0002", "ref_0001", "ref_0002"],
                    }
                ],
                "risk_points": [],
                "interview_question_operations": [],
                "why_not_top1": None,
                "rewrite_operations": [],
            }
        ],
    }

    normalized = json.loads(_normalize(payload))

    candidate = normalized["candidates"][0]
    assert candidate["summary"]["evidence_refs"] == ["ref_0001", "ref_0002"]
    assert candidate["match_reasons"][0]["evidence_refs"] == [
        "ref_0001",
        "ref_0002",
    ]
    assert normalized["contract_version"] == payload["contract_version"]


def test_repair_normalizer_preserves_unknown_reference_for_grounding_rejection() -> None:
    from app.services.explanation.generation.errors import ExplanationGroundingError

    pipeline, _run_value, prepared, payload = _prepared_and_payload()
    payload["candidates"][0]["summary"]["evidence_refs"] = ["ref_9999"]

    with pytest.raises(ExplanationGroundingError):
        pipeline.validate_and_render(_normalize(payload), prepared)


def test_repair_normalizer_does_not_turn_hallucinated_evidence_into_grounded_fact() -> None:
    from app.services.explanation.generation.errors import ExplanationGroundingError

    pipeline, _run_value, prepared, payload = _prepared_and_payload()
    payload["candidates"][0]["match_reasons"][0]["evidence_refs"] = ["ref_9999"]
    payload["candidates"][0]["summary"]["evidence_refs"] = ["ref_9999"]

    with pytest.raises(ExplanationGroundingError):
        pipeline.validate_and_render(_normalize(payload), prepared)


def test_repair_normalization_preserves_ranking_fingerprints_order_and_scores() -> None:
    pipeline, run, prepared, payload = _prepared_and_payload()
    selected_refs = sorted(
        {
            ref
            for selection in (
                payload["candidates"][0]["match_reasons"]
                + payload["candidates"][0]["risk_points"]
            )
            for ref in selection["evidence_refs"]
        }
    )
    assert selected_refs
    payload["candidates"][0]["summary"]["evidence_refs"] = (
        list(reversed(selected_refs)) + [selected_refs[0]]
    )
    before = (
        run.ranking_input_fingerprint,
        run.result_fingerprint,
        [(item.candidate_id, item.result_rank, item.ltr_score_raw) for item in run.results],
    )

    pipeline.validate_and_render(_normalize(payload), prepared)

    after = (
        run.ranking_input_fingerprint,
        run.result_fingerprint,
        [(item.candidate_id, item.result_rank, item.ltr_score_raw) for item in run.results],
    )
    assert after == before
