from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace


FEATURE_ORDER = (
    "semantic_score",
    "sparse_score",
    "skill_fit_score",
    "project_evidence_score",
    "role_direction_score",
    "ai_tool_score",
    "location_score",
    "seniority_score",
    "missing_penalty",
    "overclaim_penalty",
)


def _payload() -> dict:
    feature = [0.1, 2.0, 1.0, 0.5, 0.25, 0.0, 1.0, 1.0, 0.0, None]
    return {
        "schema_version": "1.0",
        "dataset_version": "1.0.0",
        "feature_version": "feature_schema_v1",
        "feature_fingerprint": "dc85c7237c6c67785199d221c919ae48c31c9a6323857070e6399d3eae365e42",
        "model_feature_order": list(FEATURE_ORDER),
        "retrieval": {"strategy": "hybrid", "top_k": 48},
        "source_fingerprints": {"freeze": "a" * 64, "retrieval": "b" * 64},
        "splits": {
            "train": {
                "query_ids": ["job_001"],
                "group_sizes": [2],
                "row_count": 2,
                "label_distribution": {"0": 1, "3": 1},
                "rows": [
                    {"split": "train", "job_id": "job_001", "candidate_id": "cand_001", "relevance_grade": 3, "feature_vector": feature},
                    {"split": "train", "job_id": "job_001", "candidate_id": "cand_002", "relevance_grade": 0, "feature_vector": feature},
                ],
            },
            "dev": {
                "query_ids": ["job_015"],
                "group_sizes": [1],
                "row_count": 1,
                "label_distribution": {"2": 1},
                "rows": [
                    {"split": "dev", "job_id": "job_015", "candidate_id": "cand_003", "relevance_grade": 2, "feature_vector": feature}
                ],
            },
        },
    }


def test_dataset_fingerprint_is_stable_and_excludes_self_field() -> None:
    from app.services.ranking.dataset import attach_dataset_fingerprint, validate_dataset_fingerprint

    first = attach_dataset_fingerprint(_payload())
    second = attach_dataset_fingerprint(_payload())

    assert first == second
    assert len(first["ltr_dataset_fingerprint"]) == 64
    validate_dataset_fingerprint(first)


def test_training_matrix_uses_only_exact_feature_order_and_native_nan() -> None:
    from app.services.ranking.dataset import matrix_for_split

    artifact = attach = __import__(
        "app.services.ranking.dataset", fromlist=["attach_dataset_fingerprint"]
    ).attach_dataset_fingerprint(_payload())
    matrix = matrix_for_split(artifact, "train")

    assert matrix.features.shape == (2, 10)
    assert matrix.labels.tolist() == [3, 0]
    assert matrix.groups == [2]
    assert matrix.query_ids == ["job_001"]
    assert math.isnan(matrix.features[0, 9])
    assert matrix.pair_ids == [("job_001", "cand_001"), ("job_001", "cand_002")]


def test_matrix_rejects_feature_order_mismatch_and_test_split() -> None:
    import pytest

    from app.services.ranking.dataset import DatasetIntegrityError, attach_dataset_fingerprint, matrix_for_split

    payload = _payload()
    payload["model_feature_order"].reverse()
    artifact = attach_dataset_fingerprint(payload)
    with pytest.raises(DatasetIntegrityError):
        matrix_for_split(artifact, "train")
    with pytest.raises(DatasetIntegrityError):
        matrix_for_split(attach_dataset_fingerprint(_payload()), "test")


