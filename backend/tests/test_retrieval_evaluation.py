from __future__ import annotations

import json
import asyncio
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


EXPECTED_V4_FINGERPRINT = (
    "b004bc52c33f3e15bf38dba1777305039909bb5229261dcf1851b289e7c8f2e7"
)
EXPECTED_V4_METRICS = {
    "dev": {
        "dense": {
            "hit_rate_at_k": {"hit_rate_at_10": 0.8, "hit_rate_at_5": 0.4},
            "mrr_at_20": 0.453333,
            "query_count": 5,
            "recall_at_k": {
                "recall_at_10": 0.4,
                "recall_at_20": 0.7,
                "recall_at_5": 0.22,
            },
        },
        "hybrid": {
            "hit_rate_at_k": {"hit_rate_at_10": 0.8, "hit_rate_at_5": 0.8},
            "mrr_at_20": 0.666667,
            "query_count": 5,
            "recall_at_k": {
                "recall_at_10": 0.66,
                "recall_at_20": 0.85,
                "recall_at_5": 0.4,
            },
        },
        "sparse": {
            "hit_rate_at_k": {"hit_rate_at_10": 1.0, "hit_rate_at_5": 1.0},
            "mrr_at_20": 0.766667,
            "query_count": 5,
            "recall_at_k": {
                "recall_at_10": 0.77,
                "recall_at_20": 0.86,
                "recall_at_5": 0.68,
            },
        },
    },
    "test": {
        "dense": {
            "hit_rate_at_k": {"hit_rate_at_10": 0.8, "hit_rate_at_5": 0.8},
            "mrr_at_20": 0.477778,
            "query_count": 5,
            "recall_at_k": {
                "recall_at_10": 0.42,
                "recall_at_20": 0.7,
                "recall_at_5": 0.42,
            },
        },
        "hybrid": {
            "hit_rate_at_k": {"hit_rate_at_10": 1.0, "hit_rate_at_5": 0.8},
            "mrr_at_20": 0.728571,
            "query_count": 5,
            "recall_at_k": {
                "recall_at_10": 0.66,
                "recall_at_20": 0.9,
                "recall_at_5": 0.47,
            },
        },
        "sparse": {
            "hit_rate_at_k": {"hit_rate_at_10": 1.0, "hit_rate_at_5": 1.0},
            "mrr_at_20": 0.866667,
            "query_count": 5,
            "recall_at_k": {
                "recall_at_10": 0.8,
                "recall_at_20": 0.95,
                "recall_at_5": 0.67,
            },
        },
    },
}


