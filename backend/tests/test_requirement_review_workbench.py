"""V5: a read-only requirement view over canonical persisted explanation evidence."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from narrative_v2_comparison_fixture import build_comparison_group
from test_recruiter_proposition_runtime import _SourceRepository, _source

from app.services.explanation.presentation.structured_service import RecruiterPropositionService


def _service(group=None, *, source=None):
    from app.services.requirement_review.service import RequirementReviewService

    group = group or build_comparison_group(1)
    repository = _SourceRepository(source if source is not None else _source(group))
    return RequirementReviewService(repository, RecruiterPropositionService(repository)), repository, group


def test_all_job_requirements_are_ordered_and_source_backed_without_new_skill_claims():
    service, repository, group = _service()
    before = group["ranking_before"]

    result = asyncio.run(service.get(42))

    assert repository.reads == [42, 42]
    assert result.contract_version == "requirement_review_v1"
    assert result.candidate_id == group["outputs"][0].candidate_id
    assert result.role_title == group["bundle"].job.role_title
    assert [row.requirement_id for row in result.requirements] == [
        item.requirement_id for item in group["bundle"].job.requirements
    ]
    assert [row.priority for row in result.requirements] == [
        item.priority.value for item in group["bundle"].job.requirements
    ]
    assert result.requirements[0].text == group["bundle"].job.requirements[0].text
    assert result.requirements[0].diagnostic_status == "not_assessed"
    assert result.requirements[0].evidence_status == "not_assessed"
    assert any(item.kind == "technical_alignment" for item in result.requirements[0].propositions)
    assert result.requirements[3].propositions == ()
    assert result.requirements[4].evidence_status == "available"
    assert result.requirements[4].source_refs == ("job_requirement:req_python",)
    assert all(len(item.job_requirement_refs) == 1 for row in result.requirements for item in row.propositions)
    assert any(len(item.job_requirement_refs) > 1 for item in result.cross_requirement_propositions)
    project = next(item for item in result.source_descriptors if item.evidence_ref.startswith("candidate:1:project:"))
    assert project.source_kind == "historical_project"
    assert "fastapi" in project.description
    assert "project_001" in project.description
    assert all(item.evidence_ref in {ref for proposition in result.cross_requirement_propositions for ref in proposition.evidence_refs} | {
        ref for row in result.requirements for proposition in row.propositions for ref in proposition.evidence_refs
    } for item in result.source_descriptors)
    assert group["run"].result_fingerprint == before["fingerprint"]
    assert [item.candidate_id for item in group["run"].results] == before["order"]
    assert [item.ltr_score_raw for item in group["run"].results] == before["ltr_scores"]


def test_missing_and_mismatched_source_fail_closed():
    from app.services.requirement_review.service import RequirementReviewInvalidError, RequirementReviewNotFoundError, RequirementReviewService

    group = build_comparison_group(1)
    missing = _SourceRepository(None)
    with pytest.raises(RequirementReviewNotFoundError):
        asyncio.run(RequirementReviewService(missing, RecruiterPropositionService(missing)).get(42))
    service, _, _ = _service(group)
    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(service.get(43))


def test_foreign_or_unknown_requirement_proposition_fails_closed():
    from app.services.requirement_review.service import RequirementReviewInvalidError, RequirementReviewService

    group = build_comparison_group(1)
    repository = _SourceRepository(_source(group))
    canonical = asyncio.run(RecruiterPropositionService(repository).get(42))
    base = canonical.why_review[0]
    contaminated = base.model_copy(update={"job_requirement_refs": ("job_requirement:not_in_job",)})
    invalid_brief = canonical.model_copy(update={"why_review": (contaminated,) + canonical.why_review[1:]})

    class InvalidPropositions:
        async def get(self, _):
            return invalid_brief

    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(repository, InvalidPropositions()).get(42))
    extra_job_ref = base.model_copy(update={"evidence_refs": (*base.evidence_refs, "job_requirement:not_in_job")})
    invalid_brief = canonical.model_copy(update={"why_review": (extra_job_ref,) + canonical.why_review[1:]})
    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(repository, InvalidPropositions()).get(42))

    unknown_namespace = base.model_copy(update={"evidence_refs": (*base.evidence_refs, "unscoped:source")})
    invalid_brief = canonical.model_copy(update={"why_review": (unknown_namespace,) + canonical.why_review[1:]})
    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(repository, InvalidPropositions()).get(42))

    duplicate_source = base.model_copy(update={"evidence_refs": (*base.evidence_refs, base.evidence_refs[0])})
    invalid_brief = canonical.model_copy(update={"why_review": (duplicate_source,) + canonical.why_review[1:]})
    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(repository, InvalidPropositions()).get(42))

    missing_historical_ref = base.model_copy(update={"evidence_refs": ("candidate:1:project:invented", *base.evidence_refs)})
    invalid_brief = canonical.model_copy(update={"why_review": (missing_historical_ref,) + canonical.why_review[1:]})
    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(repository, InvalidPropositions()).get(42))

    foreign = base.model_copy(update={"candidate_id": "foreign_candidate"})
    invalid_brief = canonical.model_copy(update={"why_review": (foreign,) + canonical.why_review[1:]})
    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(repository, InvalidPropositions()).get(42))

    foreign_ref = base.model_copy(update={"evidence_refs": ("candidate:2:project:foreign", *base.evidence_refs)})
    invalid_brief = canonical.model_copy(update={"why_review": (foreign_ref,) + canonical.why_review[1:]})
    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(repository, InvalidPropositions()).get(42))


def test_requirement_source_descriptor_requires_complete_canonical_id():
    from pydantic import ValidationError

    from app.schemas.requirement_review import RequirementSourceDescriptorV1

    for evidence_ref in ("candidate:1:project:", "candidate:1:skill:python", "candidate:1:project:ok/extra", "candidate:1:project:ok:extra"):
        with pytest.raises(ValidationError):
            RequirementSourceDescriptorV1(
                evidence_ref=evidence_ref,
                source_kind="historical_project",
                description="synthetic invalid source",
            )

    assert RequirementSourceDescriptorV1(
        evidence_ref=f"candidate:1:skill:{'a' * 32}",
        source_kind="historical_skill_claim",
        description="synthetic valid historical skill",
    ).evidence_ref == f"candidate:1:skill:{'a' * 32}"


def test_second_source_read_cannot_switch_ranking_or_candidate():
    from app.services.requirement_review.service import RequirementReviewInvalidError, RequirementReviewService

    group = build_comparison_group(1)
    initial = _source(group)
    switched = _source(group, 1)

    class SwitchingRepository:
        reads = 0

        async def load_source(self, _):
            self.reads += 1
            return initial if self.reads == 1 else switched

    repository = SwitchingRepository()
    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(repository, RecruiterPropositionService(repository)).get(42))
    assert repository.reads == 2


def test_duplicate_requirement_id_is_not_silently_collapsed():
    from app.services.requirement_review.service import RequirementReviewInvalidError, RequirementReviewService
    from app.services.explanation.contracts import evidence_bundle_fingerprint

    group = build_comparison_group(1)
    source = _source(group)
    requirements = list(source.bundle.job.requirements)
    duplicate = requirements[1].model_copy(update={"requirement_id": requirements[0].requirement_id})
    job = source.bundle.job.model_copy(update={"requirements": [requirements[0], duplicate, *requirements[2:]]})
    bundle = source.bundle.model_copy(update={"job": job})
    altered = source.__class__(
        explanation_run_id=source.explanation_run_id,
        match_explanation_id=source.match_explanation_id,
        bundle=bundle,
        output=source.output,
        candidate_output_fingerprint=source.candidate_output_fingerprint,
        evidence_bundle_fingerprint=evidence_bundle_fingerprint(bundle),
    )
    repository = _SourceRepository(altered)
    original_brief = asyncio.run(RecruiterPropositionService(_SourceRepository(source)).get(42))
    synthetic_brief = original_brief.model_copy(update={
        "source_bundle_fingerprint": altered.evidence_bundle_fingerprint,
    })

    class SameSourceBrief:
        async def get(self, _):
            return synthetic_brief

    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(repository, SameSourceBrief()).get(42))

def test_mismatched_canonical_requirement_ref_is_rejected():
    from app.services.requirement_review.service import RequirementReviewInvalidError, RequirementReviewService
    from app.services.explanation.contracts import evidence_bundle_fingerprint

    group = build_comparison_group(1)
    source = _source(group)
    requirements = list(source.bundle.job.requirements)
    requirements[0] = requirements[0].model_copy(update={"evidence_id": "job_requirement:other_id"})
    bundle = source.bundle.model_copy(update={"job": source.bundle.job.model_copy(update={"requirements": requirements})})
    altered = source.__class__(
        explanation_run_id=source.explanation_run_id,
        match_explanation_id=source.match_explanation_id,
        bundle=bundle,
        output=source.output,
        candidate_output_fingerprint=source.candidate_output_fingerprint,
        evidence_bundle_fingerprint=evidence_bundle_fingerprint(bundle),
    )
    canonical = asyncio.run(RecruiterPropositionService(_SourceRepository(source)).get(42))
    brief = canonical.model_copy(update={"source_bundle_fingerprint": altered.evidence_bundle_fingerprint})

    class SameSourceBrief:
        async def get(self, _):
            return brief

    with pytest.raises(RequirementReviewInvalidError):
        asyncio.run(RequirementReviewService(_SourceRepository(altered), SameSourceBrief()).get(42))


def test_long_valid_historical_project_metadata_does_not_make_view_unavailable():
    from app.services.explanation.contracts import evidence_bundle_fingerprint
    from app.services.requirement_review.service import RequirementReviewService

    group = build_comparison_group(1)
    source = _source(group)
    candidate = source.bundle.candidates[0]
    project = candidate.projects[0].model_copy(update={
        "technologies": ["x" * 120 for _ in range(50)], "skills_demonstrated": ["python"],
    })
    altered_candidate = candidate.model_copy(update={"projects": [project, *candidate.projects[1:]]})
    bundle = source.bundle.model_copy(update={"candidates": [altered_candidate, *source.bundle.candidates[1:]]})
    altered = source.__class__(
        explanation_run_id=source.explanation_run_id,
        match_explanation_id=source.match_explanation_id,
        bundle=bundle,
        output=source.output,
        candidate_output_fingerprint=source.candidate_output_fingerprint,
        evidence_bundle_fingerprint=evidence_bundle_fingerprint(bundle),
    )
    repository = _SourceRepository(altered)
    result = asyncio.run(RequirementReviewService(repository, RecruiterPropositionService(repository)).get(42))
    descriptor = next(item for item in result.source_descriptors if item.source_kind == "historical_project")
    assert "另 46 项" in descriptor.description
    assert "展示技能标签 python" in descriptor.description
    assert len(descriptor.description) <= 500


def test_unlinked_historical_signal_does_not_leak_an_uncited_source_descriptor():
    """The view only exposes sources belonging to propositions it actually displays."""
    from app.services.requirement_review.service import RequirementReviewService

    group = build_comparison_group(1)
    repository = _SourceRepository(_source(group))
    canonical = asyncio.run(RecruiterPropositionService(repository).get(42))
    unlinked = canonical.technical_signals[0].model_copy(update={
        "evidence_refs": ("candidate:1:project_evidence:evidence_001",),
    })
    brief = canonical.model_copy(update={
        "technical_signals": (unlinked, *canonical.technical_signals[1:]),
    })

    class BriefWithUnlinkedSignal:
        async def get(self, _):
            return brief

    result = asyncio.run(RequirementReviewService(repository, BriefWithUnlinkedSignal()).get(42))
    displayed_refs = {
        ref
        for proposition in (
            *(item for row in result.requirements for item in row.propositions),
            *result.cross_requirement_propositions,
        )
        for ref in proposition.evidence_refs
        if ref.startswith("candidate:")
    }
    assert {item.evidence_ref for item in result.source_descriptors} == displayed_refs
    assert "candidate:1:project_evidence:evidence_001" not in displayed_refs


def test_api_returns_typed_rows_and_exact_missing_or_mismatched_errors():
    from app.api.dependencies import get_requirement_review_service
    from app.main import create_app
    from app.services.requirement_review.service import RequirementReviewService

    group = build_comparison_group(1)
    repository = _SourceRepository(_source(group))
    app = create_app()
    app.dependency_overrides[get_requirement_review_service] = lambda: RequirementReviewService(
        repository, RecruiterPropositionService(repository)
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        ok = client.get("/api/v1/match-explanations/42/requirement-review")
        mismatched = client.get("/api/v1/match-explanations/43/requirement-review")
    missing_repository = _SourceRepository(None)
    app.dependency_overrides[get_requirement_review_service] = lambda: RequirementReviewService(
        missing_repository, RecruiterPropositionService(missing_repository)
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        missing = client.get("/api/v1/match-explanations/42/requirement-review")
    assert ok.status_code == 200
    assert len(ok.json()["data"]["requirements"]) == len(group["bundle"].job.requirements)
    assert mismatched.status_code == 409
    assert mismatched.json()["error"]["code"] == "requirement_review_source_invalid"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "requirement_review_source_not_found"
    assert missing.json()["success"] is False
