from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.exceptions import EvaluationIntegrityError
from app.schemas.labels import RelevanceGrade, RelevanceLabel
from app.schemas.retrieval import RetrievalRequest, RetrievalStrategy
from app.services.retrieval.documents import RETRIEVAL_DOCUMENT_VERSION


RELEVANCE_THRESHOLD = int(RelevanceGrade.PLAUSIBLE_MATCH)
METRIC_K_VALUES = (5, 10, 20)
PHASE4_EVALUATION_PROTOCOL: dict[str, Any] = {
    "exposed_predecessor_versions": [
        "retrieval_doc_v1",
        "retrieval_doc_v2",
        "retrieval_doc_v3",
    ],
    "interpretation": "post-exposure fixed synthetic sandbox benchmark",
    "prior_test_exposure": True,
    "pristine_held_out": False,
}
PHASE4_RETRIEVAL_CONFIG: dict[str, Any] = {
    "document_version": RETRIEVAL_DOCUMENT_VERSION,
    "candidate_document_fields": [
        "target_roles",
        "skills.name",
        "skills.category",
        "projects.summary",
        "projects.role",
        "projects.technologies",
        "projects.skills_demonstrated",
        "project_evidence.supports_skills",
        "project_evidence.evidence_type",
        "project_evidence.statement",
        "ai_tools",
    ],
    "project_construction_signal_policy": "derive_full_base_variant_fragments_from_owned_names_and_remove_case_insensitively_from_all_candidate_text",
    "job_document_fields": [
        "role_title",
        "role_direction",
        "must_have.text",
        "must_have.category",
        "must_have.evidence_expectation",
        "nice_to_have.text",
        "nice_to_have.category",
        "nice_to_have.evidence_expectation",
        "evaluation_focus",
    ],
    "embedding_provider": "sentence_transformers",
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_dimension": 384,
    "bm25_k1": 1.5,
    "bm25_b": 0.75,
    "rrf_k": 60,
    "dense_weight": 1.0,
    "sparse_weight": 1.0,
    "pool_minimum": 20,
    "pool_multiplier": 3,
    "dense_tie_policy": "exact_all_eligible_then_score_entity_id_then_pool",
    "default_filters": None,
    "relevance_threshold": RELEVANCE_THRESHOLD,
    "metric_k_values": list(METRIC_K_VALUES),
    "hit_rate_k_values": [5, 10],
}


@dataclass(frozen=True)
class QueryMetrics:
    recall_at_k: dict[int, float]
    hit_rate_at_k: dict[int, float]
    mrr: float


@dataclass(frozen=True)
class AggregateMetrics:
    recall_at_k: dict[int, float]
    hit_rate_at_k: dict[int, float]
    mrr: float
    query_count: int


@dataclass(frozen=True)
class FrozenBenchmark:
    candidate_ids: set[str]
    job_ids: set[str]
    labels: list[RelevanceLabel]
    relevant_ids_by_job: dict[str, set[str]]
    splits: dict[str, list[str]]
    judgments_per_query: int
    total_possible_pairs: int
    judgments_complete: bool
    relevance_threshold: int


def evaluate_query(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str],
    *,
    k_values: Sequence[int],
) -> QueryMetrics:
    if not relevant_ids:
        raise EvaluationIntegrityError("Every evaluated query must have relevant judgments")
    recalls = {
        k: len(set(retrieved_ids[:k]) & relevant_ids) / len(relevant_ids)
        for k in k_values
    }
    hit_rates = {
        k: float(bool(set(retrieved_ids[:k]) & relevant_ids)) for k in k_values
    }
    first_relevant_rank = next(
        (rank for rank, entity_id in enumerate(retrieved_ids, start=1) if entity_id in relevant_ids),
        None,
    )
    return QueryMetrics(
        recall_at_k=recalls,
        hit_rate_at_k=hit_rates,
        mrr=1 / first_relevant_rank if first_relevant_rank else 0.0,
    )