def test_builder_uses_only_explicit_train_dev_judgments_and_frozen_features() -> None:
    import asyncio

    from app.schemas.retrieval import RetrievalResult
    from app.services.dataset_validation import load_dataset
    from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION
    from app.services.features.extractor import extract_pair_features
    from app.services.ranking.dataset import build_ltr_dataset

    root = Path(__file__).resolve().parents[2]
    bundle = load_dataset(root)
    candidates = sorted(bundle.candidates, key=lambda item: item.candidate_id)
    jobs = {item.job_id: item for item in bundle.jobs}

    class FrozenFeaturePath:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, int]] = []

        async def features_for_job_candidates(self, job_id, request):
            self.calls.append((job_id, request.strategy.value, request.top_k))
            results = []
            for rank, candidate in enumerate(candidates, start=1):
                retrieval = RetrievalResult(
                    entity_id=candidate.candidate_id,
                    rank=rank,
                    matched_channels=["dense", "sparse"],
                    dense_rank=rank,
                    dense_score=rank / 100,
                    sparse_rank=rank,
                    sparse_score=float(rank),
                    fusion_score=1 / (60 + rank),
                )
                extraction = extract_pair_features(candidate, jobs[job_id], retrieval)
                results.append(
                    SimpleNamespace(
                        entity_id=candidate.candidate_id,
                        retrieval=retrieval,
                        feature_vector=extraction.vector,
                    )
                )
            return SimpleNamespace(
                feature_version=FEATURE_VERSION,
                feature_fingerprint=FEATURE_FINGERPRINT,
                results=results,
                retrieval_diagnostics=SimpleNamespace(
                    returned_count=48,
                    corpus_size=48,
                    eligible_count=48,
                    dense_pool_size=48,
                    sparse_pool_size=48,
                ),
            )

    service = FrozenFeaturePath()
    artifact = asyncio.run(
        build_ltr_dataset(
            feature_service=service,
            bundle=bundle,
            repository_root=root,
        )
    )

    assert len(service.calls) == 19
    assert all(strategy == "hybrid" and top_k == 48 for _, strategy, top_k in service.calls)
    assert artifact["splits"]["train"]["row_count"] == 168
    assert artifact["splits"]["dev"]["row_count"] == 60
    assert artifact["splits"]["train"]["group_sizes"] == [12] * 14
    assert artifact["splits"]["dev"]["group_sizes"] == [12] * 5
    assert set(artifact["splits"]) == {"train", "dev"}
    rows = [
        *artifact["splits"]["train"]["rows"],
        *artifact["splits"]["dev"]["rows"],
    ]
    assert len(rows) == 228
    assert len({(row["job_id"], row["candidate_id"]) for row in rows}) == 228
    assert all(len(row["feature_vector"]) == 10 for row in rows)
    assert all(
        set(row) == {"split", "job_id", "candidate_id", "relevance_grade", "feature_vector"}
        for row in rows
    )
    assert not any(row["job_id"] in {"job_020", "job_021", "job_022", "job_023", "job_024"} for row in rows)
    assert artifact["source_fingerprints"]["dataset_freeze_manifest_sha256"]
    assert artifact["source_fingerprints"]["retrieval_configuration_fingerprint"]


def test_builder_rejects_missing_judged_pair_and_incomplete_retrieval_pool() -> None:
    import asyncio
    import pytest

    from app.services.dataset_validation import load_dataset
    from app.services.ranking.dataset import DatasetIntegrityError, build_ltr_dataset

    root = Path(__file__).resolve().parents[2]
    bundle = load_dataset(root)

    class IncompleteFeaturePath:
        async def features_for_job_candidates(self, job_id, request):
            return SimpleNamespace(
                feature_version="feature_schema_v1",
                feature_fingerprint="dc85c7237c6c67785199d221c919ae48c31c9a6323857070e6399d3eae365e42",
                results=[],
                retrieval_diagnostics=SimpleNamespace(
                    returned_count=0,
                    corpus_size=48,
                    eligible_count=48,
                    dense_pool_size=0,
                    sparse_pool_size=0,
                ),
            )

    with pytest.raises(DatasetIntegrityError, match="48 Candidates"):
        asyncio.run(
            build_ltr_dataset(
                feature_service=IncompleteFeaturePath(),
                bundle=bundle,
                repository_root=root,
            )
        )


def test_phase6_label_loader_materializes_train_dev_only() -> None:
    from app.services.dataset_validation import load_relevance_labels, load_query_splits

    root = Path(__file__).resolve().parents[2]
    query_splits = load_query_splits(root)
    allowed_jobs = {
        job_id for job_id, split in query_splits.items() if split in {"train", "dev"}
    }

    labels = load_relevance_labels(root, allowed_jobs)

    assert len(labels) == 228
    assert {label.job_id for label in labels} == allowed_jobs
    assert all(label.split.value in {"train", "dev"} for label in labels)
    assert not any(label.job_id in {"job_020", "job_021", "job_022", "job_023", "job_024"} for label in labels)