def test_v4_report_discloses_prior_test_exposure_without_changing_results() -> None:
    report = json.loads(
        (REPOSITORY_ROOT / "data/eval/phase4_retrieval_report_v4.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["config_fingerprint"] == EXPECTED_V4_FINGERPRINT
    assert report["metrics"] == EXPECTED_V4_METRICS
    assert report["interpretation"] == (
        "post-exposure fixed synthetic sandbox benchmark"
    )
    assert report["evaluation_protocol"] == {
        "exposed_predecessor_versions": [
            "retrieval_doc_v1",
            "retrieval_doc_v2",
            "retrieval_doc_v3",
        ],
        "interpretation": "post-exposure fixed synthetic sandbox benchmark",
        "prior_test_exposure": True,
        "pristine_held_out": False,
    }
    assert report["test_seal"] == {
        "pristine_held_out": False,
        "scope": "v4_internal_only",
        "sealed_after_dev": True,
        "test_tuning_permitted": False,
    }


def test_report_generation_metadata_matches_the_disclosed_protocol() -> None:
    from app.services.retrieval.evaluation import PHASE4_EVALUATION_PROTOCOL

    assert PHASE4_EVALUATION_PROTOCOL == {
        "exposed_predecessor_versions": [
            "retrieval_doc_v1",
            "retrieval_doc_v2",
            "retrieval_doc_v3",
        ],
        "interpretation": "post-exposure fixed synthetic sandbox benchmark",
        "prior_test_exposure": True,
        "pristine_held_out": False,
    }


def test_evaluation_documentation_discloses_exposure_and_dense_truncation() -> None:
    evaluation_doc = (
        REPOSITORY_ROOT / "docs/retrieval-evaluation.md"
    ).read_text(encoding="utf-8")
    design_doc = (REPOSITORY_ROOT / "docs/retrieval-design.md").read_text(
        encoding="utf-8"
    )
    combined = f"{evaluation_doc}\n{design_doc}".casefold()

    assert "development used train/dev behavior only" not in combined
    assert "## test exposure history" in evaluation_doc.casefold()
    assert "post-exposure fixed synthetic sandbox benchmark" in combined
    assert "not a pristine held-out" in combined
    assert "48 / 48" in combined
    assert "23 / 24" in combined
    assert "256" in combined


def test_metrics_use_only_judged_relevant_items_and_do_not_assume_unlabeled_negative() -> None:
    from app.services.retrieval.evaluation import evaluate_query

    metrics = evaluate_query(
        retrieved_ids=["unlabeled", "relevant_b", "judged_negative", "relevant_a"],
        relevant_ids={"relevant_a", "relevant_b"},
        k_values=(2, 4),
    )

    assert metrics.recall_at_k == {2: 0.5, 4: 1.0}
    assert metrics.hit_rate_at_k == {2: 1.0, 4: 1.0}
    assert metrics.mrr == 0.5
    assert not hasattr(metrics, "precision_at_k")
    assert not hasattr(metrics, "ndcg_at_k")


def test_aggregate_metrics_average_queries_without_relevance_weighting() -> None:
    from app.services.retrieval.evaluation import aggregate_queries, evaluate_query

    first = evaluate_query(["a", "b"], {"a"}, k_values=(1, 2))
    second = evaluate_query(["x", "b"], {"b", "c"}, k_values=(1, 2))
    aggregate = aggregate_queries([first, second])

    assert aggregate.recall_at_k == {1: 0.5, 2: 0.75}
    assert aggregate.hit_rate_at_k == {1: 0.5, 2: 1.0}
    assert aggregate.mrr == pytest.approx(0.75)
    assert aggregate.query_count == 2


def test_report_labels_mrr_as_top_twenty_diagnostic() -> None:
    from app.services.retrieval.evaluation import aggregate_queries, evaluate_query
    from scripts.evaluate_retrieval import _metrics_payload

    first = evaluate_query(["a"], {"a"}, k_values=(5, 10, 20))
    aggregate = aggregate_queries([first])
    payload = _metrics_payload(aggregate)

    assert payload["mrr_at_20"] == 1.0
    assert "mrr" not in payload


def test_config_fingerprint_is_deterministic_and_changes_with_config() -> None:
    from app.services.retrieval.evaluation import (
        PHASE4_RETRIEVAL_CONFIG,
        config_fingerprint,
    )

    first = config_fingerprint(PHASE4_RETRIEVAL_CONFIG)
    second = config_fingerprint(dict(reversed(list(PHASE4_RETRIEVAL_CONFIG.items()))))
    changed = config_fingerprint({**PHASE4_RETRIEVAL_CONFIG, "rrf_k": 61})

    assert first == second
    assert len(first) == 64
    assert first != changed
    assert PHASE4_RETRIEVAL_CONFIG["document_version"] == "retrieval_doc_v4"
    assert "projects.name" not in PHASE4_RETRIEVAL_CONFIG["candidate_document_fields"]


def test_frozen_benchmark_has_incomplete_judgments_and_grade_two_threshold() -> None:
    from app.services.retrieval.evaluation import load_frozen_benchmark

    benchmark = load_frozen_benchmark(REPOSITORY_ROOT)

    assert len(benchmark.candidate_ids) == 48
    assert len(benchmark.job_ids) == 24
    assert len(benchmark.labels) == 288
    assert benchmark.judgments_per_query == 12
    assert benchmark.total_possible_pairs == 48 * 24
    assert benchmark.judgments_complete is False
    assert benchmark.relevance_threshold == 2
    assert benchmark.relevant_ids_by_job["job_001"]
    assert all(
        label.relevance_grade >= 2
        for label in benchmark.labels
        if label.candidate_id in benchmark.relevant_ids_by_job[label.job_id]
    )


def test_frozen_benchmark_rejects_canonical_hash_mismatch(tmp_path) -> None:
    from app.exceptions import EvaluationIntegrityError
    from app.services.retrieval.evaluation import load_frozen_benchmark

    shutil.copytree(REPOSITORY_ROOT / "data", tmp_path / "data")
    candidates = tmp_path / "data" / "samples" / "candidates.jsonl"
    candidates.write_text(
        candidates.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )

    with pytest.raises(EvaluationIntegrityError, match="freeze hash"):
        load_frozen_benchmark(tmp_path)


def test_evaluation_corpus_integrity_rejects_extra_or_missing_entities() -> None:
    from app.exceptions import EvaluationIntegrityError
    from app.services.retrieval.evaluation import validate_evaluation_corpus

    with pytest.raises(EvaluationIntegrityError, match="candidate corpus"):
        validate_evaluation_corpus(
            actual_candidate_ids={"cand_a", "cand_extra"},
            expected_candidate_ids={"cand_a"},
            query_ids={"job_a"},
            expected_job_ids={"job_a"},
        )
    with pytest.raises(EvaluationIntegrityError, match="query IDs"):
        validate_evaluation_corpus(
            actual_candidate_ids={"cand_a"},
            expected_candidate_ids={"cand_a"},
            query_ids={"job_extra"},
            expected_job_ids={"job_a"},
        )


def test_runtime_retrieval_sources_have_no_evaluation_data_dependency() -> None:
    runtime_root = REPOSITORY_ROOT / "backend" / "app" / "services" / "retrieval"
    runtime_files = [
        runtime_root / name
        for name in (
            "documents.py",
            "embedding.py",
            "sparse.py",
            "fusion.py",
            "vector_store.py",
            "indexing.py",
            "service.py",
        )
    ]
    prohibited = (
        "labels.jsonl",
        "pairwise_preferences",
        "query_splits",
        "relevance_grade",
        "hard_negative",
        "annotation_source",
        "retrieval.evaluation",
    )

    for path in runtime_files:
        source = path.read_text(encoding="utf-8")
        assert all(value not in source for value in prohibited), path.name


def test_changing_labels_cannot_change_runtime_retrieval_output() -> None:
    from app.schemas.retrieval import ChannelResult
    from app.services.retrieval.fusion import reciprocal_rank_fusion

    dense = [ChannelResult(entity_id="a", rank=1, score=0.9)]
    sparse = [ChannelResult(entity_id="b", rank=1, score=2.0)]
    before = reciprocal_rank_fusion(dense, sparse, rrf_k=60)
    labels = {"a": 0, "b": 3}
    labels.update({"a": 3, "b": 0})
    after = reciprocal_rank_fusion(dense, sparse, rrf_k=60)

    assert before == after
    assert labels == {"a": 3, "b": 0}


def test_split_evaluation_uses_same_queries_strategies_and_no_filters() -> None:
    from app.services.retrieval.evaluation import evaluate_split

    class Service:
        def __init__(self):
            self.calls = []

        async def retrieve_candidates(self, job_id, request):
            self.calls.append((job_id, request.strategy.value, request.top_k, request.filters))
            order = {
                "dense": ["cand_a", "cand_x", "cand_b"],
                "sparse": ["cand_x", "cand_b", "cand_a"],
                "hybrid": ["cand_b", "cand_a", "cand_x"],
            }[request.strategy.value]
            return SimpleNamespace(
                results=[SimpleNamespace(entity_id=entity_id) for entity_id in order]
            )

    service = Service()
    result = asyncio.run(
        evaluate_split(
            service=service,
            query_ids=["job_a", "job_b"],
            relevant_ids_by_job={
                "job_a": {"cand_a", "cand_b"},
                "job_b": {"cand_a", "cand_b"},
            },
            k_values=(1, 2, 3),
        )
    )

    assert set(result) == {"dense", "sparse", "hybrid"}
    assert result["hybrid"].recall_at_k == {1: 0.5, 2: 1.0, 3: 1.0}
    assert len(service.calls) == 6
    assert {call[0] for call in service.calls} == {"job_a", "job_b"}
    assert {call[1] for call in service.calls} == {"dense", "sparse", "hybrid"}
    assert all(call[2] == 3 and call[3] is None for call in service.calls)


def test_test_seal_preflight_rejects_rerun_before_evaluation(tmp_path) -> None:
    from app.exceptions import EvaluationIntegrityError
    from scripts.evaluate_retrieval import _load_test_seal

    report_path = tmp_path / "sealed-report.json"
    report_path.write_text(
        json.dumps(
            {
                "config_fingerprint": "frozen-config",
                "metrics": {"dev": {}, "test": {}},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EvaluationIntegrityError, match="refusing to rerun"):
        _load_test_seal(report_path, "frozen-config")


def test_dev_preflight_cannot_overwrite_a_sealed_test_report(tmp_path) -> None:
    from app.exceptions import EvaluationIntegrityError
    from scripts.evaluate_retrieval import _ensure_dev_report_writable

    report_path = tmp_path / "sealed-report.json"
    report_path.write_text(
        json.dumps({"metrics": {"dev": {}, "test": {}}}), encoding="utf-8"
    )

    with pytest.raises(EvaluationIntegrityError, match="cannot overwrite"):
        _ensure_dev_report_writable(report_path)


def test_evaluation_rejects_runtime_config_that_differs_from_fingerprint() -> None:
    from app.exceptions import EvaluationIntegrityError
    from scripts.evaluate_retrieval import _validate_frozen_runtime_settings

    settings = SimpleNamespace(
        retrieval_embedding_provider="sentence_transformers",
        retrieval_embedding_model="different-model",
        retrieval_embedding_dimension=384,
        retrieval_rrf_k=60,
        retrieval_bm25_k1=1.5,
        retrieval_bm25_b=0.75,
        retrieval_pool_minimum=20,
        retrieval_pool_multiplier=3,
    )

    with pytest.raises(EvaluationIntegrityError, match="embedding_model"):
        _validate_frozen_runtime_settings(settings)
