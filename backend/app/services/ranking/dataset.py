from __future__ import annotations

from copy import deepcopy
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from app.services.features.contract import MODEL_FEATURE_ORDER
from app.services.features.contract import FEATURE_FINGERPRINT, FEATURE_VERSION
from app.schemas.retrieval import RetrievalRequest, RetrievalStrategy


class DatasetIntegrityError(ValueError):
    """Raised when a derived LTR dataset violates its frozen contract."""


@dataclass(frozen=True)
class RankingMatrix:
    features: np.ndarray
    labels: np.ndarray
    groups: list[int]
    query_ids: list[str]
    pair_ids: list[tuple[str, str]]


def stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def attach_dataset_fingerprint(payload: dict[str, Any]) -> dict[str, Any]:
    canonical = deepcopy(payload)
    canonical.pop("ltr_dataset_fingerprint", None)
    fingerprint = hashlib.sha256(stable_json(canonical).encode("utf-8")).hexdigest()
    canonical["ltr_dataset_fingerprint"] = fingerprint
    return canonical


def validate_dataset_fingerprint(artifact: dict[str, Any]) -> None:
    expected = artifact.get("ltr_dataset_fingerprint")
    actual = attach_dataset_fingerprint(artifact)["ltr_dataset_fingerprint"]
    if expected != actual:
        raise DatasetIntegrityError("LTR dataset fingerprint mismatch")


def matrix_for_split(artifact: dict[str, Any], split: str) -> RankingMatrix:
    validate_dataset_fingerprint(artifact)
    if split not in {"train", "dev"}:
        raise DatasetIntegrityError("Only Train and Dev matrices are permitted")
    if tuple(artifact.get("model_feature_order", ())) != MODEL_FEATURE_ORDER:
        raise DatasetIntegrityError("LTR feature order differs from frozen Phase 5")
    split_payload = artifact.get("splits", {}).get(split)
    if not isinstance(split_payload, dict):
        raise DatasetIntegrityError(f"Missing {split} split")
    rows = split_payload.get("rows", [])
    if not isinstance(rows, list):
        raise DatasetIntegrityError("LTR rows must be a list")
    try:
        groups = [int(value) for value in split_payload.get("group_sizes", [])]
    except (TypeError, ValueError) as error:
        raise DatasetIntegrityError("LTR group sizes must be integers") from error
    if any(group <= 0 for group in groups):
        raise DatasetIntegrityError("LTR group sizes must be positive")
    if sum(groups) != len(rows):
        raise DatasetIntegrityError("LTR group sizes do not sum to row count")
    if split_payload.get("row_count") != len(rows):
        raise DatasetIntegrityError("LTR row_count does not match rows")
    query_ids = [str(value) for value in split_payload.get("query_ids", [])]
    if len(query_ids) != len(groups):
        raise DatasetIntegrityError("LTR query count differs from group count")
    if len(set(query_ids)) != len(query_ids):
        raise DatasetIntegrityError("LTR query groups are noncontiguous")

    feature_rows: list[list[float]] = []
    seen_jobs: set[str] = set()
    offset = 0
    for query_id, group_size in zip(query_ids, groups):
        block = rows[offset : offset + group_size]
        block_job_ids: set[str] = set()
        for row in block:
            if not isinstance(row, dict):
                raise DatasetIntegrityError("LTR rows must be objects")
            if row.get("split") != split:
                raise DatasetIntegrityError("LTR row split does not match requested split")
            job_id = str(row.get("job_id"))
            block_job_ids.add(job_id)
            if job_id != query_id:
                raise DatasetIntegrityError(
                    f"LTR query block {query_id} contains unexpected Job {job_id}"
                )
            if job_id in seen_jobs:
                raise DatasetIntegrityError("LTR query groups are noncontiguous")
            vector = row.get("feature_vector")
            if not isinstance(vector, list) or len(vector) != len(MODEL_FEATURE_ORDER):
                raise DatasetIntegrityError("LTR feature vector width is invalid")
            try:
                feature_rows.append(
                    [np.nan if value is None else float(value) for value in vector]
                )
            except (TypeError, ValueError) as error:
                raise DatasetIntegrityError("LTR feature vector contains a non-numeric value") from error
        if block_job_ids != {query_id}:
            raise DatasetIntegrityError("LTR query block contains multiple Jobs")
        seen_jobs.add(query_id)
        offset += group_size

    features = np.asarray(feature_rows, dtype=float)
    if features.shape != (len(rows), len(MODEL_FEATURE_ORDER)):
        raise DatasetIntegrityError("LTR feature matrix has an invalid shape")
    try:
        labels = np.asarray([int(row["relevance_grade"]) for row in rows], dtype=int)
    except (KeyError, TypeError, ValueError) as error:
        raise DatasetIntegrityError("LTR relevance grades must be integers") from error
    if not set(labels.tolist()) <= {0, 1, 2, 3}:
        raise DatasetIntegrityError("LTR labels must be integer grades zero through three")
    pair_ids = [(str(row["job_id"]), str(row["candidate_id"])) for row in rows]
    if len(set(pair_ids)) != len(pair_ids):
        raise DatasetIntegrityError("LTR dataset contains duplicate pair rows")
    return RankingMatrix(
        features=features,
        labels=labels,
        groups=groups,
        query_ids=query_ids,
        pair_ids=pair_ids,
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_provenance(repository_root: Path) -> tuple[str, dict[str, Any]]:
    manifest_path = repository_root / "data/eval/dataset_freeze_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    retrieval_report = json.loads(
        (repository_root / "data/eval/phase4_retrieval_report_v4.json").read_text(
            encoding="utf-8"
        )
    )
    canonical_files = manifest.get("canonical_files")
    if not isinstance(canonical_files, dict):
        raise DatasetIntegrityError("Dataset freeze manifest lacks canonical file hashes")
    for relative_path, expected_sha in canonical_files.items():
        source_path = repository_root / str(relative_path)
        if not source_path.is_file():
            raise DatasetIntegrityError(
                f"Canonical source file is missing: {relative_path}"
            )
        actual_sha = _file_sha256(source_path)
        if actual_sha != str(expected_sha):
            raise DatasetIntegrityError(
                f"Canonical source hash mismatch: {relative_path}"
            )

    return str(manifest["dataset_version"]), {
        "dataset_freeze_manifest_sha256": _file_sha256(manifest_path),
        "canonical_files": deepcopy(canonical_files),
        "retrieval_configuration_fingerprint": str(
            retrieval_report["config_fingerprint"]
        ),
    }


