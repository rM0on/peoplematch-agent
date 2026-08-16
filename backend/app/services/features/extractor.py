from __future__ import annotations

from collections.abc import Collection, Iterable

from app.schemas.candidate import CandidateProfile, RiskLevel, VerificationStatus
from app.schemas.features import (
    FeatureAvailability,
    FeatureDiagnostics,
    FeatureVector,
    PairFeatureExtraction,
)
from app.schemas.job import JobProfile, RequirementCategory
from app.schemas.retrieval import RetrievalResult
from app.services.features.matching import (
    EVIDENCE_REQUIREMENT_CATEGORIES,
    SKILL_REQUIREMENT_CATEGORIES,
    applicable_requirements,
    match_requirement,
    normalized_atoms,
)
from app.services.features.normalization import normalize_text, normalized_tokens


def _candidate_capabilities(candidate: CandidateProfile) -> dict[str, str]:
    return normalized_atoms(
        [skill.name for skill in candidate.skills]
        + [technology for project in candidate.projects for technology in project.technologies]
        + [skill for project in candidate.projects for skill in project.skills_demonstrated]
    )


def _evidence_capabilities(candidate: CandidateProfile) -> dict[str, str]:
    return normalized_atoms(
        skill
        for evidence in candidate.project_evidence
        if evidence.verification_status == VerificationStatus.AVAILABLE
        for skill in evidence.supports_skills
    )


def _weighted_coverage(
    candidate: CandidateProfile,
    job: JobProfile,
    *,
    evidence: bool,
    allowed_categories: Collection[RequirementCategory],
):
    atoms = _evidence_capabilities(candidate) if evidence else _candidate_capabilities(candidate)
    weighted = []
    must_matches = []
    nice_matches = []
    for requirement, weight, bucket in (
        [
            (item, 2.0, must_matches)
            for item in applicable_requirements(job.must_have, allowed_categories)
        ]
        + [
            (item, 1.0, nice_matches)
            for item in applicable_requirements(job.nice_to_have, allowed_categories)
        ]
    ):
        match = match_requirement(requirement, atoms)
        weighted.append((weight, match))
        bucket.append(match)
    if not weighted:
        return None, must_matches, nice_matches
    score = sum(weight * match.value for weight, match in weighted) / sum(
        weight for weight, _ in weighted
    )
    return score, must_matches, nice_matches


def _role_score(candidate: CandidateProfile, job: JobProfile) -> float | None:
    candidate_roles = [normalized_tokens(value) for value in candidate.target_roles]
    job_roles = [normalized_tokens(job.role_title)] + [
        normalized_tokens(value) for value in job.role_direction
    ]
    candidate_roles = [tokens for tokens in candidate_roles if tokens]
    job_roles = [tokens for tokens in job_roles if tokens]
    if not candidate_roles or not job_roles:
        return None
    scores = []
    for candidate_tokens in candidate_roles:
        for job_tokens in job_roles:
            if candidate_tokens == job_tokens:
                scores.append(1.0)
                continue
            left, right = set(candidate_tokens), set(job_tokens)
            scores.append(len(left & right) / len(left | right))
    return max(scores)


def _ai_tool_score(candidate: CandidateProfile, job: JobProfile):
    requirements = [
        item
        for item in [*job.must_have, *job.nice_to_have]
        if item.category == RequirementCategory.AI_TOOLING
    ]
    if not requirements:
        return None, []
    atoms = normalized_atoms(candidate.ai_tools)
    matched = sorted(
        {
            atom
            for requirement in requirements
            for atom in match_requirement(requirement, atoms).matched_atoms
        }
    )
    return (1.0 if matched else 0.0), matched


def _location_score(candidate: CandidateProfile, job: JobProfile):
    candidate_cities = {normalize_text(value) for value in candidate.preferred_locations.cities if normalize_text(value)}
    job_cities = {normalize_text(value) for value in job.location.cities if normalize_text(value)}
    if not candidate_cities or not job_cities:
        return None, "unavailable"
    matched = bool(candidate_cities & job_cities)
    return (1.0 if matched else 0.0), ("exact_match" if matched else "mismatch")


