"""Trusted, read-only recruiter projection over a persisted explanation source."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from narrative_v2_comparison_fixture import build_comparison_group

from app.repositories.recruiter_narrative_repository import NarrativeSource
from app.services.explanation.contracts import candidate_output_fingerprint, evidence_bundle_fingerprint


class _SourceRepository:
    def __init__(self, source: NarrativeSource | None) -> None:
        self.source = source
        self.reads: list[int] = []

    async def load_source(self, explanation_id: int) -> NarrativeSource | None:
        self.reads.append(explanation_id)
        return self.source


def _source(group: dict, candidate_index: int = 0) -> NarrativeSource:
    output = group["outputs"][candidate_index]
    bundle = group["bundle"]
    return NarrativeSource(
        explanation_run_id="synthetic-explanation-run",
        match_explanation_id=42,
        bundle=bundle,
        output=output,
        candidate_output_fingerprint=candidate_output_fingerprint(output),
        evidence_bundle_fingerprint=evidence_bundle_fingerprint(bundle),
    )


def test_runtime_structured_brief_is_source_backed_and_does_not_mutate_ranking():
    from app.services.explanation.presentation.structured_service import RecruiterPropositionService

    group = build_comparison_group(1)
    repository = _SourceRepository(_source(group))
    before = group["ranking_before"]

    result = asyncio.run(RecruiterPropositionService(repository).get(42))

    assert repository.reads == [42]
    assert result.contract_version == "structured_recruiter_brief_v1"
    assert result.review_status == "TRUSTED_STRUCTURED"
    assert result.match_run_id == group["run"].run_id
    assert result.ranking_fingerprint == before["fingerprint"]
    assert result.candidate_id == group["outputs"][0].candidate_id
    assert result.result_rank == 1
    assert result.review_action.kind == "human_review_recommendation"
    assert result.why_review and result.technical_signals and result.unknowns and result.verification_targets
    for proposition in result.all_propositions():
        assert proposition.candidate_id == result.candidate_id
        assert proposition.result_rank == result.result_rank
        assert proposition.source_fact_ids
        assert proposition.evidence_refs
        assert all(
            ref.startswith(("candidate:1:", "job_requirement:"))
            for ref in proposition.evidence_refs
        )
    assert group["run"].result_fingerprint == before["fingerprint"]
    assert [item.candidate_id for item in group["run"].results] == before["order"]
    assert [item.ltr_score_raw for item in group["run"].results] == before["ltr_scores"]


def test_weak_overlap_keeps_conditional_review_strength():
    from app.services.explanation.presentation.structured_service import RecruiterPropositionService

    group = build_comparison_group(1)
    result = asyncio.run(RecruiterPropositionService(_SourceRepository(_source(group, 1))).get(42))
    assert result.result_rank == 2
    assert result.review_action.predicate == "consider_targeted_screen"
    assert result.review_action.modality == "recommendation"


def test_cross_candidate_explanation_is_rejected_fail_closed():
    from app.services.explanation.presentation.structured_service import (
        RecruiterPropositionService, RecruiterPropositionSourceInvalidError,
    )

    group = build_comparison_group(1)
    source = _source(group)
    foreign_output = source.output.model_copy(update={
        "candidate_id": group["outputs"][1].candidate_id,
        "result_rank": group["outputs"][1].result_rank,
    })
    contaminated = NarrativeSource(
        explanation_run_id=source.explanation_run_id,
        match_explanation_id=source.match_explanation_id,
        bundle=source.bundle,
        output=foreign_output,
        candidate_output_fingerprint=candidate_output_fingerprint(foreign_output),
        evidence_bundle_fingerprint=source.evidence_bundle_fingerprint,
    )
    with pytest.raises(RecruiterPropositionSourceInvalidError):
        asyncio.run(RecruiterPropositionService(_SourceRepository(contaminated)).get(42))


def test_missing_or_mismatched_source_does_not_return_a_brief():
    from app.services.explanation.presentation.structured_service import (
        RecruiterPropositionService, RecruiterPropositionSourceInvalidError,
        RecruiterPropositionSourceNotFoundError,
    )

    with pytest.raises(RecruiterPropositionSourceNotFoundError):
        asyncio.run(RecruiterPropositionService(_SourceRepository(None)).get(42))
    group = build_comparison_group(1)
    with pytest.raises(RecruiterPropositionSourceInvalidError):
        asyncio.run(RecruiterPropositionService(_SourceRepository(_source(group))).get(43))


def test_runtime_api_exposes_only_structured_source_backed_propositions():
    from app.api.dependencies import get_recruiter_proposition_service
    from app.main import create_app
    from app.services.explanation.presentation.structured_service import RecruiterPropositionService

    group = build_comparison_group(1)
    app = create_app()
    app.dependency_overrides[get_recruiter_proposition_service] = lambda: RecruiterPropositionService(
        _SourceRepository(_source(group))
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/match-explanations/42/recruiter-propositions")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["review_status"] == "TRUSTED_STRUCTURED"
    assert data["candidate_id"] == group["outputs"][0].candidate_id
    assert data["review_action"]["predicate"] == "prioritize_technical_review"
    assert data["why_review"] and data["technical_signals"]
    assert data["unknowns"] and data["verification_targets"]
    assert "narrative" not in data


def test_runtime_api_missing_source_returns_safe_error():
    from app.api.dependencies import get_recruiter_proposition_service
    from app.main import create_app
    from app.services.explanation.presentation.structured_service import RecruiterPropositionService

    app = create_app()
    app.dependency_overrides[get_recruiter_proposition_service] = lambda: RecruiterPropositionService(
        _SourceRepository(None)
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/match-explanations/42/recruiter-propositions")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "recruiter_proposition_source_not_found"