async def build_ltr_dataset(*, feature_service, bundle, repository_root: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    dataset_version, source_fingerprints = _source_provenance(root)
    labels_by_job: dict[str, dict[str, Any]] = defaultdict(dict)
    for label in bundle.labels:
        if label.split.value not in {"train", "dev"}:
            continue
        if label.candidate_id in labels_by_job[label.job_id]:
            raise DatasetIntegrityError(
                f"Duplicate explicit judgment for {label.job_id}/{label.candidate_id}"
            )
        labels_by_job[label.job_id][label.candidate_id] = label

    split_payloads: dict[str, dict[str, Any]] = {}
    for split in ("train", "dev"):
        query_ids = sorted(
            job_id
            for job_id, assigned_split in bundle.query_splits.items()
            if assigned_split == split
        )
        rows: list[dict[str, Any]] = []
        groups: list[int] = []
        label_counts: Counter[int] = Counter()
        for job_id in query_ids:
            response = await feature_service.features_for_job_candidates(
                job_id,
                RetrievalRequest(
                    strategy=RetrievalStrategy.HYBRID,
                    top_k=48,
                    filters=None,
                ),
            )
            diagnostics = response.retrieval_diagnostics
            complete = (
                diagnostics.returned_count == 48
                and diagnostics.corpus_size == 48
                and diagnostics.eligible_count == 48
                and diagnostics.dense_pool_size == 48
                and diagnostics.sparse_pool_size == 48
                and len(response.results) == 48
            )
            if not complete:
                raise DatasetIntegrityError(
                    f"Job {job_id} did not retrieve the complete eligible 48 Candidates"
                )
            if response.feature_version != FEATURE_VERSION:
                raise DatasetIntegrityError("Feature version changed during LTR build")
            if response.feature_fingerprint != FEATURE_FINGERPRINT:
                raise DatasetIntegrityError("Feature fingerprint changed during LTR build")
            entity_ids = [item.entity_id for item in response.results]
            if len(set(entity_ids)) != 48:
                raise DatasetIntegrityError(
                    f"Job {job_id} retrieval contains duplicate Candidates"
                )
            judged = labels_by_job[job_id]
            start = len(rows)
            for item in response.results:
                label = judged.get(item.entity_id)
                if label is None:
                    continue
                if item.retrieval.dense_score is None or item.retrieval.sparse_score is None:
                    raise DatasetIntegrityError(
                        f"Judged pair {job_id}/{item.entity_id} lacks retrieval channels"
                    )
                vector = [
                    getattr(item.feature_vector, name) for name in MODEL_FEATURE_ORDER
                ]
                rows.append(
                    {
                        "split": split,
                        "job_id": job_id,
                        "candidate_id": item.entity_id,
                        "relevance_grade": int(label.relevance_grade),
                        "feature_vector": vector,
                    }
                )
                label_counts[int(label.relevance_grade)] += 1
            group_size = len(rows) - start
            if group_size != len(judged) or group_size != 12:
                raise DatasetIntegrityError(
                    f"Job {job_id} must join exactly 12 explicit judgments"
                )
            groups.append(group_size)
        split_payloads[split] = {
            "query_ids": query_ids,
            "group_sizes": groups,
            "row_count": len(rows),
            "label_distribution": {
                str(grade): label_counts[grade] for grade in range(4)
            },
            "rows": rows,
        }

    artifact = attach_dataset_fingerprint(
        {
            "schema_version": "1.0",
            "artifact_version": "ltr_dataset_v1",
            "dataset_version": dataset_version,
            "feature_version": FEATURE_VERSION,
            "feature_fingerprint": FEATURE_FINGERPRINT,
            "model_feature_order": list(MODEL_FEATURE_ORDER),
            "retrieval": {
                "strategy": RetrievalStrategy.HYBRID.value,
                "top_k": 48,
                "row_order_policy": "frozen_hybrid_relative_order",
            },
            "source_fingerprints": source_fingerprints,
            "splits": split_payloads,
            "unjudged_policy": "excluded_not_negative",
            "test_rows_included": False,
        }
    )
    train = matrix_for_split(artifact, "train")
    dev = matrix_for_split(artifact, "dev")
    if train.features.shape[0] != 168 or train.groups != [12] * 14:
        raise DatasetIntegrityError("Train LTR dataset must contain 168 rows in 14 groups")
    if dev.features.shape[0] != 60 or dev.groups != [12] * 5:
        raise DatasetIntegrityError("Dev LTR dataset must contain 60 rows in 5 groups")
    return artifact
