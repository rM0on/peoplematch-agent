from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _record(path: str, model):
    line = (ROOT / path).read_text(encoding="utf-8").splitlines()[0]
    return model.model_validate(json.loads(line))


def _profiles():
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobProfile

    return (
        _record("data/samples/candidates.jsonl", CandidateProfile),
        _record("data/samples/jobs.jsonl", JobProfile),
    )


def test_normalizer_is_deterministic_nfkc_casefold_and_punctuation_safe() -> None:
    from app.services.features.normalization import normalize_text

    assert normalize_text("  ＦＡＳＴＡＰＩ—PyTest!  ") == "fastapi pytest"
    assert normalize_text("  ＦＡＳＴＡＰＩ—PyTest!  ") == normalize_text(
        "fastapi pytest"
    )


def test_feature_extraction_is_deterministic_bounded_and_preserves_raw_channels() -> None:
    from app.schemas.retrieval import RetrievalResult
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    retrieval = RetrievalResult(
        entity_id=candidate.candidate_id,
        rank=3,
        matched_channels=["dense", "sparse"],
        dense_rank=4,
        dense_score=-0.125,
        sparse_rank=2,
        sparse_score=7.75,
        fusion_score=0.031,
    )

    first = extract_pair_features(candidate, job, retrieval)
    second = extract_pair_features(candidate, job, retrieval)

    assert first == second
    assert first.vector.semantic_score == -0.125
    assert first.vector.sparse_score == 7.75
    assert first.diagnostics.retrieval_rank == 3
    assert first.diagnostics.dense_rank == 4
    assert first.diagnostics.sparse_rank == 2
    assert first.diagnostics.fusion_score == 0.031
    for name in (
        "skill_fit_score",
        "project_evidence_score",
        "role_direction_score",
        "ai_tool_score",
        "location_score",
        "seniority_score",
        "missing_penalty",
        "overclaim_penalty",
    ):
        value = getattr(first.vector, name)
        assert value is None or 0 <= value <= 1


def test_missing_retrieval_channels_are_null_not_zero() -> None:
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    result = extract_pair_features(candidate, job)

    assert result.vector.semantic_score is None
    assert result.vector.sparse_score is None
    assert result.diagnostics.availability.semantic_score is False
    assert result.diagnostics.availability.sparse_score is False


def test_single_retrieval_channel_does_not_invent_the_other_channel() -> None:
    from app.schemas.retrieval import RetrievalResult
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    dense = extract_pair_features(
        candidate,
        job,
        RetrievalResult(
            entity_id=candidate.candidate_id,
            rank=1,
            matched_channels=["dense"],
            dense_rank=1,
            dense_score=0.42,
        ),
    )
    sparse = extract_pair_features(
        candidate,
        job,
        RetrievalResult(
            entity_id=candidate.candidate_id,
            rank=1,
            matched_channels=["sparse"],
            sparse_rank=1,
            sparse_score=4.2,
        ),
    )

    assert dense.vector.semantic_score == 0.42
    assert dense.vector.sparse_score is None
    assert dense.diagnostics.availability.sparse_score is False
    assert sparse.vector.sparse_score == 4.2
    assert sparse.vector.semantic_score is None
    assert sparse.diagnostics.availability.semantic_score is False


def test_no_applicable_requirements_is_missing_not_perfect_or_zero() -> None:
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    job = job.model_copy(
        update={
            "must_have": [
                item
                for item in job.must_have
                if item.category.value in {"location", "seniority", "role_direction"}
            ],
            "nice_to_have": [],
        }
    )
    result = extract_pair_features(candidate, job)

    assert result.vector.skill_fit_score is None
    assert result.vector.project_evidence_score is None
    assert result.vector.missing_penalty is None
    assert result.diagnostics.availability.skill_fit_score is False
    assert result.diagnostics.availability.missing_penalty is False


