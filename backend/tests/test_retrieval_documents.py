from __future__ import annotations

import json
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _line(path: str, index: int = 0) -> dict[str, object]:
    return json.loads(
        (REPOSITORY_ROOT / path).read_text(encoding="utf-8").splitlines()[index]
    )


def test_candidate_document_contains_recall_fields_and_excludes_prohibited_fields() -> None:
    from app.schemas.candidate import CandidateProfile
    from app.schemas.shared import Seniority
    from app.services.retrieval.documents import (
        RETRIEVAL_DOCUMENT_VERSION,
        build_candidate_document,
    )

    payload = _line("data/samples/candidates.jsonl")
    record = CandidateProfile.model_validate(payload)
    excluded = record.model_copy(
        update={
            "name": "EXCLUDED_CANDIDATE_NAME",
            "raw_text": "EXCLUDED_RAW_TEXT " * 4,
            "github_url": "sandbox://EXCLUDED_GITHUB_URL",
            "missing_fields": ["EXCLUDED_MISSING_FIELD"],
            "projects": [
                record.projects[0].model_copy(
                    update={"name": "EXCLUDED_SYNTHETIC_PROJECT_FAMILY"}
                ),
                *record.projects[1:],
            ],
            "project_evidence": [
                record.project_evidence[0].model_copy(
                    update={
                        "statement": (
                            "Used inside EXCLUDED_SYNTHETIC_PROJECT_FAMILY "
                            "to provide auditable evidence."
                        )
                    }
                ),
                *record.project_evidence[1:],
            ],
            "preferred_locations": record.preferred_locations.model_copy(
                update={"cities": ["EXCLUDED_CANDIDATE_CITY"]}
            ),
            "seniority": Seniority.STAFF,
            "work_style": record.work_style.model_copy(
                update={"collaboration_style": "EXCLUDED_COLLABORATION_STYLE"}
            ),
            "overclaim_risk": record.overclaim_risk.model_copy(
                update={"reasons": ["EXCLUDED_OVERCLAIM_REASON"]}
            ),
        }
    )
    document = build_candidate_document(excluded)

    assert document.entity_id == record.candidate_id
    assert document.document_version == RETRIEVAL_DOCUMENT_VERSION == "retrieval_doc_v4"
    included = [
        record.target_roles[0],
        record.skills[0].name,
        record.skills[0].category.value,
        "A local multi-step assistant that calls typed tools",
        record.projects[0].role,
        record.projects[0].technologies[0],
        record.projects[0].skills_demonstrated[0],
        record.project_evidence[0].supports_skills[0],
        record.project_evidence[0].evidence_type.value,
        "Used inside the project to provide auditable evidence.",
        record.ai_tools[0],
    ]
    assert all(value in document.text for value in included)

    prohibited = [
        excluded.candidate_id,
        excluded.name,
        excluded.projects[0].name,
        excluded.raw_text,
        excluded.github_url,
        record.projects[0].project_id,
        record.project_evidence[0].evidence_id,
        record.project_evidence[0].artifact_ref,
        record.data_origin,
        record.archetype.value,
        excluded.missing_fields[0],
        excluded.preferred_locations.cities[0],
        excluded.seniority.value,
        excluded.work_style.collaboration_style,
        excluded.overclaim_risk.reasons[0],
    ]
    assert all(value and value not in document.text for value in prohibited)
    assert document.cities == excluded.preferred_locations.cities
    assert document.seniorities == [excluded.seniority]
    assert len(document.document_fingerprint) == 64


def test_job_document_contains_recall_fields_and_excludes_prohibited_fields() -> None:
    from app.schemas.job import JobProfile
    from app.schemas.shared import ProductStage, Seniority
    from app.services.retrieval.documents import build_job_document

    payload = _line("data/samples/jobs.jsonl")
    record = JobProfile.model_validate(payload)
    excluded = record.model_copy(
        update={
            "company_name": "EXCLUDED_COMPANY_NAME",
            "raw_jd": "EXCLUDED_RAW_JOB_DESCRIPTION " * 4,
            "location": record.location.model_copy(
                update={"cities": ["EXCLUDED_JOB_CITY"]}
            ),
            "seniority_requirement": [Seniority.STAFF],
            "product_stage": ProductStage.MATURE,
            "team_tags": ["EXCLUDED_TEAM_TAG"],
        }
    )
    document = build_job_document(excluded)

    included = [
        record.role_title,
        record.role_direction[0],
        record.must_have[0].text,
        record.must_have[0].category.value,
        record.must_have[0].evidence_expectation,
        record.nice_to_have[0].text,
        record.nice_to_have[0].category.value,
        record.evaluation_focus[0],
    ]
    assert all(value in document.text for value in included)

    prohibited = [
        excluded.job_id,
        excluded.company_name,
        excluded.raw_jd,
        record.archetype.value,
        record.must_have[0].requirement_id,
        record.data_origin,
        excluded.location.cities[0],
        excluded.seniority_requirement[0].value,
        excluded.product_stage.value,
        excluded.team_tags[0],
    ]
    assert all(value and value not in document.text for value in prohibited)
    assert document.cities == excluded.location.cities
    assert document.seniorities == excluded.seniority_requirement


def test_document_fingerprint_is_stable_and_changes_with_semantic_text() -> None:
    from app.schemas.candidate import CandidateProfile
    from app.services.retrieval.documents import build_candidate_document

    record = CandidateProfile.model_validate(_line("data/samples/candidates.jsonl"))
    first = build_candidate_document(record)
    second = build_candidate_document(record)
    changed = build_candidate_document(
        record.model_copy(update={"target_roles": [*record.target_roles, "New Semantic Role"]})
    )

    assert first.document_fingerprint == second.document_fingerprint
    assert first.document_fingerprint != changed.document_fingerprint


def test_all_frozen_project_construction_signals_are_absent_from_candidate_text() -> None:
    from app.schemas.candidate import CandidateProfile
    from app.services.retrieval.documents import build_candidate_document

    for line in (REPOSITORY_ROOT / "data/samples/candidates.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        record = CandidateProfile.model_validate(json.loads(line))
        document = build_candidate_document(record)
        for project in record.projects:
            signals = {
                value.strip()
                for value in re.split(r"\s+[—–-]\s+", project.name)
                if value.strip()
            } | {project.name}
            assert all(
                signal.casefold() not in document.text.casefold()
                for signal in signals
            )
