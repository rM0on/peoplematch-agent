"""Synthetic, in-memory evidence pairs for opt-in real-provider quality review."""

from __future__ import annotations

from app.schemas.explanations import CandidateExplanationOutput
from app.services.explanation.evidence import EvidenceBundleBuilder
from app.services.explanation.presentation.adapter import build_narrative_projection
from test_explanation_evidence_engine import (
    _refresh_candidate_snapshot_fingerprint,
    _refresh_ranking_snapshot_fingerprint,
    _refresh_result_fingerprint,
    _run,
)


_GROUPS = {
    1: (
        "AI Agent Engineer",
        ("Python", "RAG", "AI Agent", "FastAPI"),
        ("Python", "RAG", "AI Agent", "FastAPI"),
        ("Python", "LambdaMART", "Retrieval", "Evaluation"),
    ),
    2: (
        "Recommendation Engineer",
        ("Python", "Retrieval", "LambdaMART", "Evaluation"),
        ("Python", "Retrieval", "LambdaMART", "Evaluation"),
        ("Python", "FastAPI", "PostgreSQL", "Docker"),
    ),
    3: (
        "AI Backend Engineer",
        ("Python", "FastAPI", "PostgreSQL", "RAG"),
        ("Python", "FastAPI", "PostgreSQL", "Docker"),
        ("Python", "RAG", "Qdrant", "Vector Database"),
    ),
    # Phase 2 semantic-intent holdouts; group 1-3 remain the immutable paired baseline.
    4: (
        "LLM Application Engineer",
        ("Python", "RAG", "Qdrant", "FastAPI"),
        ("Python", "RAG", "Qdrant", "Prompt Engineering"),
        ("Python", "Redis", "Docker", "Evaluation"),
    ),
    5: (
        "Search Ranking Engineer",
        ("Python", "Retrieval", "Ranking", "Evaluation"),
        ("Python", "Embedding", "Docker", "Redis"),
        ("FastAPI", "PostgreSQL", "Qdrant", "RAG"),
    ),
    # Phase 2 final-refinement holdouts. Not used to tune the intent builder.
    6: (
        "Data Search Infrastructure Engineer",
        ("Python", "Elasticsearch", "Kafka", "Redis"),
        ("Python", "Elasticsearch", "Kafka", "Docker"),
        ("Python", "RAG", "FastAPI", "Qdrant"),
    ),
    7: (
        "Vision API Engineer",
        ("Python", "FastAPI", "PyTorch", "Computer Vision"),
        ("Python", "Redis", "Qdrant", "Docker"),
        ("Python", "FastAPI", "PyTorch", "Docker"),
    ),
    # Preregistered Interview Semantics holdouts; never used for rule selection.
    8: (
        "MLOps Platform Engineer",
        ("Python", "Kubernetes", "MLflow", "Observability"),
        ("Python", "FastAPI", "Redis", "Docker"),
        ("Python", "Kubernetes", "MLflow", "Monitoring"),
    ),
    9: (
        "Streaming Data Engineer",
        ("Python", "Kafka", "Flink", "Monitoring"),
        ("Python", "Kafka", "Flink", "Redis"),
        ("Python", "FastAPI", "PostgreSQL", "Docker"),
    ),
}


def build_comparison_group(group: int) -> dict:
    role, requirements, terms_a, terms_b = _GROUPS[group]
    run = _run(run_id=f"synthetic_phase3_group_{group}")
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
        snapshot["skills"] = [{"name": term, "category": "backend" if term == "Python" else "llm_application"}
                              for term in terms]
        snapshot["projects"][0]["technologies"] = list(terms)
        snapshot["projects"][0]["skills_demonstrated"] = list(terms)
        snapshot["project_evidence"][0]["supports_skills"] = list(terms)
        _refresh_candidate_snapshot_fingerprint(result)
    _refresh_ranking_snapshot_fingerprint(run)
    _refresh_result_fingerprint(run)
    bundle = EvidenceBundleBuilder().build(run)
    requirement_refs = [item.evidence_id for item in bundle.job.requirements
                        if item.requirement_id == "req_python" or item.requirement_id.startswith("req_domain_")]
    outputs = []
    projections = []
    for candidate in bundle.candidates:
        skill = candidate.skills[0].evidence_id
        project = candidate.projects[0].evidence_id
        output = CandidateExplanationOutput.model_validate({
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
        outputs.append(output)
        projections.append(build_narrative_projection(bundle=bundle, source=output))
    return {
        "role": role, "requirements": requirements,
        "run": run, "bundle": bundle, "outputs": tuple(outputs),
        "projections": tuple(projections),
        "ranking_before": {
            "fingerprint": run.result_fingerprint,
            "order": [item.candidate_id for item in run.results],
            "ltr_scores": [item.ltr_score_raw for item in run.results],
        },
    }


__all__ = ["build_comparison_group"]