def test_ai_tool_score_is_explicit_overlap_only_and_missing_without_requirement() -> None:
    from app.schemas.job import JobRequirement
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    explicit = JobRequirement(
        requirement_id="req_explicit_tool",
        text="Experience using prompt tracing",
        category="ai_tooling",
        evidence_expectation="A reviewable local workflow artifact",
    )
    matched = extract_pair_features(
        candidate, job.model_copy(update={"nice_to_have": [explicit]})
    )
    unmatched = extract_pair_features(
        candidate,
        job.model_copy(
            update={
                "nice_to_have": [
                    explicit.model_copy(update={"text": "Experience using UnknownTool"})
                ]
            }
        ),
    )
    unavailable = extract_pair_features(
        candidate, job.model_copy(update={"nice_to_have": []})
    )

    assert matched.vector.ai_tool_score == 1
    assert matched.diagnostics.matched_ai_tools == ["prompt tracing"]
    assert unmatched.vector.ai_tool_score == 0
    assert unmatched.diagnostics.availability.ai_tool_score is True
    assert unavailable.vector.ai_tool_score is None
    assert unavailable.diagnostics.availability.ai_tool_score is False


def test_skill_and_evidence_coverage_are_monotonic_and_distinct() -> None:
    from app.schemas.candidate import ProjectEvidence, SkillClaim
    from app.schemas.job import JobRequirement, RequirementCategory
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    requirement = JobRequirement(
        requirement_id="req_added_skill",
        text="Practical use of FastAPI",
        category=RequirementCategory.SKILL,
        evidence_expectation="Reviewable code or test evidence",
    )
    job = job.model_copy(update={"must_have": [requirement]})

    without_skill = candidate.model_copy(
        update={
            "skills": [item for item in candidate.skills if item.name != "FastAPI"],
            "projects": [
                project.model_copy(
                    update={
                        "technologies": [
                            item for item in project.technologies if item != "FastAPI"
                        ],
                        "skills_demonstrated": [
                            item
                            for item in project.skills_demonstrated
                            if item != "FastAPI"
                        ],
                    }
                )
                for project in candidate.projects
            ],
            "project_evidence": [],
        }
    )
    claimed_only = without_skill.model_copy(
        update={
            "skills": [
                *without_skill.skills,
                SkillClaim(name="FastAPI", category="backend"),
            ]
        }
    )
    evidenced = claimed_only.model_copy(
        update={
            "project_evidence": [
                ProjectEvidence(
                    evidence_id="ev_added_fastapi",
                    project_id=claimed_only.projects[0].project_id,
                    supports_skills=["FastAPI"],
                    evidence_type="tests",
                    statement="A deterministic synthetic test artifact supports this capability.",
                    artifact_ref="sandbox://feature-test/fastapi",
                    verification_status="available",
                )
            ]
        }
    )

    missing = extract_pair_features(without_skill, job)
    claimed = extract_pair_features(claimed_only, job)
    supported = extract_pair_features(evidenced, job)

    assert claimed.vector.skill_fit_score >= missing.vector.skill_fit_score
    assert claimed.vector.missing_penalty <= missing.vector.missing_penalty
    assert claimed.vector.project_evidence_score == 0
    assert supported.vector.project_evidence_score >= claimed.vector.project_evidence_score


def test_skill_fit_uses_exact_must_two_nice_one_weights() -> None:
    from app.schemas.job import JobRequirement
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    matched = JobRequirement(
        requirement_id="req_weight_match",
        text="Practical use of FastAPI",
        category="skill",
        evidence_expectation="A reviewable implementation artifact",
    )
    missing = JobRequirement(
        requirement_id="req_weight_missing",
        text="Practical use of NeverPresentCapability",
        category="skill",
        evidence_expectation="A reviewable implementation artifact",
    )
    must_matched = extract_pair_features(
        candidate,
        job.model_copy(update={"must_have": [matched], "nice_to_have": [missing]}),
    )
    nice_matched = extract_pair_features(
        candidate,
        job.model_copy(update={"must_have": [missing], "nice_to_have": [matched]}),
    )

    assert must_matched.vector.skill_fit_score == 2 / 3
    assert nice_matched.vector.skill_fit_score == 1 / 3