def _seniority_score(candidate: CandidateProfile, job: JobProfile):
    if candidate.seniority is None or not job.seniority_requirement:
        return None, "unavailable"
    matched = candidate.seniority in job.seniority_requirement
    return (1.0 if matched else 0.0), ("exact_match" if matched else "mismatch")


def _unique_atoms(matches: Iterable) -> list[str]:
    return sorted({atom for match in matches for atom in match.matched_atoms})


def extract_pair_features(
    candidate: CandidateProfile,
    job: JobProfile,
    retrieval_result: RetrievalResult | None = None,
) -> PairFeatureExtraction:
    skill_score, skill_must, skill_nice = _weighted_coverage(
        candidate,
        job,
        evidence=False,
        allowed_categories=SKILL_REQUIREMENT_CATEGORIES,
    )
    evidence_score, evidence_must, evidence_nice = _weighted_coverage(
        candidate,
        job,
        evidence=True,
        allowed_categories=EVIDENCE_REQUIREMENT_CATEGORIES,
    )
    missing_penalty = (
        sum(1.0 - item.value for item in skill_must) / len(skill_must)
        if skill_must
        else None
    )
    role_score = _role_score(candidate, job)
    ai_tool_score, matched_ai_tools = _ai_tool_score(candidate, job)
    location_score, location_relation = _location_score(candidate, job)
    seniority_score, seniority_relation = _seniority_score(candidate, job)
    risk_map = {RiskLevel.LOW: 0.0, RiskLevel.MEDIUM: 0.5, RiskLevel.HIGH: 1.0}
    overclaim_score = risk_map.get(candidate.overclaim_risk.level)
    dense_score = retrieval_result.dense_score if retrieval_result else None
    sparse_score = retrieval_result.sparse_score if retrieval_result else None

    vector = FeatureVector(
        semantic_score=dense_score,
        sparse_score=sparse_score,
        skill_fit_score=skill_score,
        project_evidence_score=evidence_score,
        role_direction_score=role_score,
        ai_tool_score=ai_tool_score,
        location_score=location_score,
        seniority_score=seniority_score,
        missing_penalty=missing_penalty,
        overclaim_penalty=overclaim_score,
    )
    all_skill_matches = [*skill_must, *skill_nice]
    all_evidence_matches = [*evidence_must, *evidence_nice]
    diagnostics = FeatureDiagnostics(
        availability=FeatureAvailability(
            **{
                name: getattr(vector, name) is not None
                for name in FeatureVector.model_fields
            }
        ),
        matched_must_have_requirement_ids=[
            item.requirement_id for item in skill_must if item.value == 1.0
        ],
        weak_matched_must_have_requirement_ids=[
            item.requirement_id for item in skill_must if item.value == 0.5
        ],
        missing_must_have_requirement_ids=[
            item.requirement_id for item in skill_must if item.value == 0.0
        ],
        matched_nice_to_have_requirement_ids=[
            item.requirement_id for item in skill_nice if item.value > 0.0
        ],
        evidence_supported_requirement_ids=[
            item.requirement_id for item in all_evidence_matches if item.value > 0.0
        ],
        matched_capabilities=_unique_atoms(all_skill_matches),
        matched_evidence_skills=_unique_atoms(all_evidence_matches),
        matched_ai_tools=matched_ai_tools,
        location_relation=location_relation,
        seniority_relation=seniority_relation,
        overclaim_level=getattr(candidate.overclaim_risk.level, "value", None),
        overclaim_reason_count=len(candidate.overclaim_risk.reasons),
        retrieval_rank=retrieval_result.rank if retrieval_result else None,
        dense_rank=retrieval_result.dense_rank if retrieval_result else None,
        sparse_rank=retrieval_result.sparse_rank if retrieval_result else None,
        fusion_score=retrieval_result.fusion_score if retrieval_result else None,
    )
    return PairFeatureExtraction(vector=vector, diagnostics=diagnostics)
