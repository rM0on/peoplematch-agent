"""Deterministic rendering of grounded selections into the frozen output contract."""

from __future__ import annotations

from app.schemas.explanations import (
    CandidateExplanationOutput,
    ExplanationOutputV1,
    InternalEvidenceBundleV1,
)
from app.services.explanation.contracts import validate_explanation_output_references
from app.services.explanation.evidence.contracts import EvidenceFactsV1
from app.services.explanation.generation.contracts import ResolvedExplanationPlanV1


_REASON_TEXT = {
    "skill_fit": "Recorded candidate and requirement evidence is available.",
    "project_evidence": "Recorded project evidence is available.",
    "location": "Recorded location evidence is available.",
    "seniority": "Recorded seniority evidence is available.",
    "ranking_context": "Recorded ranking context is available.",
}
_OUTPUT_REASON_CATEGORY = {
    "skill_fit": "skill_alignment",
    "project_evidence": "project_evidence",
    "location": "location",
    "seniority": "seniority",
    "ranking_context": "ranking_context",
}
_RISK_TEXT = {
    "missing_requirement": "A required recorded requirement has no available evidence.",
    "weak_evidence": "Recorded evidence for a requirement is partial.",
    "overclaim_signal": "A recorded overclaim signal is present.",
}


def _canonical(refs: list[str]) -> list[str]:
    return sorted(set(refs))


def _source_by_candidate(facts: EvidenceFactsV1) -> dict[str, object]:
    return {candidate.candidate_id: candidate for candidate in facts.candidates}


def _matching_requirement_text(bundle: InternalEvidenceBundleV1, requirement_id: str) -> str:
    requirement = next(
        item for item in bundle.job.requirements if item.requirement_id == requirement_id
    )
    text = " ".join(requirement.text.split())
    if len(text) < 5:
        text = f"Requirement: {text or requirement_id}"
    return text[:240].rstrip()


def _render_match_reasons(candidate, source) -> list[dict]:
    reasons = [
        {
            "category": _OUTPUT_REASON_CATEGORY[item.category],
            "text": _REASON_TEXT[item.category],
            "evidence_refs": _canonical(item.evidence_refs),
        }
        for item in candidate.match_reasons
    ]
    # The frozen output contract needs two reasons.  A ranking-context-only
    # provider selection is truthful, so add only another recorded context;
    # never manufacture a semantic capability statement.
    selected = {tuple(item["evidence_refs"]) for item in reasons}
    for context in source.ranking_context:
        rendered = {
            "category": "ranking_context",
            "text": _REASON_TEXT["ranking_context"],
            "evidence_refs": _canonical(context.evidence_refs),
        }
        if tuple(rendered["evidence_refs"]) not in selected and len(reasons) < 2:
            reasons.append(rendered)
            selected.add(tuple(rendered["evidence_refs"]))
    if len(reasons) < 2:
        raise ValueError("validated facts do not contain enough recorded ranking context")
    return reasons


def _render_missing_skills(source, bundle: InternalEvidenceBundleV1) -> list[dict]:
    """This output is derived entirely from deterministic Phase 9.2 facts."""

    return [
        {
            "requirement_id": item.requirement_id,
            "requirement_text": _matching_requirement_text(bundle, item.requirement_id),
            "priority": item.priority,
            "status": item.status,
            "evidence_status": item.evidence_status,
            "evidence_refs": _canonical(item.evidence_refs),
        }
        for item in source.missing_requirements
        if item.status in {"partial", "missing"}
    ]


def _render_rewrites(candidate) -> list[dict]:
    """Translate only operation selections with enough existing source refs."""

    output = []
    for operation in candidate.rewrite_operations:
        refs = _canonical(operation.evidence_refs)
        skill = next((ref for ref in refs if ":skill:" in ref), None)
        project = next(
            (ref for ref in refs if ":project:" in ref or ":project_evidence:" in ref),
            None,
        )
        job_requirement = next((ref for ref in refs if ref.startswith("job_requirement:")), None)
        if operation.operation == "surface_existing_skill" and skill:
            output.append({"operation": operation.operation, "skill_evidence_id": skill, "evidence_refs": refs})
        elif operation.operation == "link_skill_to_project" and skill and project:
            output.append({"operation": operation.operation, "skill_evidence_id": skill, "project_evidence_id": project, "evidence_refs": refs})
        elif operation.operation == "clarify_evidence_status" and project and ":project_evidence:" in project:
            output.append({"operation": operation.operation, "evidence_record_id": project, "evidence_refs": refs})
        elif operation.operation == "reorder_existing_claim" and (skill or project):
            output.append({"operation": operation.operation, "claim_evidence_id": skill or project, "evidence_refs": refs})
        elif operation.operation == "state_gap_explicitly" and job_requirement:
            output.append({"operation": operation.operation, "requirement_evidence_id": job_requirement, "evidence_refs": refs})
        else:
            raise ValueError("grounded rewrite operation has no compatible primary evidence")
    return output


def render_explanation_output(
    grounded: ResolvedExplanationPlanV1,
    *,
    bundle: InternalEvidenceBundleV1,
    evidence_facts: EvidenceFactsV1,
) -> ExplanationOutputV1:
    """Render only fixed backend templates; provider text is never persisted."""

    source_by_candidate = _source_by_candidate(evidence_facts)
    candidates = []
    for candidate in grounded.candidates:
        source = source_by_candidate[candidate.candidate_id]
        rewrites = _render_rewrites(candidate)
        output = CandidateExplanationOutput(
            output_schema_version="explanation_output_v1",
            candidate_id=candidate.candidate_id,
            result_rank=candidate.result_rank,
            summary={
                "text": "This explanation uses recorded matching evidence.",
                "evidence_refs": _canonical(candidate.summary.evidence_refs),
            },
            match_reasons=_render_match_reasons(candidate, source),
            risk_points=[
                {
                    "category": item.category,
                    "text": _RISK_TEXT[item.category],
                    "evidence_refs": _canonical(item.evidence_refs),
                }
                for item in candidate.risk_points
            ],
            missing_skills=_render_missing_skills(source, bundle),
            interview_questions=[
                {
                    "question": "Can you clarify the recorded evidence?",
                    "rationale": "This question is tied to recorded evidence.",
                    "evidence_refs": _canonical(item.evidence_refs),
                }
                for item in candidate.interview_question_operations
            ],
            why_not_top1=(
                None
                if candidate.why_not_top1 is None
                else {
                    "category": "ranking_comparison",
                    "text": "Recorded comparison context differs from the rank-one candidate.",
                    "evidence_refs": _canonical(candidate.why_not_top1.evidence_refs),
                }
            ),
            profile_rewrite_suggestion=(
                None if not rewrites else {"operations": rewrites}
            ),
        )
        validate_explanation_output_references(output, bundle)
        candidates.append(output)
    return ExplanationOutputV1(
        contract_version="explanation_output_v1",
        candidates=candidates,
    )


__all__ = ["render_explanation_output"]
