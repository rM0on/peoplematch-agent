from __future__ import annotations

from dataclasses import dataclass

from app.schemas.explanations import CandidateExplanationOutput, InternalEvidenceBundleV1
from app.services.explanation.contracts import validate_explanation_output_references


@dataclass(frozen=True)
class NarrativeProjection:
    candidate_id: str
    result_rank: int
    role_title: str
    facts: dict[str, tuple[str, ...]]
    verification_status: dict[str, str]
    positive_refs: frozenset[str]
    risk_refs: frozenset[str]
    interview_refs: frozenset[str]


def build_narrative_projection(
    *, bundle: InternalEvidenceBundleV1, source: CandidateExplanationOutput
) -> NarrativeProjection:
    """Expose only facts selected by a validated historical explanation."""

    from app.services.explanation.presentation.validator import NarrativeValidationError

    try:
        validate_explanation_output_references(source, bundle)
    except ValueError:
        raise NarrativeValidationError() from None
    owner = next(
        (candidate for candidate in bundle.candidates if candidate.candidate_id == source.candidate_id
         and candidate.result_rank == source.result_rank),
        None,
    )
    if owner is None:
        raise NarrativeValidationError()

    selected_positive = {
        *source.summary.evidence_refs,
        *(ref for item in source.match_reasons for ref in item.evidence_refs),
    }
    selected_risk = {
        *(ref for item in source.risk_points for ref in item.evidence_refs),
        *(ref for item in source.missing_skills for ref in item.evidence_refs),
    }
    selected_interview = {
        *selected_positive,
        *selected_risk,
        *(ref for item in source.interview_questions for ref in item.evidence_refs),
    }
    factual: dict[str, tuple[str, ...]] = {}
    verification_status: dict[str, str] = {}
    for skill in owner.skills:
        factual[skill.evidence_id] = (skill.name,)
    for project in owner.projects:
        factual[project.evidence_id] = tuple(
            sorted(set(project.technologies + project.skills_demonstrated))
        )
    for record in owner.project_evidence:
        factual[record.evidence_id] = tuple(record.supports_skills)
        verification_status[record.evidence_id] = record.verification_status.value
    for requirement in bundle.job.requirements:
        factual[requirement.evidence_id] = (requirement.text,)

    allowed = selected_positive | selected_risk | selected_interview
    facts = {ref: terms for ref, terms in factual.items() if ref in allowed and terms}
    positive = frozenset(selected_positive & facts.keys())
    candidate_positive = [ref for ref in positive if ref.startswith("candidate:")]
    if not candidate_positive:
        raise NarrativeValidationError()
    if not any(ref.startswith("job_requirement:") for ref in positive):
        raise NarrativeValidationError()
    return NarrativeProjection(
        candidate_id=source.candidate_id,
        result_rank=source.result_rank,
        role_title=bundle.job.role_title,
        facts=facts,
        verification_status={ref: status for ref, status in verification_status.items() if ref in facts},
        positive_refs=positive,
        risk_refs=frozenset(selected_risk & facts.keys()),
        interview_refs=frozenset(selected_interview & facts.keys()),
    )


__all__ = ["NarrativeProjection", "build_narrative_projection"]