def test_phase6_label_loader_rejects_test_job_requests() -> None:
    import pytest

    from app.services.dataset_validation import DatasetValidationError, load_relevance_labels

    root = Path(__file__).resolve().parents[2]
    with pytest.raises(DatasetValidationError, match="Test jobs"):
        load_relevance_labels(root, {"job_020"})


def test_matrix_rejects_row_split_and_query_identity_mismatches() -> None:
    import pytest

    from app.services.ranking.dataset import DatasetIntegrityError, attach_dataset_fingerprint, matrix_for_split

    split_mismatch = _payload()
    split_mismatch["splits"]["train"]["rows"][0]["split"] = "dev"
    with pytest.raises(DatasetIntegrityError, match="row split"):
        matrix_for_split(attach_dataset_fingerprint(split_mismatch), "train")

    query_mismatch = _payload()
    query_mismatch["splits"]["train"]["rows"][0]["job_id"] = "job_016"
    with pytest.raises(DatasetIntegrityError, match="query block"):
        matrix_for_split(attach_dataset_fingerprint(query_mismatch), "train")


def test_matrix_rejects_noncontiguous_query_groups_and_invalid_group_sizes() -> None:
    import pytest

    from app.services.ranking.dataset import DatasetIntegrityError, attach_dataset_fingerprint, matrix_for_split

    payload = _payload()
    base_rows = payload["splits"]["train"]["rows"]
    payload["splits"]["train"] = {
        "query_ids": ["job_001", "job_002", "job_001"],
        "group_sizes": [1, 1, 1],
        "row_count": 3,
        "label_distribution": {"0": 2, "3": 1},
        "rows": [
            {**base_rows[0], "job_id": "job_001", "candidate_id": "cand_001"},
            {**base_rows[1], "job_id": "job_002", "candidate_id": "cand_002"},
            {**base_rows[0], "job_id": "job_001", "candidate_id": "cand_003"},
        ],
    }
    with pytest.raises(DatasetIntegrityError, match="noncontiguous"):
        matrix_for_split(attach_dataset_fingerprint(payload), "train")

    invalid_group = _payload()
    invalid_group["splits"]["train"]["group_sizes"] = [0, 2]
    with pytest.raises(DatasetIntegrityError, match="positive"):
        matrix_for_split(attach_dataset_fingerprint(invalid_group), "train")


def test_matrix_rejects_wrong_width_and_duplicate_pairs() -> None:
    import pytest

    from app.services.ranking.dataset import DatasetIntegrityError, attach_dataset_fingerprint, matrix_for_split

    wrong_width = _payload()
    wrong_width["splits"]["train"]["rows"][0]["feature_vector"] = [0.0]
    with pytest.raises(DatasetIntegrityError, match="width"):
        matrix_for_split(attach_dataset_fingerprint(wrong_width), "train")

    duplicate = _payload()
    duplicate["splits"]["train"]["rows"][1]["candidate_id"] = "cand_001"
    with pytest.raises(DatasetIntegrityError, match="duplicate pair"):
        matrix_for_split(attach_dataset_fingerprint(duplicate), "train")


def test_source_provenance_rejects_canonical_hash_mismatch(tmp_path) -> None:
    import json
    import pytest

    from app.services.ranking.dataset import DatasetIntegrityError, _source_provenance

    manifest_path = tmp_path / "data/eval/dataset_freeze_manifest.json"
    retrieval_path = tmp_path / "data/eval/phase4_retrieval_report_v4.json"
    source_path = tmp_path / "data/samples/candidates.jsonl"
    manifest_path.parent.mkdir(parents=True)
    source_path.parent.mkdir(parents=True)
    source_path.write_text("canonical", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "dataset_version": "1.0.0",
                "canonical_files": {"data/samples/candidates.jsonl": "0" * 64},
            }
        ),
        encoding="utf-8",
    )
    retrieval_path.write_text(json.dumps({"config_fingerprint": "f" * 64}), encoding="utf-8")

    with pytest.raises(DatasetIntegrityError, match="hash mismatch"):
        _source_provenance(tmp_path)
