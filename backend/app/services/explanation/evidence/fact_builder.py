from __future__ import annotations

from app.services.explanation.evidence.contracts import (
    CandidateFactSet,
    EvidenceFactsV1,
    MatchReasonFact,
    RankingContextFact,
    RiskFact,
)
from app.services.explanation.evidence.comparison_builder import Top1ComparisonBuilder
from app.services.explanation.evidence.requirement_builder import MissingRequirementBuilder
from app.services.explanation.contracts import evidence_bundle_fingerprint
from app.services.explanation.evidence.fingerprints import evidence_content_fingerprint
from app.services.explanation.evidence.validation import validate_evidence_facts


_RANKING_CONTEXT_SOURCES = (
    ("feature", "semantic_score"),
    ("feature", "sparse_score"),
    ("feature", "skill_fit_score"),
    ("feature", "project_evidence_score"),
    ("feature", "role_direction_score"),
    ("feature", "ai_tool_score"),
    ("feature", "location_score"),
    ("feature", "seniority_score"),
    ("feature", "missing_penalty"),
    ("feature", "overclaim_penalty"),
    ("ranking", "result_rank"),
    ("ranking", "ltr_rank"),
    ("ranking", "ltr_score_raw"),
    ("ranking", "cross_encoder_rank"),
    ("ranking", "cross_encoder_score_raw"),
)
RANKING_CONTEXT_SOURCE_KINDS = {
    name: kind for kind, name in _RANKING_CONTEXT_SOURCES
}


def _fact(candidate, kind: str, name: str):
    return next(
        (
            fact
            for fact in candidate.facts
            if fact.kind.value == kind and fact.name == name
        ),
        None,
    )


def _diagnostic_labels(candidate, name: str) -> set[str]:
    source = _fact(candidate, "diagnostic", name)
    return set(source.value or []) if source is not None else set()


def _bounded_skill_alignment_refs(
    candidate_refs: set[str], requirement_refs: set[str]
) -> list[str]:
    """Select at most six refs deterministically while preserving both owners."""

    if not candidate_refs or not requirement_refs:
        return []
    selected = {min(candidate_refs), min(requirement_refs)}
    for evidence_ref in sorted((candidate_refs | requirement_refs) - selected):
        if len(selected) == 6:
            break
        selected.add(evidence_ref)
    return sorted(selected)


def build_match_reasons(bundle, candidate) -> list[MatchReasonFact]:
    """Build semantic reasons only from historical source evidence."""

    reasons: list[MatchReasonFact] = []
    matched_labels = _diagnostic_labels(candidate, "matched_capabilities") | _diagnostic_labels(
        candidate, "matched_evidence_skills"
    )
    matched_requirements = _diagnostic_labels(
        candidate, "matched_must_have_requirement_ids"
    ) | _diagnostic_labels(candidate, "matched_nice_to_have_requirement_ids")
    candidate_refs = {
        skill.evidence_id for skill in candidate.skills if skill.name in matched_labels
    }
    candidate_refs.update(
        project.evidence_id
        for project in candidate.projects
        if matched_labels
        & (set(project.technologies) | set(project.skills_demonstrated))
    )
    requirement_refs = {
        requirement.evidence_id
        for requirement in bundle.job.requirements
        if requirement.evidence_id in matched_requirements
        and requirement.category.value == "skill"
    }
    skill_refs = _bounded_skill_alignment_refs(candidate_refs, requirement_refs)
    if skill_refs:
        reasons.append(
            MatchReasonFact(
                category="skill_fit",
                evidence_refs=skill_refs,
                statement_key="skill_fit_recorded",
            )
        )

    project_refs = sorted(item.evidence_id for item in candidate.project_evidence)
    if project_refs:
        reasons.append(
            MatchReasonFact(
                category="project_evidence",
                evidence_refs=project_refs[:6],
                statement_key="project_evidence_recorded",
            )
        )

    for diagnostic_name, category, statement_key in (
        ("location_relation", "location", "location_recorded"),
        ("seniority_relation", "seniority", "seniority_recorded"),
    ):
        source = _fact(candidate, "diagnostic", diagnostic_name)
        if source is not None and source.value == "exact_match":
            reasons.append(
                MatchReasonFact(
                    category=category,
                    evidence_refs=[source.evidence_id],
                    statement_key=statement_key,
                )
            )
    return reasons


def build_ranking_context(candidate) -> list[RankingContextFact]:
    """Keep recorded model inputs separate from semantic explanation evidence."""

    context = []
    for kind, name in _RANKING_CONTEXT_SOURCES:
        source = _fact(candidate, kind, name)
        if source is not None and source.value is not None:
            context.append(
                RankingContextFact(
                    dimension=name,
                    evidence_refs=[source.evidence_id],
                )
            )
    return context


class EvidenceFactBuilder:
    """Build only deterministic fact keys and references; never prose or causality."""

    def build(self, bundle) -> list[CandidateFactSet]:
        requirements = MissingRequirementBuilder().build(bundle)
        comparisons = {
            item.candidate_id: item.comparison
            for item in Top1ComparisonBuilder().build(bundle)
        }
        by_candidate: dict[tuple[str, int], list] = {}
        for item in requirements:
            by_candidate.setdefault((item.candidate_id, item.result_rank), []).append(item)
        output: list[CandidateFactSet] = []
        for candidate in bundle.candidates:
            facts = {
                (fact.kind.value, fact.name): fact
                for fact in candidate.facts
                if fact.kind.value != "comparison"
            }
            reasons = build_match_reasons(bundle, candidate)
            ranking_context = build_ranking_context(candidate)
            risks: list[RiskFact] = []
            missing = by_candidate[(candidate.candidate_id, candidate.result_rank)]
            for requirement in missing:
                if requirement.status in {"missing", "partial"}:
                    risks.append(
                        RiskFact(
                            category=(
                                "missing_requirement"
                                if requirement.status == "missing"
                                else "weak_evidence"
                            ),
                            evidence_refs=requirement.evidence_refs,
                            statement_key=(
                                "missing_requirement"
                                if requirement.status == "missing"
                                else "partial_requirement_evidence"
                            ),
                        )
                    )
            overclaim = facts.get(("diagnostic", "overclaim_level"))
            if overclaim is not None and overclaim.value == "high":
                risks.append(
                    RiskFact(
                        category="overclaim_signal",
                        evidence_refs=[overclaim.evidence_id],
                        statement_key="recorded_overclaim_signal",
                    )
                )
            output.append(
                CandidateFactSet(
                    candidate_id=candidate.candidate_id,
                    result_rank=candidate.result_rank,
                    match_reasons=reasons,
                    ranking_context=ranking_context,
                    risks=risks,
                    missing_requirements=missing,
                    comparison=comparisons[candidate.candidate_id],
                )
            )
        return output


def build_evidence_facts(bundle) -> EvidenceFactsV1:
    facts = EvidenceFactsV1(
        contract_version="evidence_facts_v1",
        bundle_fingerprint=evidence_bundle_fingerprint(bundle),
        normalized_content_fingerprint=evidence_content_fingerprint(bundle),
        candidates=EvidenceFactBuilder().build(bundle),
    )
    validate_evidence_facts(bundle, facts)
    return facts


__all__ = [
    "EvidenceFactBuilder",
    "build_evidence_facts",
    "build_match_reasons",
    "build_ranking_context",
    "RANKING_CONTEXT_SOURCE_KINDS",
]
