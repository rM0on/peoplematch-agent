from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_checked_in_dataset_passes_full_validation() -> None:
    from app.services.dataset_validation import validate_dataset

    report = validate_dataset(REPOSITORY_ROOT)

    assert report.candidate_count == 48
    assert report.job_count == 24
    assert report.label_count >= 288
    assert report.pairwise_count >= 48


def test_validator_rejects_unknown_label_candidate() -> None:
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    bundle.labels[0] = bundle.labels[0].model_copy(
        update={"candidate_id": "cand_missing"}
    )

    with pytest.raises(DatasetValidationError, match="unknown candidate_id"):
        validate_bundle(bundle)


def test_validator_rejects_unknown_label_evidence_reference() -> None:
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    label = bundle.labels[0]
    bundle.labels[0] = label.model_copy(
        update={"supporting_evidence_ids": ["ev_not_owned"]}
    )

    with pytest.raises(DatasetValidationError, match="evidence not owned"):
        validate_bundle(bundle)


def test_validator_rejects_unknown_label_requirement_reference() -> None:
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    label = bundle.labels[0]
    bundle.labels[0] = label.model_copy(
        update={"affected_requirement_ids": ["req_not_owned"]}
    )

    with pytest.raises(DatasetValidationError, match="unknown job requirements"):
        validate_bundle(bundle)


def test_validator_rejects_query_split_leakage() -> None:
    from app.schemas.labels import DatasetSplit
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    first_job_id = bundle.labels[0].job_id
    conflicting_index = next(
        index
        for index, label in enumerate(bundle.labels)
        if label.job_id == first_job_id
    )
    bundle.labels[conflicting_index] = bundle.labels[conflicting_index].model_copy(
        update={"split": DatasetSplit.TEST}
    )

    with pytest.raises(DatasetValidationError, match="split"):
        validate_bundle(bundle)


def test_validator_requires_hard_negative_for_every_job() -> None:
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    first_job_id = bundle.jobs[0].job_id
    bundle.labels = [
        label.model_copy(update={"hard_negative": False})
        if label.job_id == first_job_id
        else label
        for label in bundle.labels
    ]

    with pytest.raises(DatasetValidationError, match="hard negative"):
        validate_bundle(bundle)


def test_dataset_uses_query_level_split_counts() -> None:
    from app.services.dataset_validation import load_dataset

    bundle = load_dataset(REPOSITORY_ROOT)
    split_counts = Counter(bundle.query_splits.values())

    assert split_counts == {"train": 14, "dev": 5, "test": 5}
    for job_id, split in bundle.query_splits.items():
        assert {label.split.value for label in bundle.labels if label.job_id == job_id} == {
            split
        }


def test_schema_export_is_deterministic() -> None:
    command = [sys.executable, "scripts/export_json_schemas.py"]
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)
    schema_dir = REPOSITORY_ROOT / "data" / "schemas"
    first_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(schema_dir.glob("*.schema.json"))
    }

    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)
    second_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(schema_dir.glob("*.schema.json"))
    }

    assert len(first_hashes) == 4
    assert second_hashes == first_hashes


def test_validation_cli_reports_success() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_dataset.py"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Dataset validation PASS" in result.stdout
    assert "48 candidates" in result.stdout


def test_dataset_statistics_are_descriptive_only() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/dataset_stats.py"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    stats_path = REPOSITORY_ROOT / "data" / "eval" / "dataset_stats.json"
    payload = json.loads(stats_path.read_text(encoding="utf-8"))

    assert "Wrote descriptive dataset statistics" in result.stdout
    assert payload["candidate_count"] == 48
    assert payload["job_count"] == 24
    assert payload["label_count"] >= 288
    assert not {"recall", "ndcg", "mrr"} & {key.lower() for key in payload}


