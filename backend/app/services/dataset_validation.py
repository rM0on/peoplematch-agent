from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.schemas.candidate import CandidateArchetype, CandidateProfile
from app.schemas.job import JobArchetype, JobProfile
from app.schemas.labels import (
    DatasetSplit,
    MismatchCode,
    PairwisePreference,
    RelevanceGrade,
    RelevanceLabel,
)
from app.services.dataset_semantics import (
    available_evidence_skills,
    evidence_backed_requirement_skills,
    qualifying_hard_negative_terms,
)


ModelT = TypeVar("ModelT", bound=BaseModel)


class DatasetValidationError(ValueError):
    """Raised when one or more cross-record dataset invariants fail."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__("Dataset validation failed:\n- " + "\n- ".join(self.errors))


@dataclass
class DatasetBundle:
    candidates: List[CandidateProfile]
    jobs: List[JobProfile]
    labels: List[RelevanceLabel]
    pairwise_preferences: List[PairwisePreference]
    query_splits: Dict[str, str]


@dataclass(frozen=True)
class DatasetValidationReport:
    candidate_count: int
    job_count: int
    label_count: int
    pairwise_count: int
    hard_negative_count: int
    split_job_counts: Dict[str, int]


def _read_jsonl(path: Path, model: Type[ModelT]) -> List[ModelT]:
    records: List[ModelT] = []
    errors: List[str] = []
    if not path.is_file():
        raise DatasetValidationError([f"missing dataset file: {path}"])

    with path.open("r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            line = raw_line.strip()
            if not line:
                errors.append(f"{path.name}:{line_number} is blank")
                continue
            try:
                payload = json.loads(line)
                records.append(model.model_validate(payload))
            except (json.JSONDecodeError, ValidationError) as exc:
                errors.append(f"{path.name}:{line_number}: {exc}")

    if errors:
        raise DatasetValidationError(errors)
    return records


def _load_query_splits(path: Path) -> Dict[str, str]:
    if not path.is_file():
        raise DatasetValidationError([f"missing split manifest: {path}"])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetValidationError([f"invalid split manifest JSON: {exc}"]) from exc

    if payload.get("schema_version") != "1.0":
        raise DatasetValidationError(["query split schema_version must be 1.0"])
    if payload.get("split_policy") != "job_query_grouped":
        raise DatasetValidationError(["query split policy must be job_query_grouped"])

    splits = payload.get("splits")
    if not isinstance(splits, dict):
        raise DatasetValidationError(["query split manifest requires a splits object"])

    job_to_split: Dict[str, str] = {}
    errors: List[str] = []
    for split in DatasetSplit:
        job_ids = splits.get(split.value)
        if not isinstance(job_ids, list):
            errors.append(f"query split {split.value} must be a list")
            continue
        for job_id in job_ids:
            if job_id in job_to_split:
                errors.append(f"job {job_id} appears in more than one query split")
            else:
                job_to_split[job_id] = split.value
    if errors:
        raise DatasetValidationError(errors)
    return job_to_split


def load_dataset(repository_root: Path) -> DatasetBundle:
    root = repository_root.resolve()
    return DatasetBundle(
        candidates=_read_jsonl(
            root / "data" / "samples" / "candidates.jsonl", CandidateProfile
        ),
        jobs=_read_jsonl(root / "data" / "samples" / "jobs.jsonl", JobProfile),
        labels=_read_jsonl(
            root / "data" / "samples" / "labels.jsonl", RelevanceLabel
        ),
        pairwise_preferences=_read_jsonl(
            root / "data" / "eval" / "pairwise_preferences.jsonl",
            PairwisePreference,
        ),
        query_splits=_load_query_splits(
            root / "data" / "eval" / "query_splits.json"
        ),
    )


def _duplicate_values(values: Iterable[str]) -> List[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def validate_bundle(bundle: DatasetBundle) -> DatasetValidationReport:
    errors: List[str] = []

    candidate_ids = [candidate.candidate_id for candidate in bundle.candidates]
    job_ids = [job.job_id for job in bundle.jobs]
    label_ids = [label.label_id for label in bundle.labels]
    preference_ids = [
        preference.preference_id for preference in bundle.pairwise_preferences
    ]

    for label, values in (
        ("candidate_id", candidate_ids),
        ("job_id", job_ids),
        ("label_id", label_ids),
        ("preference_id", preference_ids),
    ):
        duplicates = _duplicate_values(values)
        if duplicates:
            errors.append(f"duplicate {label} values: {duplicates}")

    if len(bundle.candidates) != 48:
        errors.append(f"expected 48 candidates, found {len(bundle.candidates)}")
    if len(bundle.jobs) != 24:
        errors.append(f"expected 24 jobs, found {len(bundle.jobs)}")
    if len(bundle.labels) < 288:
        errors.append(f"expected at least 288 labels, found {len(bundle.labels)}")
    if len(bundle.pairwise_preferences) < 48:
        errors.append(
            "expected at least 48 pairwise preferences, "
            f"found {len(bundle.pairwise_preferences)}"
        )

    candidate_by_id = {
        candidate.candidate_id: candidate for candidate in bundle.candidates
    }
    job_by_id = {job.job_id: job for job in bundle.jobs}

    expected_candidate_archetypes = {item.value for item in CandidateArchetype}
    actual_candidate_archetypes = {
        candidate.archetype.value for candidate in bundle.candidates
    }
    missing_candidate_archetypes = expected_candidate_archetypes - actual_candidate_archetypes
    if missing_candidate_archetypes:
        errors.append(
            f"candidate archetypes not covered: {sorted(missing_candidate_archetypes)}"
        )

    expected_job_archetypes = {item.value for item in JobArchetype}
    actual_job_archetypes = {job.archetype.value for job in bundle.jobs}
    missing_job_archetypes = expected_job_archetypes - actual_job_archetypes
    if missing_job_archetypes:
        errors.append(f"job archetypes not covered: {sorted(missing_job_archetypes)}")

    evidence_ids_by_candidate: Dict[str, set[str]] = {}
    for candidate in bundle.candidates:
        evidence_ids = [
            evidence.evidence_id for evidence in candidate.project_evidence
        ]
        duplicate_evidence = _duplicate_values(evidence_ids)
        if duplicate_evidence:
            errors.append(
                f"candidate {candidate.candidate_id} has duplicate evidence IDs: "
                f"{duplicate_evidence}"
            )
        evidence_ids_by_candidate[candidate.candidate_id] = set(evidence_ids)
        if candidate.data_origin != "synthetic_sandbox":
            errors.append(
                f"candidate {candidate.candidate_id} is not synthetic_sandbox"
            )

    requirement_ids_by_job: Dict[str, set[str]] = {}
    for job in bundle.jobs:
        requirement_ids_by_job[job.job_id] = {
            requirement.requirement_id
            for requirement in [*job.must_have, *job.nice_to_have]
        }
        if job.data_origin != "synthetic_sandbox":
            errors.append(f"job {job.job_id} is not synthetic_sandbox")

    if set(bundle.query_splits) != set(job_ids):
        missing = set(job_ids) - set(bundle.query_splits)
        unknown = set(bundle.query_splits) - set(job_ids)
        if missing:
            errors.append(f"jobs missing from query split manifest: {sorted(missing)}")
        if unknown:
            errors.append(f"unknown jobs in query split manifest: {sorted(unknown)}")

    split_counts = Counter(bundle.query_splits.values())
    expected_split_counts = {"train": 14, "dev": 5, "test": 5}
    if dict(split_counts) != expected_split_counts:
        errors.append(
            f"query split job counts must be {expected_split_counts}, found "
            f"{dict(split_counts)}"
        )

    labels_by_job: Dict[str, List[RelevanceLabel]] = defaultdict(list)
    for label in bundle.labels:
        if label.candidate_id not in candidate_by_id:
            errors.append(
                f"label {label.label_id} references unknown candidate_id "
                f"{label.candidate_id}"
            )
        if label.job_id not in job_by_id:
            errors.append(
                f"label {label.label_id} references unknown job_id {label.job_id}"
            )
            continue

        labels_by_job[label.job_id].append(label)
        expected_split = bundle.query_splits.get(label.job_id)
        if expected_split is not None and label.split.value != expected_split:
            errors.append(
                f"label {label.label_id} split {label.split.value} conflicts with "
                f"job split {expected_split}"
            )

        known_evidence = evidence_ids_by_candidate.get(label.candidate_id, set())
        unknown_evidence = set(label.supporting_evidence_ids) - known_evidence
        if unknown_evidence:
            errors.append(
                f"label {label.label_id} references evidence not owned by candidate: "
                f"{sorted(unknown_evidence)}"
            )

        known_requirements = requirement_ids_by_job.get(label.job_id, set())
        unknown_requirements = set(label.affected_requirement_ids) - known_requirements
        if unknown_requirements:
            errors.append(
                f"label {label.label_id} references unknown job requirements: "
                f"{sorted(unknown_requirements)}"
            )

        candidate = candidate_by_id.get(label.candidate_id)
        job = job_by_id[label.job_id]
        if label.hard_negative:
            if label.relevance_grade > RelevanceGrade.WEAK_OR_MISLEADING:
                errors.append(
                    f"hard negative {label.label_id} must use grade 0 or 1"
                )
            overlap_terms = (
                qualifying_hard_negative_terms(candidate, job)
                if candidate is not None
                else []
            )
            if not overlap_terms:
                errors.append(
                    f"hard negative {label.label_id} has no meaningful candidate/job overlap"
                )
            rationale = label.rationale.casefold()
            if "overlapping terms:" not in rationale or "actual mismatch:" not in rationale:
                errors.append(
                    f"hard negative {label.label_id} rationale must name overlapping terms "
                    "and actual mismatch"
                )
        if candidate is not None and label.relevance_grade == RelevanceGrade.STRONG_MATCH:
            required_skills = evidence_backed_requirement_skills(job)
            supported_skills = available_evidence_skills(
                candidate, label.supporting_evidence_ids
            )
            missing_coverage = required_skills - supported_skills
            if missing_coverage:
                errors.append(
                    f"grade 3 label {label.label_id} lacks available evidence coverage "
                    f"for {sorted(missing_coverage)}"
                )
            location_compatible = (
                not set(candidate.preferred_locations.cities).isdisjoint(
                    job.location.cities
                )
                or candidate.preferred_locations.relocation_open
                or job.location.remote_policy.value == "remote"
            )
            if not location_compatible:
                errors.append(
                    f"grade 3 label {label.label_id} has a location conflict"
                )
            if candidate.seniority not in job.seniority_requirement:
                errors.append(
                    f"grade 3 label {label.label_id} has a seniority conflict"
                )
            if job.product_stage.value not in candidate.work_style.team_stage_preference:
                errors.append(
                    f"grade 3 label {label.label_id} has a work-style conflict"
                )
        if candidate is not None and label.relevance_grade == RelevanceGrade.PLAUSIBLE_MATCH:
            supporting = [
                evidence
                for evidence in candidate.project_evidence
                if evidence.evidence_id in label.supporting_evidence_ids
            ]
            if not supporting or any(
                evidence.verification_status.value != "available"
                for evidence in supporting
            ):
                errors.append(
                    f"grade 2 label {label.label_id} must link available adjacent evidence"
                )
            if not label.mismatch_reasons:
                errors.append(
                    f"grade 2 label {label.label_id} must name at least one gap"
                )

        constraint_categories = {
            MismatchCode.LOCATION_MISMATCH: "location",
            MismatchCode.SENIORITY_MISMATCH: "seniority",
            MismatchCode.WORK_STYLE_MISMATCH: "work_style",
        }
        requirements_by_id = {
            requirement.requirement_id: requirement.category.value
            for requirement in [*job.must_have, *job.nice_to_have]
        }
        affected_categories = {
            requirements_by_id[requirement_id]
            for requirement_id in label.affected_requirement_ids
            if requirement_id in requirements_by_id
        }
        for mismatch_reason in label.mismatch_reasons:
            expected_category = constraint_categories.get(mismatch_reason)
            if (
                expected_category is not None
                and expected_category not in affected_categories
            ):
                errors.append(
                    f"{mismatch_reason.value} on label {label.label_id} requires "
                    f"an affected {expected_category} requirement"
                )

    for job_id in job_ids:
        job_labels = labels_by_job.get(job_id, [])
        grade_counts = Counter(label.relevance_grade for label in job_labels)
        if len(job_labels) < 12:
            errors.append(f"job {job_id} has fewer than 12 relevance labels")
        if len(grade_counts) < 2:
            errors.append(f"job {job_id} lacks relevance grade diversity")
        if grade_counts[RelevanceGrade.STRONG_MATCH] < 2:
            errors.append(f"job {job_id} has fewer than 2 grade 3 labels")
        if grade_counts[RelevanceGrade.PLAUSIBLE_MATCH] < 2:
            errors.append(f"job {job_id} has fewer than 2 grade 2 labels")
        if (
            grade_counts[RelevanceGrade.NON_MATCH]
            + grade_counts[RelevanceGrade.WEAK_OR_MISLEADING]
            < 2
        ):
            errors.append(f"job {job_id} has fewer than 2 grade 0/1 labels")
        if not any(label.hard_negative for label in job_labels):
            errors.append(f"job {job_id} has no hard negative")

    pairwise_by_job: Counter[str] = Counter()
    seen_pairs: set[tuple[str, str, str]] = set()
    grade_by_job_candidate = {
        (label.job_id, label.candidate_id): label.relevance_grade
        for label in bundle.labels
    }
    for preference in bundle.pairwise_preferences:
        if preference.job_id not in job_by_id:
            errors.append(
                f"preference {preference.preference_id} references unknown job_id"
            )
            continue
        for role, candidate_id in (
            ("winner", preference.winner_candidate_id),
            ("loser", preference.loser_candidate_id),
        ):
            if candidate_id not in candidate_by_id:
                errors.append(
                    f"preference {preference.preference_id} {role} references "
                    f"unknown candidate_id {candidate_id}"
                )
            if (preference.job_id, candidate_id) not in grade_by_job_candidate:
                errors.append(
                    f"preference {preference.preference_id} {role} candidate has no "
                    "relevance label for the job"
                )
        expected_split = bundle.query_splits.get(preference.job_id)
        if expected_split and preference.split.value != expected_split:
            errors.append(
                f"preference {preference.preference_id} split conflicts with job split"
            )
        pair_key = (
            preference.job_id,
            preference.winner_candidate_id,
            preference.loser_candidate_id,
        )
        if pair_key in seen_pairs:
            errors.append(f"duplicate pairwise comparison: {pair_key}")
        seen_pairs.add(pair_key)
        pairwise_by_job[preference.job_id] += 1

        winner_grade = grade_by_job_candidate.get(
            (preference.job_id, preference.winner_candidate_id)
        )
        loser_grade = grade_by_job_candidate.get(
            (preference.job_id, preference.loser_candidate_id)
        )
        if winner_grade is not None and loser_grade is not None:
            if winner_grade <= loser_grade:
                errors.append(
                    f"preference {preference.preference_id} winner grade must exceed "
                    "loser grade"
                )

    for job_id in job_ids:
        if pairwise_by_job[job_id] < 2:
            errors.append(f"job {job_id} has fewer than 2 pairwise preferences")

    covered_mismatches = {
        reason for label in bundle.labels for reason in label.mismatch_reasons
    }
    required_mismatches = {
        MismatchCode.DIRECTION_MISMATCH,
        MismatchCode.EVIDENCE_INSUFFICIENT,
        MismatchCode.KEYWORD_FALSE_POSITIVE,
        MismatchCode.MUST_HAVE_MISSING,
        MismatchCode.LOCATION_MISMATCH,
        MismatchCode.SENIORITY_MISMATCH,
        MismatchCode.WORK_STYLE_MISMATCH,
        MismatchCode.OVERCLAIM_RISK,
    }
    missing_mismatches = required_mismatches - covered_mismatches
    if missing_mismatches:
        errors.append(
            "required mismatch codes not covered: "
            f"{sorted(item.value for item in missing_mismatches)}"
        )

    if errors:
        raise DatasetValidationError(errors)

    return DatasetValidationReport(
        candidate_count=len(bundle.candidates),
        job_count=len(bundle.jobs),
        label_count=len(bundle.labels),
        pairwise_count=len(bundle.pairwise_preferences),
        hard_negative_count=sum(label.hard_negative for label in bundle.labels),
        split_job_counts=dict(split_counts),
    )


def validate_dataset(repository_root: Path) -> DatasetValidationReport:
    return validate_bundle(load_dataset(repository_root))
