"""Deterministic grounding for the provider's opaque explanation selections."""

from __future__ import annotations

from app.schemas.explanations import InternalEvidenceBundleV1
from app.services.explanation.evidence.contracts import EvidenceFactsV1
from app.services.explanation.evidence.normalization import normalize_label
from app.services.explanation.generation.contracts import (
    ExplanationPlanV1,
    ResolvedExplanationPlanV1,
)
from app.services.explanation.generation.reference_projection import (
    ProviderReferenceMap,
    resolve_explanation_plan,
)


def _reference_index(bundle: InternalEvidenceBundleV1) -> dict[str, str]:
    index = {item.evidence_id: "job_requirement" for item in bundle.job.requirements}
    for candidate in bundle.candidates:
        for values, kind in (
            (candidate.skills, "skill"),
            (candidate.projects, "project"),
            (candidate.project_evidence, "project_evidence"),
        ):
            index.update({item.evidence_id: kind for item in values})
        index.update({item.evidence_id: item.kind.value for item in candidate.facts})
    return index


def _canonical(refs: list[str]) -> tuple[str, ...]:
    return tuple(sorted(refs))


def _fact_candidates(facts: EvidenceFactsV1) -> dict[str, object]:
    return {candidate.candidate_id: candidate for candidate in facts.candidates}


def _validate_reason_selections(resolved, source) -> None:
    expected = {
        (item.category, item.statement_key, _canonical(item.evidence_refs))
        for item in source.match_reasons
    }
    expected.update(
        ("ranking_context", "ranking_context_recorded", _canonical(item.evidence_refs))
        for item in source.ranking_context
    )
    for item in resolved.match_reasons:
        selection = (item.category, item.template_key, _canonical(item.evidence_refs))
        if selection not in expected:
            raise ValueError("match reason does not exactly select validated semantic evidence")


def _validate_risk_selections(resolved, source) -> None:
    expected = {
        (item.category, item.statement_key, _canonical(item.evidence_refs))
        for item in source.risks
    }
    for item in resolved.risk_points:
        selection = (item.category, item.template_key, _canonical(item.evidence_refs))
        if selection not in expected:
            raise ValueError("risk point does not exactly select validated risk evidence")


def _validate_summary(resolved) -> None:
    selected = {
        ref
        for item in (*resolved.match_reasons, *resolved.risk_points)
        for ref in item.evidence_refs
    }
    if not set(resolved.summary.evidence_refs).issubset(selected):
        raise ValueError("summary references must be selected grounded facts")


def _skill_project_relationship(bundle, resolved, skill_ref: str, project_ref: str) -> bool:
    candidate = next(
        item
        for item in bundle.candidates
        if item.candidate_id == resolved.candidate_id
        and item.result_rank == resolved.result_rank
    )
    skill = next(item for item in candidate.skills if item.evidence_id == skill_ref)
    normalized_skill = normalize_label(skill.name, "rewrite skill")
    related_labels: set[str] = set()
    project = next(
        (item for item in candidate.projects if item.evidence_id == project_ref),
        None,
    )
    if project is not None:
        related_labels.update(project.technologies)
        related_labels.update(project.skills_demonstrated)
    else:
        record = next(
            item for item in candidate.project_evidence if item.evidence_id == project_ref
        )
        related_labels.update(record.supports_skills)
        owner_project = next(
            (item for item in candidate.projects if item.project_id == record.project_id),
            None,
        )
        if owner_project is not None:
            related_labels.update(owner_project.technologies)
            related_labels.update(owner_project.skills_demonstrated)
    return normalized_skill in {
        normalize_label(label, "rewrite project skill") for label in related_labels
    }


def _validate_operations(resolved, source, kind_index: dict[str, str], bundle) -> None:
    allowed_interview_refs = {
        _canonical(item.evidence_refs)
        for item in source.missing_requirements
        if item.status in {"missing", "partial"}
    }
    for operation in resolved.interview_question_operations:
        if _canonical(operation.evidence_refs) not in allowed_interview_refs:
            raise ValueError(
                "interview operation must exactly select a missing or partial requirement"
            )
    for operation in resolved.rewrite_operations:
        kinds = {kind_index[ref] for ref in operation.evidence_refs}
        if operation.operation == "surface_existing_skill":
            valid = kinds <= {"skill", "project", "project_evidence"} and "skill" in kinds
        elif operation.operation == "link_skill_to_project":
            ordered_refs = sorted(operation.evidence_refs)
            skill_ref = next(
                (ref for ref in ordered_refs if kind_index[ref] == "skill"),
                None,
            )
            project_ref = next(
                (
                    ref
                    for ref in ordered_refs
                    if kind_index[ref] in {"project", "project_evidence"}
                ),
                None,
            )
            valid = (
                kinds <= {"skill", "project", "project_evidence"}
                and skill_ref is not None
                and project_ref is not None
                and _skill_project_relationship(
                    bundle,
                    resolved,
                    skill_ref,
                    project_ref,
                )
            )
        elif operation.operation == "clarify_evidence_status":
            valid = kinds <= {"skill", "project", "project_evidence", "diagnostic"} and "project_evidence" in kinds
        elif operation.operation == "reorder_existing_claim":
            valid = kinds <= {"skill", "project", "project_evidence"}
        else:  # state_gap_explicitly
            requirement_refs = [
                ref for ref in operation.evidence_refs if kind_index[ref] == "job_requirement"
            ]
            gap = next(
                (
                    item
                    for item in source.missing_requirements
                    if len(requirement_refs) == 1
                    and requirement_refs[0] in item.evidence_refs
                ),
                None,
            )
            valid = (
                kinds <= {"job_requirement", "diagnostic"}
                and gap is not None
                and gap.status in {"missing", "partial"}
                and gap.evidence_status != "available"
            )
        if not valid:
            raise ValueError("rewrite operation references violate its semantic policy")


def _validate_comparison(resolved, source) -> None:
    if resolved.result_rank == 1:
        if resolved.why_not_top1 is not None:
            raise ValueError("rank-one Candidate cannot have a top-1 comparison")
        return
    if resolved.why_not_top1 is None or source.comparison is None:
        raise ValueError("non-top-one Candidate requires an exact top-1 comparison")
    expected = _canonical(
        [ref for item in source.comparison.comparisons for ref in item.evidence_refs]
    )[:6]
    if _canonical(resolved.why_not_top1.evidence_refs) != expected:
        raise ValueError("top-1 comparison does not exactly select recorded comparison evidence")


def ground_explanation_plan(
    plan: ExplanationPlanV1,
    *,
    reference_map: ProviderReferenceMap,
    bundle: InternalEvidenceBundleV1,
    evidence_facts: EvidenceFactsV1,
) -> ResolvedExplanationPlanV1:
    """Resolve and validate every provider selection against frozen facts.

    It intentionally does not inspect provider prose because the plan contract
    contains none.  The only accepted provider output is a typed selection of
    known, deterministic fact tuples.
    """

    resolved = resolve_explanation_plan(
        plan,
        reference_map=reference_map,
        bundle=bundle,
        evidence_facts=evidence_facts,
    )
    source_by_candidate = _fact_candidates(evidence_facts)
    kind_index = _reference_index(bundle)
    for candidate in resolved.candidates:
        source = source_by_candidate[candidate.candidate_id]
        _validate_reason_selections(candidate, source)
        _validate_risk_selections(candidate, source)
        _validate_summary(candidate)
        _validate_operations(candidate, source, kind_index, bundle)
        _validate_comparison(candidate, source)
    return resolved


__all__ = ["ground_explanation_plan"]