def test_seed_manifest_is_deterministic_and_defers_database_insertion() -> None:
    command = [sys.executable, "scripts/prepare_seed_bundle.py"]
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)
    manifest_path = REPOSITORY_ROOT / "data" / "seed" / "manifest.json"
    first_content = manifest_path.read_bytes()

    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)
    second_content = manifest_path.read_bytes()
    payload = json.loads(second_content.decode("utf-8"))

    assert second_content == first_content
    assert payload["database_insertion"] == "deferred_to_phase_2"
    assert payload["schema_version"] == "1.0"
    assert len(payload["files"]) == 9


def test_dataset_freeze_manifest_is_deterministic_and_pins_test_queries() -> None:
    command = [sys.executable, "scripts/freeze_dataset.py"]
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)
    manifest_path = (
        REPOSITORY_ROOT / "data" / "eval" / "dataset_freeze_manifest.json"
    )
    first_content = manifest_path.read_bytes()

    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)
    second_content = manifest_path.read_bytes()
    payload = json.loads(second_content.decode("utf-8"))

    assert second_content == first_content
    assert payload["dataset_version"] == "1.0.0"
    assert payload["schema_version"] == "1.0"
    assert payload["candidate_count"] == 48
    assert payload["job_count"] == 24
    assert payload["label_count"] == 288
    assert payload["pairwise_count"] == 48
    assert payload["test_job_ids"] == [
        "job_020",
        "job_021",
        "job_022",
        "job_023",
        "job_024",
    ]
    assert set(payload["canonical_files"]) == {
        "data/samples/candidates.jsonl",
        "data/samples/jobs.jsonl",
        "data/samples/labels.jsonl",
        "data/eval/pairwise_preferences.jsonl",
        "data/eval/query_splits.json",
    }
    assert all(
        re.fullmatch(r"[0-9a-f]{64}", digest)
        for digest in payload["canonical_files"].values()
    )


