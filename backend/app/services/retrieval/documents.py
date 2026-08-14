from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobProfile
from app.schemas.persistence import CandidateRecord, JobRecord
from app.schemas.retrieval import CandidateRetrievalDocument, JobRetrievalDocument


RETRIEVAL_DOCUMENT_VERSION = "retrieval_doc_v4"


def _values(label: str, values: Iterable[str]) -> str:
    normalized = [value.strip() for value in values if value and value.strip()]
    return f"{label}: {' | '.join(normalized)}" if normalized else ""


def _semantic_text(sections: Iterable[str]) -> str:
    return "\n".join(section for section in sections if section)


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _remove_owned_project_construction_signals(
    text: str, project_names: Iterable[str]
) -> str:
    names = {value.strip() for value in project_names if value and value.strip()}
    signals = set(names)
    for name in names:
        signals.update(
            value.strip()
            for value in re.split(r"\s+[—–-]\s+", name)
            if value.strip()
        )
    sanitized = text
    for signal in sorted(
        signals,
        key=len,
        reverse=True,
    ):
        sanitized = re.sub(
            re.escape(signal), "the project", sanitized, flags=re.IGNORECASE
        )
    return sanitized


def build_candidate_document(
    record: CandidateProfile | CandidateRecord,
) -> CandidateRetrievalDocument:
    text = _remove_owned_project_construction_signals(
        _semantic_text(
        (
            _values("target_roles", record.target_roles),
            _values("skills", (skill.name for skill in record.skills)),
            _values("skill_categories", (skill.category.value for skill in record.skills)),
            _values("project_summaries", (project.summary for project in record.projects)),
            _values("project_roles", (project.role for project in record.projects)),
            _values(
                "project_technologies",
                (value for project in record.projects for value in project.technologies),
            ),
            _values(
                "project_skills",
                (value for project in record.projects for value in project.skills_demonstrated),
            ),
            _values(
                "evidence_supported_skills",
                (value for evidence in record.project_evidence for value in evidence.supports_skills),
            ),
            _values(
                "evidence_types",
                (evidence.evidence_type.value for evidence in record.project_evidence),
            ),
            _values(
                "evidence_statements",
                (evidence.statement for evidence in record.project_evidence),
            ),
            _values("ai_tools", record.ai_tools),
        )),
        (project.name for project in record.projects),
    )
    return CandidateRetrievalDocument(
        entity_id=record.candidate_id,
        document_version=RETRIEVAL_DOCUMENT_VERSION,
        document_fingerprint=_fingerprint(text),
        text=text,
        cities=record.preferred_locations.cities,
        seniorities=[record.seniority],
    )


def build_job_document(record: JobProfile | JobRecord) -> JobRetrievalDocument:
    requirements = [*record.must_have, *record.nice_to_have]
    text = _semantic_text(
        (
            _values("role_title", (record.role_title,)),
            _values("role_direction", record.role_direction),
            _values("requirement_text", (item.text for item in requirements)),
            _values("requirement_categories", (item.category.value for item in requirements)),
            _values(
                "evidence_expectations",
                (item.evidence_expectation for item in requirements),
            ),
            _values("evaluation_focus", record.evaluation_focus),
        )
    )
    return JobRetrievalDocument(
        entity_id=record.job_id,
        document_version=RETRIEVAL_DOCUMENT_VERSION,
        document_fingerprint=_fingerprint(text),
        text=text,
        cities=record.location.cities,
        seniorities=record.seniority_requirement,
    )