def test_location_seniority_and_overclaim_have_conservative_semantics() -> None:
    from app.schemas.candidate import CandidateLocationPreference, OverclaimRisk
    from app.schemas.job import JobLocation
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    matched = extract_pair_features(candidate, job)
    mismatch_candidate = candidate.model_copy(
        update={
            "preferred_locations": CandidateLocationPreference(
                cities=["Shenzhen"], remote_policy="hybrid", relocation_open=False
            ),
            "seniority": "staff",
            "overclaim_risk": OverclaimRisk(level="high", reasons=["synthetic"]),
        }
    )
    mismatched = extract_pair_features(mismatch_candidate, job)
    missing_job = job.model_copy(
        update={
            "location": JobLocation.model_construct(
                cities=[], remote_policy="hybrid", relocation_supported=False
            ),
            "seniority_requirement": [],
        }
    )
    unavailable = extract_pair_features(candidate, missing_job)

    assert matched.vector.location_score == 1
    assert matched.vector.seniority_score == 1
    assert mismatched.vector.location_score == 0
    assert mismatched.vector.seniority_score == 0
    assert mismatched.vector.overclaim_penalty == 1
    assert unavailable.vector.location_score is None
    assert unavailable.vector.seniority_score is None
    assert unavailable.diagnostics.availability.location_score is False
    assert unavailable.diagnostics.availability.seniority_score is False


def test_overclaim_mapping_covers_the_complete_canonical_enum() -> None:
    from app.schemas.candidate import OverclaimRisk
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    expected = {"low": 0.0, "medium": 0.5, "high": 1.0}
    for level, value in expected.items():
        risk = OverclaimRisk(
            level=level,
            reasons=[] if level == "low" else ["structured synthetic risk"],
        )
        changed = candidate.model_copy(update={"overclaim_risk": risk})
        assert extract_pair_features(changed, job).vector.overclaim_penalty == value


def test_forbidden_metadata_and_construction_text_do_not_change_features() -> None:
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    baseline = extract_pair_features(candidate, job).vector
    changed = candidate.model_copy(
        update={
            "candidate_id": "cand_changed",
            "name": "Changed Synthetic Name",
            "raw_text": "Feature engineering FastAPI Shanghai senior labels grade 3",
            "github_url": "https://example.invalid/changed",
            "archetype": "overclaim_candidate",
            "data_origin": "changed_provenance",
            "schema_version": "changed_schema",
            "projects": [
                item.model_copy(
                    update={
                        "name": "Feature Engineering Family Suffix",
                        "summary": "FastAPI ranking label hard negative benchmark text",
                    }
                )
                for item in candidate.projects
            ],
            "project_evidence": [
                item.model_copy(
                    update={"statement": "FastAPI label grade test split benchmark"}
                )
                for item in candidate.project_evidence
            ],
        }
    )
    changed_job = job.model_copy(
        update={
            "job_id": "job_changed",
            "company_name": "Changed Company",
            "raw_jd": "FastAPI Agent workflow labels hard negatives",
            "archetype": "rag_engineer",
            "data_origin": "changed_provenance",
            "schema_version": "changed_schema",
        }
    )

    assert extract_pair_features(changed, changed_job).vector == baseline


def test_external_label_pairwise_and_hard_negative_mutation_cannot_change_vector() -> None:
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    annotations = {
        "relevance_grade": 0,
        "hard_negative": False,
        "pairwise_preference": "left",
        "split": "train",
    }
    before = extract_pair_features(candidate, job).vector
    annotations.update(
        relevance_grade=3,
        hard_negative=True,
        pairwise_preference="right",
        split="test",
    )
    after = extract_pair_features(candidate, job).vector

    assert annotations["relevance_grade"] == 3
    assert before == after
