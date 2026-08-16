from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _profiles():
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobProfile

    candidate = CandidateProfile.model_validate(
        json.loads(
            (ROOT / "data/samples/candidates.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
    )
    job = JobProfile.model_validate(
        json.loads(
            (ROOT / "data/samples/jobs.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
    )
    return candidate, job


@pytest.mark.parametrize(
    ("original", "expected_normalized", "expected_tokens"),
    [
        ("C", "c", ("c",)),
        ("C++", "c++", ("c++",)),
        ("C#", "c#", ("c#",)),
        ("F", "f", ("f",)),
        ("F#", "f#", ("f#",)),
        (".NET", ".net", (".net",)),
        ("ASP.NET", "aspnet", ("aspnet",)),
        ("Node.js", "nodejs", ("nodejs",)),
        ("NodeJS", "nodejs", ("nodejs",)),
        ("Next.js", "nextjs", ("nextjs",)),
        ("NextJS", "nextjs", ("nextjs",)),
        ("Vue.js", "vuejs", ("vuejs",)),
        ("React.js", "reactjs", ("reactjs",)),
        ("C/C++", "c c++", ("c", "c++")),
        ("CI/CD", "ci cd", ("ci", "cd")),
        ("GPT-4", "gpt 4", ("gpt", "4")),
        ("GPT-4o", "gpt 4o", ("gpt", "4o")),
        ("GPT-4.1", "gpt 4.1", ("gpt", "4.1")),
        ("Java", "java", ("java",)),
        ("JavaScript", "javascript", ("javascript",)),
    ],
)
def test_technical_identifier_normalization_matrix(
    original: str,
    expected_normalized: str,
    expected_tokens: tuple[str, ...],
) -> None:
    from app.services.features.normalization import normalize_text, normalized_tokens

    assert normalize_text(original) == expected_normalized
    assert normalized_tokens(original) == expected_tokens


def test_technical_normalizer_has_a_v2_contract_identity() -> None:
    from app.services.features.normalization import NORMALIZER_VERSION

    assert NORMALIZER_VERSION == "text_nfkc_casefold_technical_tokens_v2"


def test_leading_and_numeric_dots_preserve_technical_identity() -> None:
    from app.services.features.normalization import normalize_text

    assert normalize_text(".NET") != normalize_text("NET")
    assert normalize_text("GPT-4.1") != normalize_text("GPT-41")


@pytest.mark.parametrize(
    ("capability", "requirement_text"),
    [
        ("C", "C++ delivery experience"),
        ("C", "C# delivery experience"),
        ("C++", "C# delivery experience"),
        ("C#", "C++ delivery experience"),
        ("F", "F# delivery experience"),
        ("F#", "F delivery experience"),
        (".NET", "ASP.NET delivery experience"),
        ("Java", "JavaScript delivery experience"),
    ],
)
def test_distinct_technical_identifiers_do_not_match(
    capability: str, requirement_text: str
) -> None:
    from app.schemas.job import JobRequirement
    from app.services.features.matching import match_requirement, normalized_atoms

    requirement = JobRequirement(
        requirement_id="req_distinct_technical_identifier",
        text=requirement_text,
        category="skill",
        evidence_expectation="Reviewable structured technical evidence",
    )

    assert match_requirement(requirement, normalized_atoms([capability])).value == 0


@pytest.mark.parametrize(
    ("capability", "requirement_text"),
    [
        ("Node.js", "NodeJS delivery experience"),
        ("NodeJS", "Node.js delivery experience"),
        ("Next.js", "NextJS delivery experience"),
        ("NextJS", "Next.js delivery experience"),
    ],
)
def test_dot_spelling_variants_share_one_lexical_identity(
    capability: str, requirement_text: str
) -> None:
    from app.schemas.job import JobRequirement
    from app.services.features.matching import match_requirement, normalized_atoms

    requirement = JobRequirement(
        requirement_id="req_dot_spelling_variant",
        text=requirement_text,
        category="skill",
        evidence_expectation="Reviewable structured technical evidence",
    )

    assert match_requirement(requirement, normalized_atoms([capability])).value == 1


def test_symbol_distinctions_propagate_to_all_affected_pair_features() -> None:
    from app.schemas.candidate import ProjectEvidence, SkillClaim
    from app.schemas.job import JobRequirement
    from app.services.features.extractor import extract_pair_features

    candidate, job = _profiles()
    project = candidate.projects[0].model_copy(
        update={"technologies": ["C++"], "skills_demonstrated": ["C++"]}
    )
    candidate = candidate.model_copy(
        update={
            "skills": [SkillClaim(name="C++", category="backend")],
            "projects": [project],
            "project_evidence": [
                ProjectEvidence(
                    evidence_id="ev_technical_normalization",
                    project_id=project.project_id,
                    supports_skills=["C++"],
                    evidence_type="tests",
                    statement="Structured synthetic evidence supports C++ only.",
                    artifact_ref="sandbox://feature-test/technical-normalization",
                    verification_status="available",
                )
            ],
            "ai_tools": ["Tool++"],
        }
    )
    csharp_requirement = JobRequirement(
        requirement_id="req_csharp_only",
        text="Hands-on C# delivery experience",
        category="skill",
        evidence_expectation="Reviewable C# implementation evidence",
    )
    tool_hash_requirement = JobRequirement(
        requirement_id="req_tool_hash_only",
        text="Hands-on Tool# delivery experience",
        category="ai_tooling",
        evidence_expectation="Reviewable Tool# workflow evidence",
    )
    job = job.model_copy(
        update={
            "must_have": [csharp_requirement],
            "nice_to_have": [tool_hash_requirement],
        }
    )

    result = extract_pair_features(candidate, job)

    assert result.vector.skill_fit_score == 0
    assert result.vector.project_evidence_score == 0
    assert result.vector.missing_penalty == 1
    assert result.vector.ai_tool_score == 0
