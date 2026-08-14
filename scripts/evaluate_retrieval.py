from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_engine, get_session_factory  # noqa: E402
from app.exceptions import EvaluationIntegrityError  # noqa: E402
from app.repositories.candidate_repository import CandidateRepository  # noqa: E402
from app.repositories.job_repository import JobRepository  # noqa: E402
from app.services.retrieval.embedding import (  # noqa: E402
    SentenceTransformerEmbeddingProvider,
)
from app.services.retrieval.evaluation import (  # noqa: E402
    METRIC_K_VALUES,
    PHASE4_EVALUATION_PROTOCOL,
    PHASE4_RETRIEVAL_CONFIG,
    config_fingerprint,
    evaluate_split,
    load_frozen_benchmark,
    validate_evaluation_corpus,
)
from app.services.retrieval.service import RetrievalService  # noqa: E402
from app.services.retrieval.vector_store import QdrantDenseVectorStore  # noqa: E402


DEFAULT_REPORT = REPOSITORY_ROOT / "data" / "eval" / "phase4_retrieval_report_v4.json"


def _metrics_payload(metrics) -> dict[str, object]:
    payload = asdict(metrics)
    payload["recall_at_k"] = {
        f"recall_at_{k}": round(value, 6)
        for k, value in metrics.recall_at_k.items()
    }
    payload["hit_rate_at_k"] = {
        f"hit_rate_at_{k}": round(value, 6)
        for k, value in metrics.hit_rate_at_k.items()
        if k in {5, 10}
    }
    payload["mrr_at_20"] = round(payload.pop("mrr"), 6)
    return payload


def _load_test_seal(report_path: Path, fingerprint: str) -> dict[str, object]:
    if not report_path.exists():
        raise EvaluationIntegrityError("Dev-sealed report is required before test evaluation")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("config_fingerprint") != fingerprint:
        raise EvaluationIntegrityError("Config fingerprint changed after dev seal")
    metrics = report.get("metrics", {})
    if "dev" not in metrics:
        raise EvaluationIntegrityError("Dev metrics are required before test evaluation")
    if "test" in metrics:
        raise EvaluationIntegrityError("Test metrics already exist; refusing to rerun sealed test")
    return report


def _ensure_dev_report_writable(report_path: Path) -> None:
    if not report_path.exists():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if "test" in report.get("metrics", {}):
        raise EvaluationIntegrityError(
            "Sealed test metrics exist; dev evaluation cannot overwrite this report"
        )


def _validate_frozen_runtime_settings(settings) -> None:
    actual = {
        "embedding_provider": settings.retrieval_embedding_provider,
        "embedding_model": settings.retrieval_embedding_model,
        "embedding_dimension": settings.retrieval_embedding_dimension,
        "rrf_k": settings.retrieval_rrf_k,
        "bm25_k1": settings.retrieval_bm25_k1,
        "bm25_b": settings.retrieval_bm25_b,
        "pool_minimum": settings.retrieval_pool_minimum,
        "pool_multiplier": settings.retrieval_pool_multiplier,
    }
    mismatches = [
        key for key, value in actual.items() if PHASE4_RETRIEVAL_CONFIG[key] != value
    ]
    if mismatches:
        raise EvaluationIntegrityError(
            "Runtime retrieval settings differ from frozen evaluation config: "
            + ", ".join(mismatches)
        )


async def run(split: str, report_path: Path) -> int:
    fingerprint = config_fingerprint(PHASE4_RETRIEVAL_CONFIG)
    if split == "test":
        sealed_report = _load_test_seal(report_path, fingerprint)
    else:
        _ensure_dev_report_writable(report_path)
        sealed_report = None
    settings = get_settings()
    _validate_frozen_runtime_settings(settings)
    benchmark = load_frozen_benchmark(REPOSITORY_ROOT)
    provider = SentenceTransformerEmbeddingProvider(
        model_name=settings.retrieval_embedding_model,
        dimension=settings.retrieval_embedding_dimension,
    )
    store = QdrantDenseVectorStore(url=settings.qdrant_url)
    try:
        async with get_session_factory()() as session:
            candidate_repository = CandidateRepository(session)
            job_repository = JobRepository(session)
            candidates = await candidate_repository.list_all_records()
            queries = benchmark.splits[split]
            validate_evaluation_corpus(
                actual_candidate_ids={item.candidate_id for item in candidates},
                expected_candidate_ids=benchmark.candidate_ids,
                query_ids=set(queries),
                expected_job_ids=benchmark.job_ids,
            )
            service = RetrievalService(
                candidate_repository=candidate_repository,
                job_repository=job_repository,
                embedding_provider=provider,
                vector_store=store,
                candidate_collection=settings.retrieval_candidate_collection,
                job_collection=settings.retrieval_job_collection,
                rrf_k=settings.retrieval_rrf_k,
                bm25_k1=settings.retrieval_bm25_k1,
                bm25_b=settings.retrieval_bm25_b,
                pool_minimum=settings.retrieval_pool_minimum,
                pool_multiplier=settings.retrieval_pool_multiplier,
            )
            metrics = await evaluate_split(
                service=service,
                query_ids=queries,
                relevant_ids_by_job=benchmark.relevant_ids_by_job,
                k_values=METRIC_K_VALUES,
            )

        base = {
            "phase": "4",
            "status": "in_progress",
            "interpretation": PHASE4_EVALUATION_PROTOCOL["interpretation"],
            "evaluation_protocol": PHASE4_EVALUATION_PROTOCOL,
            "dataset_version": "1.0.0",
            "schema_version": "1.0",
            "judgment_coverage": {
                "labeled_pairs": len(benchmark.labels),
                "possible_pairs": benchmark.total_possible_pairs,
                "judgments_per_query": benchmark.judgments_per_query,
                "complete": benchmark.judgments_complete,
            },
            "retrieval_config": PHASE4_RETRIEVAL_CONFIG,
            "config_fingerprint": fingerprint,
            "test_seal": {
                "scope": "v4_internal_only",
                "pristine_held_out": False,
                "sealed_after_dev": True,
                "test_tuning_permitted": False,
            },
            "metrics": {},
        }
        if sealed_report is not None:
            base = sealed_report
        base["metrics"][split] = {
            strategy: _metrics_payload(value) for strategy, value in metrics.items()
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(base, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Evaluation PASS: split={split}; config_fingerprint={fingerprint}")
        for strategy, value in base["metrics"][split].items():
            print(f"{strategy}: {json.dumps(value, sort_keys=True)}")
        return 0
    finally:
        await store.client.close()
        await get_engine().dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate sealed Phase 4 retrieval.")
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return asyncio.run(run(args.split, args.report.resolve()))


if __name__ == "__main__":
    raise SystemExit(main())