def test_dataset_freeze_check_verifies_without_rewriting_manifest() -> None:
    manifest_path = (
        REPOSITORY_ROOT / "data" / "eval" / "dataset_freeze_manifest.json"
    )
    before = manifest_path.read_bytes()

    result = subprocess.run(
        [sys.executable, "scripts/freeze_dataset.py", "--check"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert manifest_path.read_bytes() == before
    assert "Dataset freeze verification PASS" in result.stdout


def test_strong_labels_respect_candidate_constraints() -> None:
    from app.services.dataset_validation import load_dataset

    bundle = load_dataset(REPOSITORY_ROOT)
    candidates = {candidate.candidate_id: candidate for candidate in bundle.candidates}
    jobs = {job.job_id: job for job in bundle.jobs}

    for label in bundle.labels:
        if int(label.relevance_grade) != 3:
            continue
        candidate = candidates[label.candidate_id]
        job = jobs[label.job_id]
        location_compatible = (
            not set(candidate.preferred_locations.cities).isdisjoint(job.location.cities)
            or candidate.preferred_locations.relocation_open
            or job.location.remote_policy.value == "remote"
        )
        seniority_compatible = candidate.seniority in job.seniority_requirement
        work_style_compatible = (
            job.product_stage.value in candidate.work_style.team_stage_preference
        )

        assert location_compatible, label.label_id
        assert seniority_compatible, label.label_id
        assert work_style_compatible, label.label_id


def test_constraint_mismatches_reference_matching_requirement_categories() -> None:
    from app.services.dataset_validation import load_dataset

    bundle = load_dataset(REPOSITORY_ROOT)
    jobs = {job.job_id: job for job in bundle.jobs}
    expected_categories = {
        "LOCATION_MISMATCH": "location",
        "SENIORITY_MISMATCH": "seniority",
        "WORK_STYLE_MISMATCH": "work_style",
    }
    for label in bundle.labels:
        job = jobs[label.job_id]
        requirements = {
            requirement.requirement_id: requirement.category.value
            for requirement in [*job.must_have, *job.nice_to_have]
        }
        affected_categories = {
            requirements[requirement_id]
            for requirement_id in label.affected_requirement_ids
        }
        for mismatch in label.mismatch_reasons:
            expected = expected_categories.get(mismatch.value)
            if expected is not None:
                assert expected in affected_categories, label.label_id


def test_raw_profiles_avoid_known_template_grammar_errors() -> None:
    from app.services.dataset_validation import load_dataset

    bundle = load_dataset(REPOSITORY_ROOT)
    raw_texts = [candidate.raw_text for candidate in bundle.candidates] + [
        job.raw_jd for job in bundle.jobs
    ]

    assert all(" a AI " not in text for text in raw_texts)
    assert all(" a onsite " not in text for text in raw_texts)


def test_validator_rejects_constraint_conflict_on_strong_label() -> None:
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    strong_label = next(
        label for label in bundle.labels if int(label.relevance_grade) == 3
    )
    candidate_index = next(
        index
        for index, candidate in enumerate(bundle.candidates)
        if candidate.candidate_id == strong_label.candidate_id
    )
    candidate = bundle.candidates[candidate_index]
    incompatible_location = candidate.preferred_locations.model_copy(
        update={"cities": ["Remote Outpost"], "relocation_open": False}
    )
    bundle.candidates[candidate_index] = candidate.model_copy(
        update={"preferred_locations": incompatible_location}
    )

    with pytest.raises(DatasetValidationError, match="grade 3.*location"):
        validate_bundle(bundle)


def test_validator_rejects_constraint_code_with_wrong_requirement_category() -> None:
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    label_index = next(
        index
        for index, label in enumerate(bundle.labels)
        if any(reason.value == "LOCATION_MISMATCH" for reason in label.mismatch_reasons)
    )
    label = bundle.labels[label_index]
    job = next(job for job in bundle.jobs if job.job_id == label.job_id)
    skill_requirement_id = next(
        requirement.requirement_id
        for requirement in job.must_have
        if requirement.category.value == "skill"
    )
    bundle.labels[label_index] = label.model_copy(
        update={"affected_requirement_ids": [skill_requirement_id]}
    )

    with pytest.raises(DatasetValidationError, match="LOCATION_MISMATCH.*location"):
        validate_bundle(bundle)


def test_overclaim_archetype_has_broad_claims_but_limited_available_evidence() -> None:
    from app.services.dataset_validation import load_dataset

    bundle = load_dataset(REPOSITORY_ROOT)
    overclaim_profiles = [
        candidate
        for candidate in bundle.candidates
        if candidate.archetype.value == "overclaim_candidate"
    ]

    assert len(overclaim_profiles) == 4
    for candidate in overclaim_profiles:
        available_count = sum(
            evidence.verification_status.value == "available"
            for evidence in candidate.project_evidence
        )
        assert available_count <= 1, candidate.candidate_id
        assert candidate.overclaim_risk.level.value == "high"


def test_reviewed_hard_negative_ids_are_true_hard_negatives() -> None:
    from app.services.dataset_validation import load_dataset

    review = (REPOSITORY_ROOT / "docs" / "dataset-quality-review.md").read_text(
        encoding="utf-8"
    )
    sample_line = next(
        line for line in review.splitlines() if line.startswith("- Hard negatives (")
    )
    reviewed_ids = re.findall(r"lbl_\d{4}", sample_line)
    labels = {
        label.label_id: label for label in load_dataset(REPOSITORY_ROOT).labels
    }

    assert len(reviewed_ids) >= 8
    assert all(labels[label_id].hard_negative for label_id in reviewed_ids)
    assert labels["lbl_0019"].candidate_id == "cand_046"


def test_core_job_uses_retrieval_confusing_not_generic_ai_hard_negatives() -> None:
    from app.services.dataset_validation import load_dataset

    labels = {
        label.candidate_id: label
        for label in load_dataset(REPOSITORY_ROOT).labels
        if label.job_id == "job_001"
    }

    assert not labels["cand_011"].hard_negative
    assert not labels["cand_012"].hard_negative
    assert labels["cand_045"].hard_negative
    assert labels["cand_046"].hard_negative


def test_grade_three_labels_cover_evidence_backed_requirements() -> None:
    from app.services.dataset_validation import load_dataset

    bundle = load_dataset(REPOSITORY_ROOT)
    candidates = {candidate.candidate_id: candidate for candidate in bundle.candidates}
    jobs = {job.job_id: job for job in bundle.jobs}

    for label in bundle.labels:
        if int(label.relevance_grade) != 3:
            continue
        candidate = candidates[label.candidate_id]
        job = jobs[label.job_id]
        evidence_by_id = {
            evidence.evidence_id: evidence for evidence in candidate.project_evidence
        }
        supporting = [
            evidence_by_id[evidence_id]
            for evidence_id in label.supporting_evidence_ids
        ]
        available_skills = {
            skill.casefold()
            for evidence in supporting
            if evidence.verification_status.value == "available"
            for skill in evidence.supports_skills
        }
        required_skills = {
            requirement.text.removeprefix("Practical use of ").casefold()
            if requirement.category.value == "skill"
            else requirement.text.removeprefix(
                "Evaluation evidence involving "
            ).casefold()
            for requirement in job.must_have
            if requirement.category.value in {"skill", "project_evidence"}
        }

        assert required_skills <= available_skills, label.label_id


def test_grade_two_labels_name_gaps_and_link_available_adjacent_evidence() -> None:
    from app.services.dataset_validation import load_dataset

    bundle = load_dataset(REPOSITORY_ROOT)
    candidates = {candidate.candidate_id: candidate for candidate in bundle.candidates}

    for label in bundle.labels:
        if int(label.relevance_grade) != 2:
            continue
        candidate = candidates[label.candidate_id]
        evidence_by_id = {
            evidence.evidence_id: evidence for evidence in candidate.project_evidence
        }
        supporting = [
            evidence_by_id[evidence_id]
            for evidence_id in label.supporting_evidence_ids
        ]

        assert supporting, label.label_id
        assert all(
            evidence.verification_status.value == "available"
            for evidence in supporting
        ), label.label_id
        assert label.mismatch_reasons, label.label_id
        assert "remains plausible" in label.rationale, label.label_id
        assert "not a strong match" in label.rationale, label.label_id


def test_validator_rejects_grade_three_without_required_available_evidence() -> None:
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    label_index = next(
        index
        for index, label in enumerate(bundle.labels)
        if int(label.relevance_grade) == 3
    )
    label = bundle.labels[label_index]
    bundle.labels[label_index] = label.model_copy(
        update={"supporting_evidence_ids": []}
    )

    with pytest.raises(DatasetValidationError, match="grade 3.*evidence coverage"):
        validate_bundle(bundle)


def test_validator_rejects_hard_negative_above_grade_one() -> None:
    from app.schemas.labels import RelevanceGrade
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    label_index = next(
        index for index, label in enumerate(bundle.labels) if label.hard_negative
    )
    label = bundle.labels[label_index]
    bundle.labels[label_index] = label.model_copy(
        update={"relevance_grade": RelevanceGrade.PLAUSIBLE_MATCH}
    )

    with pytest.raises(DatasetValidationError, match="hard negative.*grade 0 or 1"):
        validate_bundle(bundle)


def test_hard_negative_rationales_name_overlap_and_actual_mismatch() -> None:
    from app.services.dataset_validation import load_dataset

    hard_negatives = [
        label
        for label in load_dataset(REPOSITORY_ROOT).labels
        if label.hard_negative
    ]

    assert hard_negatives
    for label in hard_negatives:
        rationale = label.rationale.casefold()
        assert "overlapping terms:" in rationale, label.label_id
        assert "actual mismatch:" in rationale, label.label_id


def test_validator_rejects_pairwise_winner_without_higher_grade() -> None:
    from app.services.dataset_validation import (
        DatasetValidationError,
        load_dataset,
        validate_bundle,
    )

    bundle = load_dataset(REPOSITORY_ROOT)
    preference = bundle.pairwise_preferences[0]
    winner_label_index = next(
        index
        for index, label in enumerate(bundle.labels)
        if label.job_id == preference.job_id
        and label.candidate_id == preference.winner_candidate_id
    )
    loser_label = next(
        label
        for label in bundle.labels
        if label.job_id == preference.job_id
        and label.candidate_id == preference.loser_candidate_id
    )
    winner_label = bundle.labels[winner_label_index]
    bundle.labels[winner_label_index] = winner_label.model_copy(
        update={"relevance_grade": loser_label.relevance_grade}
    )

    with pytest.raises(DatasetValidationError, match="winner grade must exceed"):
        validate_bundle(bundle)


def test_candidate_archetypes_are_not_four_copy_templates() -> None:
    from collections import defaultdict

    from app.services.dataset_validation import load_dataset

    profiles_by_archetype = defaultdict(list)
    for candidate in load_dataset(REPOSITORY_ROOT).candidates:
        profiles_by_archetype[candidate.archetype.value].append(candidate)

    for archetype, profiles in profiles_by_archetype.items():
        assert len({profile.raw_text for profile in profiles}) == 4, archetype
        assert (
            len(
                {
                    tuple(project.name for project in profile.projects)
                    for profile in profiles
                }
            )
            >= 2
        ), archetype
        assert (
            len(
                {
                    tuple(project.summary for project in profile.projects)
                    for profile in profiles
                }
            )
            >= 2
        ), archetype
        assert (
            len(
                {
                    tuple(skill.name for skill in profile.skills)
                    for profile in profiles
                }
            )
            >= 2
        ), archetype
        assert (
            len(
                {
                    tuple(
                        tuple(project.technologies) for project in profile.projects
                    )
                    for profile in profiles
                }
            )
            >= 2
        ), archetype
        assert (
            len(
                {
                    tuple(evidence.evidence_type.value for evidence in profile.project_evidence)
                    for profile in profiles
                }
            )
            >= 2
        ), archetype
        assert all(
            not re.search(r"\s[1-4]$", project.name)
            for profile in profiles
            for project in profile.projects
        ), archetype

    quality_orders = {
        tuple(profile.overclaim_risk.level.value for profile in profiles)
        for profiles in profiles_by_archetype.values()
    }
    assert len(quality_orders) >= 4


def test_test_split_contains_required_challenge_cases() -> None:
    from app.services.dataset_validation import load_dataset

    bundle = load_dataset(REPOSITORY_ROOT)
    test_labels = [label for label in bundle.labels if label.split.value == "test"]
    hard_negatives = [label for label in test_labels if label.hard_negative]
    reason_values = {
        reason.value for label in test_labels for reason in label.mismatch_reasons
    }
    hard_reason_values = {
        reason.value for label in hard_negatives for reason in label.mismatch_reasons
    }

    assert {
        "DIRECTION_MISMATCH",
        "EVIDENCE_INSUFFICIENT",
        "OVERCLAIM_RISK",
    } <= hard_reason_values
    assert {"LOCATION_MISMATCH", "SENIORITY_MISMATCH"} <= reason_values
    assert any(
        int(label.relevance_grade) == 2
        and len(label.supporting_evidence_ids) >= 2
        and any(
            reason.value == "DIRECTION_MISMATCH"
            for reason in label.mismatch_reasons
        )
        for label in test_labels
    )

    labels_by_pair = {
        (label.job_id, label.candidate_id): label for label in test_labels
    }
    test_preferences = [
        preference
        for preference in bundle.pairwise_preferences
        if preference.split.value == "test"
    ]
    assert any(
        labels_by_pair[(preference.job_id, preference.loser_candidate_id)].hard_negative
        and labels_by_pair[
            (preference.job_id, preference.winner_candidate_id)
        ].supporting_evidence_ids
        for preference in test_preferences
    )
