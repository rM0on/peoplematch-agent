from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.dataset_validation import load_dataset, validate_bundle
from app.services.evaluation.errors import EvaluationIntegrityError


@dataclass(frozen=True)
class JudgmentBundle:
    candidate_ids: tuple[str, ...]
    job_ids: tuple[str, ...]
    labels: tuple[Any, ...]
    pairs: tuple[Any, ...]
    candidates: tuple[Any, ...]
    grades_by_job: dict[str, dict[str, int]]
    pairs_by_job: dict[str, tuple[tuple[str, str], ...]]
    splits: dict[str, tuple[str, ...]]
    dataset_fingerprint: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_judgments(repository_root: Path, *, manifest_path: Path | None = None) -> JudgmentBundle:
    path = manifest_path or repository_root / "data/eval/dataset_freeze_manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationIntegrityError("dataset freeze manifest is unavailable") from error
    expected_identity = {
        "dataset_version": "1.0.0", "schema_version": "1.0", "candidate_count": 48,
        "job_count": 24, "label_count": 288, "pairwise_count": 48,
    }
    mismatches = [key for key, value in expected_identity.items() if manifest.get(key) != value]
    if mismatches:
        raise EvaluationIntegrityError("dataset identity mismatch: " + ", ".join(mismatches))
    canonical_files = manifest.get("canonical_files")
    if not isinstance(canonical_files, dict) or not canonical_files:
        raise EvaluationIntegrityError("canonical dataset file manifest is missing")
    for relative, expected_sha in canonical_files.items():
        candidate = repository_root / relative
        if not candidate.is_file() or _sha256(candidate) != expected_sha:
            raise EvaluationIntegrityError(f"dataset SHA-256 mismatch: {relative}")
    bundle = load_dataset(repository_root)
    try:
        validate_bundle(bundle)
    except Exception as error:
        raise EvaluationIntegrityError("dataset semantic validation failed") from error
    if (len(bundle.candidates), len(bundle.jobs), len(bundle.labels), len(bundle.pairwise_preferences)) != (48, 24, 288, 48):
        raise EvaluationIntegrityError("dataset row counts do not match the frozen contract")
    candidate_ids = tuple(sorted(item.candidate_id for item in bundle.candidates))
    job_ids = tuple(sorted(item.job_id for item in bundle.jobs))
    if len(set(candidate_ids)) != 48 or len(set(job_ids)) != 24:
        raise EvaluationIntegrityError("duplicate Candidate or Job ID")
    grades: dict[str, dict[str, int]] = defaultdict(dict)
    labels_per_job: Counter[str] = Counter()
    for label in bundle.labels:
        if label.candidate_id in grades[label.job_id]:
            raise EvaluationIntegrityError("duplicate Candidate/Job judgment")
        grade = int(label.relevance_grade)
        if grade not in (0, 1, 2, 3):
            raise EvaluationIntegrityError("invalid relevance grade")
        grades[label.job_id][label.candidate_id] = grade
        labels_per_job[label.job_id] += 1
    pairs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    seen_pairs: set[tuple[str, str, str]] = set()
    for item in bundle.pairwise_preferences:
        key = (item.job_id, item.winner_candidate_id, item.loser_candidate_id)
        if item.winner_candidate_id == item.loser_candidate_id or key in seen_pairs:
            raise EvaluationIntegrityError("invalid or duplicate pairwise judgment")
        seen_pairs.add(key)
        if item.winner_candidate_id not in grades[item.job_id] or item.loser_candidate_id not in grades[item.job_id]:
            raise EvaluationIntegrityError("pairwise candidate is not judged for its query")
        pairs[item.job_id].append((item.winner_candidate_id, item.loser_candidate_id))
    if set(labels_per_job.values()) != {12} or {len(value) for value in pairs.values()} != {2}:
        raise EvaluationIntegrityError("expected exactly 12 judgments and 2 pairs per Job")
    split_map: dict[str, list[str]] = defaultdict(list)
    for job_id, split in bundle.query_splits.items():
        split_map[split].append(job_id)
    dataset_fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    return JudgmentBundle(
        candidate_ids=candidate_ids, job_ids=job_ids, labels=tuple(bundle.labels),
        pairs=tuple(bundle.pairwise_preferences), candidates=tuple(bundle.candidates), grades_by_job=dict(grades),
        pairs_by_job={key: tuple(value) for key, value in pairs.items()},
        splits={key: tuple(sorted(value)) for key, value in split_map.items()},
        dataset_fingerprint=dataset_fingerprint,
    )