def aggregate_queries(metrics: Sequence[QueryMetrics]) -> AggregateMetrics:
    if not metrics:
        raise EvaluationIntegrityError("At least one query is required")
    count = len(metrics)
    recall_keys = metrics[0].recall_at_k
    hit_rate_keys = metrics[0].hit_rate_at_k
    return AggregateMetrics(
        recall_at_k={
            k: sum(item.recall_at_k[k] for item in metrics) / count
            for k in recall_keys
        },
        hit_rate_at_k={
            k: sum(item.hit_rate_at_k[k] for item in metrics) / count
            for k in hit_rate_keys
        },
        mrr=sum(item.mrr for item in metrics) / count,
        query_count=count,
    )


def config_fingerprint(config: Mapping[str, Any]) -> str:
    stable = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _validate_freeze_manifest(repository_root: Path) -> None:
    manifest = json.loads(
        (repository_root / "data" / "eval" / "dataset_freeze_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for relative_path, expected_hash in manifest["canonical_files"].items():
        actual_hash = hashlib.sha256(
            (repository_root / relative_path).read_bytes()
        ).hexdigest()
        if actual_hash != expected_hash:
            raise EvaluationIntegrityError(
                f"Canonical dataset freeze hash mismatch: {relative_path}"
            )


def load_frozen_benchmark(repository_root: Path) -> FrozenBenchmark:
    _validate_freeze_manifest(repository_root)
    candidates = _jsonl(repository_root / "data" / "samples" / "candidates.jsonl")
    jobs = _jsonl(repository_root / "data" / "samples" / "jobs.jsonl")
    labels = [
        RelevanceLabel.model_validate(item)
        for item in _jsonl(repository_root / "data" / "samples" / "labels.jsonl")
    ]
    split_payload = json.loads(
        (repository_root / "data" / "eval" / "query_splits.json").read_text(
            encoding="utf-8"
        )
    )
    candidate_ids = {item["candidate_id"] for item in candidates}
    job_ids = {item["job_id"] for item in jobs}
    counts = {job_id: 0 for job_id in job_ids}
    relevant_ids_by_job = {job_id: set() for job_id in job_ids}
    for label in labels:
        counts[label.job_id] += 1
        if int(label.relevance_grade) >= RELEVANCE_THRESHOLD:
            relevant_ids_by_job[label.job_id].add(label.candidate_id)
    judgment_counts = set(counts.values())
    if len(judgment_counts) != 1:
        raise EvaluationIntegrityError("Judgment coverage differs by query")
    judgments_per_query = next(iter(judgment_counts))
    total_possible_pairs = len(candidate_ids) * len(job_ids)
    return FrozenBenchmark(
        candidate_ids=candidate_ids,
        job_ids=job_ids,
        labels=labels,
        relevant_ids_by_job=relevant_ids_by_job,
        splits=split_payload["splits"],
        judgments_per_query=judgments_per_query,
        total_possible_pairs=total_possible_pairs,
        judgments_complete=len(labels) == total_possible_pairs,
        relevance_threshold=RELEVANCE_THRESHOLD,
    )


def validate_evaluation_corpus(
    *,
    actual_candidate_ids: set[str],
    expected_candidate_ids: set[str],
    query_ids: set[str],
    expected_job_ids: set[str],
) -> None:
    if actual_candidate_ids != expected_candidate_ids:
        raise EvaluationIntegrityError("Actual candidate corpus differs from frozen candidate corpus")
    if not query_ids <= expected_job_ids:
        raise EvaluationIntegrityError("Evaluation query IDs are outside the frozen job corpus")


async def evaluate_split(
    *,
    service,
    query_ids: Sequence[str],
    relevant_ids_by_job: Mapping[str, set[str]],
    k_values: Sequence[int] = METRIC_K_VALUES,
) -> dict[str, AggregateMetrics]:
    maximum_k = max(k_values)
    results: dict[str, AggregateMetrics] = {}
    for strategy in (
        RetrievalStrategy.DENSE,
        RetrievalStrategy.SPARSE,
        RetrievalStrategy.HYBRID,
    ):
        query_metrics = []
        for job_id in query_ids:
            response = await service.retrieve_candidates(
                job_id,
                RetrievalRequest(strategy=strategy, top_k=maximum_k, filters=None),
            )
            query_metrics.append(
                evaluate_query(
                    [item.entity_id for item in response.results],
                    relevant_ids_by_job[job_id],
                    k_values=k_values,
                )
            )
        results[strategy.value] = aggregate_queries(query_metrics)
    return results
