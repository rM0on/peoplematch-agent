from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobProfile
from app.schemas.persistence import CandidateRecord, JobRecord
from app.services.cross_encoder.contract import PAIR_ORDER


def _value(value: object) -> str:
    raw = getattr(value, "value", value)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(raw)).strip())


def _values(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _value(value)
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _section(label: str, values: Iterable[object]) -> str:
    normalized = _values(values)
    return f"{label}: {' | '.join(normalized)}" if normalized else ""


def _serialize(sections: Iterable[str]) -> str:
    return "\n".join(section for section in sections if section)


def build_candidate_text(record: CandidateProfile | CandidateRecord) -> str:
    available = [
        evidence
        for evidence in record.project_evidence
        if _value(evidence.verification_status) == "available"
    ]
    return _serialize(
        (
            _section("TARGET ROLES", record.target_roles),
            _section("SKILLS", (skill.name for skill in record.skills)),
            _section(
                "PROJECT TECHNOLOGIES",
                (value for project in record.projects for value in project.technologies),
            ),
            _section(
                "PROJECT-CLAIMED SKILLS",
                (value for project in record.projects for value in project.skills_demonstrated),
            ),
            _section(
                "VERIFIED EVIDENCE SKILLS",
                (value for evidence in available for value in evidence.supports_skills),
            ),
            _section("AI TOOLS", record.ai_tools),
            _section(
                "LOCATION",
                (
                    *record.preferred_locations.cities,
                    record.preferred_locations.remote_policy,
                    record.preferred_locations.relocation_open,
                ),
            ),
            _section("SENIORITY", (record.seniority,)),
            _section("WORK STYLE", record.work_style.team_stage_preference),
        )
    )


def _requirements(label: str, requirements: Iterable[object]) -> str:
    return _section(
        label,
        (
            f"{_value(requirement.category)}: {_value(requirement.text)}"
            for requirement in requirements
        ),
    )


def build_job_text(record: JobProfile | JobRecord) -> str:
    return _serialize(
        (
            _section("ROLE TITLE", (record.role_title,)),
            _section("ROLE DIRECTION", record.role_direction),
            _requirements("MUST HAVE", record.must_have),
            _requirements("NICE TO HAVE", record.nice_to_have),
            _section(
                "LOCATION",
                (
                    *record.location.cities,
                    record.location.remote_policy,
                    record.location.relocation_supported,
                ),
            ),
            _section("SENIORITY", record.seniority_requirement),
            _section("PRODUCT STAGE", (record.product_stage,)),
        )
    )


@dataclass(frozen=True)
class CrossEncoderPairText:
    text_a: str
    text_b: str
    pair_order: str = PAIR_ORDER


def build_pair_text(
    job: JobProfile | JobRecord, candidate: CandidateProfile | CandidateRecord
) -> CrossEncoderPairText:
    return CrossEncoderPairText(
        text_a=build_job_text(job),
        text_b=build_candidate_text(candidate),
    )
