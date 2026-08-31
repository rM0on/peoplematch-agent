from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_engine, get_session_factory  # noqa: E402
from app.repositories.candidate_repository import CandidateRepository  # noqa: E402
from app.repositories.job_repository import JobRepository  # noqa: E402
from app.services.cross_encoder.model import load_cross_encoder_model  # noqa: E402
from app.services.cross_encoder.service import CrossEncoderRerankingService  # noqa: E402
from app.services.evaluation import METRIC_SEMANTICS_VERSION, PROTOCOL_VERSION  # noqa: E402
from app.services.evaluation.artifacts import ArtifactWriter  # noqa: E402
from app.services.evaluation.errors import EvaluationIntegrityError  # noqa: E402
from app.services.evaluation.guard import TestSeal, validate_split_request  # noqa: E402
from app.services.evaluation.judgments import load_frozen_judgments  # noqa: E402
from app.services.evaluation.runner import evaluate_queries  # noqa: E402
from app.services.evaluation.slices import evaluate_predeclared_slices  # noqa: E402
from app.services.evaluation.strategies import FrozenStrategyAdapter, IndexedQueryEmbeddingProvider, qdrant_index_fingerprint  # noqa: E402
from app.services.features.contract import FEATURE_FINGERPRINT  # noqa: E402
from app.services.features.service import FeatureEngineeringService  # noqa: E402
from app.services.ranking.model import load_ranking_model  # noqa: E402
from app.services.ranking.service import RankingService  # noqa: E402
from app.services.retrieval.documents import RETRIEVAL_DOCUMENT_VERSION, build_job_document  # noqa: E402
from app.services.retrieval.service import RetrievalService  # noqa: E402
from app.services.retrieval.vector_store import QdrantDenseVectorStore  # noqa: E402
from app.services.match_runs.contracts import canonical_fingerprint  # noqa: E402
from app.services.match_runs.contracts import RETRIEVAL_CONFIGURATION_FINGERPRINT  # noqa: E402


FROZEN_TEST_SEAL = TestSeal(
    protocol=canonical_fingerprint({"protocol": PROTOCOL_VERSION}),
    metrics=canonical_fingerprint({"metrics": METRIC_SEMANTICS_VERSION}),
    strategies=canonical_fingerprint({"r1": ["dense_v4", "sparse_bm25_v4", "hybrid_rrf_v4"], "r2": ["hybrid_rrf_v4", "ltr_ranker_v1", "cross_encoder_experiment"]}),
    slices=canonical_fingerprint({"registry": "phase11_predeclared_slices_v1"}),
    report=canonical_fingerprint({"report": "phase11_report_v1"}),
)


