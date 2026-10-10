"""Two new synthetic holdouts, frozen for the final Phase 2 triage experiment.

These definitions were chosen after the triage request adapter was implemented.
They are not used to tune its selection or generation instructions.
"""

from __future__ import annotations

from app.schemas.explanations import CandidateExplanationOutput
from app.services.explanation.evidence import EvidenceBundleBuilder
from app.services.explanation.presentation.adapter import build_narrative_projection
from test_explanation_evidence_engine import (
    _refresh_candidate_snapshot_fingerprint, _refresh_ranking_snapshot_fingerprint,
    _refresh_result_fingerprint, _run,
)


_HOLDOUTS = {
    "workflow_automation_holdout": (
        "Workflow Automation Engineer",
        ("Python", "Task Orchestration", "API Integration", "Observability"),
        ("Python", "Task Orchestration", "API Integration", "Redis"),
        ("Python", "FastAPI", "PostgreSQL", "Docker"),
    ),
    "geospatial_ml_holdout": (
        "Geospatial ML Engineer",
        ("Python", "Geospatial Analytics", "PyTorch", "Model Serving"),
        ("Python", "FastAPI", "Redis", "Docker"),
        ("Python", "RAG", "Qdrant", "FastAPI"),
    ),
}


def build_triage_holdout(name: str) -> dict:
    role, requirements, terms_a, terms_b = _HOLDOUTS[name]
    run_id = ("synthetic_triage_holdout_10" if name == "workflow_automation_holdout"
              else "synthetic_triage_holdout_11")
    run = _run(run_id=run_id)
    job = run.ranking_input_snapshot
    job["role_title"] = role
    for index, term in enumerate(requirements[1:], start=1):
        job["must_have"].append({
            "requirement_id": f"req_domain_{index}",
            "category": "skill", "text": term,
            "evidence_expectation": "structured evidence",
        })
    for result, terms in zip(run.results, (terms_a, terms_b)):
        snapshot = result.candidate_input_snapshot
        snapshot["skills"] = [
            {"name": term, "category": "backend" if term == "Python" else "llm_application"}
            for term in terms
        ]
        snapshot["projects"][0]["technologies"] = list(terms)
        snapshot["projects"][0]["skills_demonstrated"] = list(terms)
        snapshot["project_evidence"][0]["supports_skills"] = list(terms)
        _refresh_candidate_snapshot_fingerprint(result)
    _refresh_ranking_snapshot_fingerprint(run)
    _refresh_result_fingerprint(run)
    bundle = EvidenceBundleBuilder().build(run)
    requirement_refs = [
        item.evidence_id for item in bundle.job.requirements
        if item.requirement_id == "req_python" or item.requirement_id.startswith("req_domain_")
    ]
    projections = []
    for candidate in bundle.candidates:
        skill = candidate.skills[0].evidence_id
        project = candidate.projects[0].evidence_id
        source = CandidateExplanationOutput.model_validate({
            "output_schema_version": "explanation_output_v1",
            "candidate_id": candidate.candidate_id,
            "result_rank": candidate.result_rank,
            "summary": {"text": "Synthetic source evidence is available.", "evidence_refs": [skill]},
            "match_reasons": [
                {"category": "skill_alignment", "text": "Synthetic requirement relation.",
                 "evidence_refs": [skill, *requirement_refs]},
                {"category": "project_evidence", "text": "Synthetic project relation.",
                 "evidence_refs": [project]},
            ],
            "risk_points": [], "missing_skills": [], "interview_questions": [],
            "why_not_top1": None if candidate.result_rank == 1 else {
                "category": "ranking_comparison", "text": "Synthetic rank comparison.",
                "evidence_refs": ["comparison:2:top1:skill_fit_score"],
            },
            "profile_rewrite_suggestion": None,
        })
        projections.append(build_narrative_projection(bundle=bundle, source=source))
    return {
        "role": role, "requirements": requirements,
        "run": run, "bundle": bundle, "projections": tuple(projections),
        "ranking_before": {
            "fingerprint": run.result_fingerprint,
            "order": [item.candidate_id for item in run.results],
            "ltr_scores": [item.ltr_score_raw for item in run.results],
        },
    }


__all__ = ["build_triage_holdout"]
