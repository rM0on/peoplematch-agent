from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set

from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobProfile


SEMANTIC_SIGNAL_ALIASES = {
    "agent workflow": ("agent workflow", "tool calling", "tool schema", "agent"),
    "ranking": (
        "learning to rank",
        "pairwise ranking",
        "ranking",
        "ranker",
        "feature engineering",
    ),
    "recommendation": ("recommendation", "recommender"),
    "retrieval": (
        "candidate retrieval",
        "vector retrieval",
        "lexical retrieval",
        "search relevance",
        "reranking",
        "rerank",
        "retrieval",
        "embedding",
    ),
    "evaluation": (
        "offline evaluation",
        "evaluation harness",
        "model evaluation",
        "security evaluation",
        "embedding evaluation",
        "experiment design",
        "evaluation",
    ),
    "model serving": ("model serving", "inference runtime", "inference queue"),
    "model reliability": (
        "model robustness",
        "robustness",
        "observability",
        "model serving",
        "runtime performance",
    ),
    "ml operations": (
        "kubernetes",
        "observability",
        "ci/cd",
        "rollout",
        "deployment",
    ),
    "language models": ("llm", "transformer", "fine-tuning", "tokenizer"),
    "product workflow": (
        "full-stack",
        "product delivery",
        "user workflow",
        "ai product",
        "correction loop",
    ),
    "security": ("adversarial", "security", "robustness", "threat modeling"),
    "backend systems": (
        "distributed systems",
        "api design",
        "python api",
        "event gateway",
        "request broker",
        "backpressure",
    ),
    "data storage": ("databases", "database", "warehouse", "sql"),
    "data pipelines": ("etl", "streaming", "data quality", "lineage", "pipeline"),
    "frontend": ("react", "next.js", "typescript", "accessibility", "interface"),
    "model algorithms": ("pytorch", "transformers", "fine-tuning", "model evaluation"),
}


def semantic_signal_terms(texts: Iterable[str]) -> Set[str]:
    searchable = " ".join(texts).casefold()
    return {
        signal
        for signal, aliases in SEMANTIC_SIGNAL_ALIASES.items()
        if any(alias in searchable for alias in aliases)
    }


def candidate_signal_terms(candidate: CandidateProfile) -> Set[str]:
    return semantic_signal_terms(
        [
            candidate.raw_text,
            *(skill.name for skill in candidate.skills),
            *(project.name for project in candidate.projects),
            *(project.summary for project in candidate.projects),
            *(candidate.target_roles),
        ]
    )


def job_signal_terms(job: JobProfile) -> Set[str]:
    return semantic_signal_terms(
        [
            job.role_title,
            job.raw_jd,
            *(requirement.text for requirement in job.must_have),
            *(requirement.text for requirement in job.nice_to_have),
            *(job.role_direction),
        ]
    )


def hard_negative_overlap_terms(
    candidate: CandidateProfile, job: JobProfile
) -> List[str]:
    return sorted(candidate_signal_terms(candidate) & job_signal_terms(job))


def qualifying_hard_negative_terms(
    candidate: CandidateProfile, job: JobProfile
) -> List[str]:
    return [
        term
        for term in hard_negative_overlap_terms(candidate, job)
        if term != "evaluation"
    ]


def evidence_backed_requirement_skills(job: JobProfile) -> Set[str]:
    required: Set[str] = set()
    for requirement in job.must_have:
        if requirement.category.value == "skill":
            required.add(
                requirement.text.removeprefix("Practical use of ").casefold()
            )
        elif requirement.category.value == "project_evidence":
            required.add(
                requirement.text.removeprefix(
                    "Evaluation evidence involving "
                ).casefold()
            )
    return required


def available_evidence_skills(
    candidate: CandidateProfile, evidence_ids: Optional[Sequence[str]] = None
) -> Set[str]:
    selected_ids = set(evidence_ids) if evidence_ids is not None else None
    return {
        skill.casefold()
        for evidence in candidate.project_evidence
        if evidence.verification_status.value == "available"
        and (selected_ids is None or evidence.evidence_id in selected_ids)
        for skill in evidence.supports_skills
    }


def evidence_ids_covering_skills(
    candidate: CandidateProfile, required_skills: Set[str]
) -> List[str]:
    selected: List[str] = []
    covered: Set[str] = set()
    for evidence in candidate.project_evidence:
        if evidence.verification_status.value != "available":
            continue
        supported = {skill.casefold() for skill in evidence.supports_skills}
        newly_covered = (supported & required_skills) - covered
        if newly_covered:
            selected.append(evidence.evidence_id)
            covered.update(newly_covered)
    return selected