def _git(command: str) -> str:
    return subprocess.run(["git", *command.split()], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _source_tree_fingerprint() -> str:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    digest = hashlib.sha256()
    for relative in sorted(listed):
        normalized = relative.replace("\\", "/")
        if normalized.startswith("artifacts/") or normalized.startswith("data/eval/phase11/runs/"):
            continue
        path = ROOT / relative
        if path.is_file():
            digest.update(normalized.encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _report(quality: dict[str, Any], split: str) -> str:
    lines = [
        "# Phase 11 Offline Evaluation — " + split.title(), "",
        f"Protocol: `{PROTOCOL_VERSION}`",
        f"Metric semantics: `{METRIC_SEMANTICS_VERSION}`", "",
        "This report is descriptive evidence on synthetic sandbox judgments. It is not production, hiring-accuracy, or generalization evidence.", "",
        "## R1 Retrieval", "",
    ]
    for strategy, metrics in quality["r1"]["strategies"].items():
        lines.append(f"- {strategy}: Recall@5={metrics['retrieval_recall_at_5']['mean']:.6f}, Recall@10={metrics['retrieval_recall_at_10']['mean']:.6f}, Recall@20={metrics['retrieval_recall_at_20']['mean']:.6f}")
    lines += ["", f"Leader by frozen rule: {', '.join(quality['r1']['leader']['strategy_ids'])}", "", "## R2 Controlled Ranking", ""]
    for strategy, metrics in quality["r2"]["strategies"].items():
        lines.append(f"- {strategy}: NDCG@5={metrics['judged_condensed_ndcg_at_5']['mean']:.6f}, NDCG@10={metrics['judged_condensed_ndcg_at_10']['mean']:.6f}, MRR@10={metrics['judged_condensed_mrr_at_10']['mean']:.6f}, pairwise={metrics['explicit_pairwise_accuracy']['mean']:.6f}")
    lines += ["", f"Leader by frozen rule: {', '.join(quality['r2']['leader']['strategy_ids'])}", "", "## Boundaries", "", "- Standard Precision@K: rejected under incomplete judgments.", "- Explanation diagnostics: NOT RUN; no frozen persisted Dev ExplanationRun input set is registered.", "- Phase 10 review diagnostics: NOT RUN; review exports are diagnostic-only and not relevance truth.", "- Formal Test: SEALED / NOT RUN.", "- Phase 4 Test is already exposed and can only support a post-exposure fixed synthetic sandbox benchmark.", ""]
    return "\n".join(lines)


async def _run(args: argparse.Namespace) -> int:
    bundle = load_frozen_judgments(ROOT)
    query_ids = bundle.splits[args.split]
    split_by_query = {query_id: split for split, ids in bundle.splits.items() for query_id in ids}
    source_dirty = bool(_git("status --porcelain"))
    seal_payload = json.loads((ROOT / "data/contracts/phase11_test_seal_v1.json").read_text(encoding="utf-8"))
    expected_test_seal = TestSeal.model_validate({key: seal_payload[key] for key in TestSeal.model_fields})
    validate_split_request(
        args.split, query_ids, allow_test=args.allow_test,
        expected=expected_test_seal, actual=FROZEN_TEST_SEAL,
        split_by_query=split_by_query, source_dirty=source_dirty,
    )
    settings = get_settings()
    store = QdrantDenseVectorStore(url=settings.qdrant_url)
    index_fingerprint = await qdrant_index_fingerprint(
        store,
        [settings.retrieval_candidate_collection, settings.retrieval_job_collection],
    )
    dataset_manifest = json.loads((ROOT / "data/eval/dataset_freeze_manifest.json").read_text(encoding="utf-8"))
    source_tree_fingerprint = args.source_tree_fingerprint or _source_tree_fingerprint()
    identity = {
        "protocol_version": PROTOCOL_VERSION,
        "metric_semantics_version": METRIC_SEMANTICS_VERSION,
        "dataset_version": "1.0.0",
        "dataset_fingerprint": bundle.dataset_fingerprint,
        "split": args.split,
        "query_ids": list(query_ids),
        "source_commit_sha": args.source_commit_sha or _git("rev-parse HEAD"),
        "source_tree_fingerprint": source_tree_fingerprint,
        "source_state": {
            "dirty": source_dirty,
            "command": "scripts/run_offline_evaluation.py --split <split> --include-r3 --output-root <path> --run-id <id>",
            "implementation_package": "backend.app.services.evaluation",
        },
        "dataset_contract": {
            "schema_version": "1.0", "origin": "synthetic_sandbox",
            "annotation_source": "synthetic_curated", "candidate_count": 48,
            "job_count": 24, "graded_judgment_count": 288,
            "pairwise_count": 48, "canonical_file_sha256": dataset_manifest["canonical_files"],
        },
        "strategy_config": {"r1": ["dense_v4", "sparse_bm25_v4", "hybrid_rrf_v4"], "r2_pool_depth": 48, "r3": bool(args.include_r3)},
        "candidate_pool_config": {"universe": "all_48_candidates", "filters": [], "r2_condensed_judged_count": 12},
        "model_artifacts": {
            "ltr_model_sha256": "c8f235ebd95dce611f892394859f9f0251f43f8822a39bd316c404d9ff75a000",
            "ce_snapshot_fingerprint": "013355448b38f6190a4d7250b1d062f76caddd8a5f1cabc47bdc716490a60236",
        },
        "feature_fingerprint": FEATURE_FINGERPRINT,
        "retrieval_document_version": RETRIEVAL_DOCUMENT_VERSION,
        "retrieval_config_fingerprint": RETRIEVAL_CONFIGURATION_FINGERPRINT,
        "retrieval_index_fingerprint": index_fingerprint,
        "judgment_policy": {
            "primary_threshold": "broad_relevance_v1:grade>=2",
            "diagnostic_threshold": "strong_relevance_v1:grade==3",
            "gain_by_grade": [0, 1, 3, 7],
            "missing_judgment": "unjudged_is_not_negative",
            "aggregation": "macro_arithmetic_mean",
        },
        "metric_specs": {
            "r1": ["retrieval_recall_at_5", "retrieval_recall_at_10", "retrieval_recall_at_20"],
            "r2": ["judged_condensed_ndcg_at_5", "judged_condensed_ndcg_at_10", "judged_condensed_mrr_at_10", "explicit_pairwise_accuracy"],
            "standard_precision_at_k": "REJECTED",
        },
        "random_seed": None,
        "claim_limitations": ["synthetic_sandbox", "synthetic_curated", "incomplete_judgments", "descriptive_only", "no_production_or_hiring_accuracy_claim"],
        "test_seal": FROZEN_TEST_SEAL.model_dump(mode="json"),
        "phase4_test_exposure": "post_exposure_fixed_synthetic_sandbox_benchmark",
    }
    identity["evaluation_input_fingerprint"] = canonical_fingerprint(
        {key: value for key, value in identity.items() if key not in {"source_state"}}
    )
    writer = ArtifactWriter(Path(args.output_root), args.run_id, identity)
    writer.start()
    try:
        async with get_session_factory()() as session:
            candidate_repository = CandidateRepository(session)
            job_repository = JobRepository(session)
            jobs = await job_repository.list_all_records()
            embedding = IndexedQueryEmbeddingProvider(
                store=store,
                collection_name=settings.retrieval_job_collection,
                query_documents={item.job_id: build_job_document(item) for item in jobs},
                model_name=settings.retrieval_embedding_model,
                dimension=settings.retrieval_embedding_dimension,
            )
            retrieval = RetrievalService(
                candidate_repository=candidate_repository, job_repository=job_repository,
                embedding_provider=embedding, vector_store=store,
                candidate_collection=settings.retrieval_candidate_collection,
                job_collection=settings.retrieval_job_collection, rrf_k=settings.retrieval_rrf_k,
                bm25_k1=settings.retrieval_bm25_k1, bm25_b=settings.retrieval_bm25_b,
                pool_minimum=settings.retrieval_pool_minimum, pool_multiplier=settings.retrieval_pool_multiplier,
            )
            feature_service = FeatureEngineeringService(retrieval_service=retrieval, candidate_repository=candidate_repository, job_repository=job_repository)
            ltr_model = load_ranking_model(model_path=Path(settings.ranking_model_path), metadata_path=Path(settings.ranking_model_metadata_path))
            ranking = RankingService(feature_service=feature_service, ranking_model=ltr_model)
            ce_model = load_cross_encoder_model(model_path=Path(settings.cross_encoder_model_path), manifest_path=Path(settings.cross_encoder_model_manifest_path), text_contract_path=Path(settings.cross_encoder_text_contract_path))
            ce = CrossEncoderRerankingService(ranking_service=ranking, cross_encoder_model=ce_model, job_repository=job_repository, candidate_repository=candidate_repository, batch_size=settings.cross_encoder_batch_size)
            adapter = FrozenStrategyAdapter(retrieval_service=retrieval, ranking_service=ranking, cross_encoder_service=ce, ltr_model=ltr_model, ce_model=ce_model)
            quality = await evaluate_queries(
                adapter=adapter, query_ids=query_ids, candidate_ids=bundle.candidate_ids,
                grades_by_job=bundle.grades_by_job, pairs_by_job=bundle.pairs_by_job,
                include_r3=args.include_r3,
                dataset_fingerprint=bundle.dataset_fingerprint,
                index_fingerprint=index_fingerprint,
            )
            orders_by_strategy = {
                strategy: {
                    query_id: quality["r2"]["per_query_pool_provenance"][query_id][strategy]["ordered_candidate_ids"]
                    for query_id in query_ids
                }
                for strategy in quality["r2"]["strategies"]
            }
            quality["slices"] = evaluate_predeclared_slices(
                labels=bundle.labels,
                query_ids=query_ids,
                orders_by_strategy=orders_by_strategy,
                high_overclaim_candidate_ids={
                    candidate.candidate_id
                    for candidate in bundle.candidates
                    if candidate.overclaim_risk.level.value == "high"
                },
            )
            quality["explanation"] = {"status": "NOT_RUN", "reason": "no frozen persisted Dev ExplanationRun evaluation input set is registered"}
        writer.complete(
            quality=quality,
            diagnostics={
                "latency_protocol": {"status": "NOT_RUN", "reason": "50-observation-per-stage latency campaign is deferred; quality run timings are not substituted"},
                "phase10_review": {"status": "NOT_RUN", "reason": "no explicit Phase10 review export input was supplied"},
                "limitations": ["synthetic curated judgments", "incomplete judgment matrix", "descriptive only", "latency excluded from quality fingerprint"],
            },
            warnings=["unjudged candidates are not negatives", "CE remains experiment-only", "formal Test was not run"],
            report=_report(quality, args.split),
        )
        print(f"Phase 11 {args.split} evaluation COMPLETED: {writer.final}")
        return 0
    except EvaluationIntegrityError as error:
        writer.invalidate(str(error))
        print(f"Phase 11 evaluation INVALID: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        writer.fail(f"{type(error).__name__}: {error}")
        print(f"Phase 11 evaluation FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 3
    finally:
        await store.client.close()
        await get_engine().dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen Phase 11 offline evaluation.")
    parser.add_argument("--split", choices=("train", "dev", "test"), default="dev")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/phase11/runs")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--include-r3", action="store_true")
    parser.add_argument("--source-commit-sha")
    parser.add_argument("--source-tree-fingerprint")
    parser.add_argument("--allow-test", action="store_true", help="Explicit Test safety rail; do not use during implementation.")
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
