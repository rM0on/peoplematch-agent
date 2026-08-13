from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.candidate import CandidateProfile  # noqa: E402
from app.schemas.job import JobProfile  # noqa: E402
from app.schemas.labels import PairwisePreference, RelevanceLabel  # noqa: E402
from app.services.dataset_semantics import (  # noqa: E402
    available_evidence_skills,
    evidence_backed_requirement_skills,
    evidence_ids_covering_skills,
    hard_negative_overlap_terms,
    job_signal_terms,
    qualifying_hard_negative_terms,
    semantic_signal_terms,
)
from phase1_candidate_blueprints import (  # noqa: E402
    ADJACENT_SKILLS,
    ALTERNATE_PROJECT_FAMILIES,
    CANDIDATE_BLUEPRINTS,
    NARRATIVE_OPENERS,
    PROJECT_NAME_QUALIFIERS,
    PROJECT_SCOPE_NOTES,
    TECHNOLOGY_EXTRAS,
    VARIANTS,
    VARIANT_PERMUTATIONS,
)
from phase1_job_blueprints import (  # noqa: E402
    ADDITIONAL_JOB_VARIANTS,
    JOB_BLUEPRINTS,
)


SCHEMA_VERSION = "1.0"
DATA_ORIGIN = "synthetic_sandbox"
ANNOTATION_SOURCE = "synthetic_curated"

CURATED_JOB_GRADE_CANDIDATES = {
    "job_001": {
        3: ["cand_005", "cand_007"],
        2: ["cand_006", "cand_041"],
        1: ["cand_042", "cand_045", "cand_046", "cand_011", "cand_012"],
        0: ["cand_021", "cand_022", "cand_033"],
    },
    "job_002": {
        3: ["cand_007", "cand_005"],
        2: ["cand_006", "cand_018"],
        1: ["cand_017", "cand_048", "cand_046"],
        0: ["cand_009", "cand_010", "cand_013", "cand_014", "cand_025"],
    },
}





def _candidate_risk(archetype: str, variant_index: int) -> Dict[str, Any]:
    if archetype == "overclaim_candidate":
        return {
            "level": "high",
            "reasons": [
                "Several advanced AI specialties are claimed, but at most one narrow executable artifact is available.",
                "The listed projects do not demonstrate comparable depth across agent, ranking, and serving work.",
            ],
        }
    if variant_index == 3:
        return {
            "level": "high",
            "reasons": [
                "Advanced self-reported skill levels exceed the depth shown by the available project artifacts."
            ],
        }
    if variant_index == 1:
        return {
            "level": "medium",
            "reasons": [
                "One project is described without a directly available implementation artifact."
            ],
        }
    return {"level": "low", "reasons": []}


def _unique_strings(values: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(values))


def _candidate_skills(
    blueprint: Dict[str, Any], candidate_position: int
) -> List[tuple[str, str]]:
    skills = list(blueprint["skills"])
    adjacent = ADJACENT_SKILLS[blueprint["archetype"]]
    if candidate_position == 1:
        skills.append(adjacent[0])
    elif candidate_position == 2:
        skills.append(adjacent[1])
    elif candidate_position == 3:
        skills.extend(adjacent)
    return list(dict.fromkeys(skills))


def _evidence_statuses(
    archetype: str, variant_index: int, skill_count: int
) -> List[str]:
    if archetype == "overclaim_candidate":
        statuses = [
            "described" if index % 2 == 0 else "missing"
            for index in range(skill_count)
        ]
        if variant_index == 2:
            statuses[0] = "available"
        return statuses
    if variant_index in {0, 2}:
        return ["available"] * skill_count
    if variant_index == 1:
        pattern = ["available", "described", "missing"]
        return [pattern[index % len(pattern)] for index in range(skill_count)]
    pattern = ["described", "missing"]
    return [pattern[index % len(pattern)] for index in range(skill_count)]


def _evidence_type(skill_category: str, offset: int) -> str:
    by_category = {
        "evaluation": ["evaluation_report", "tests", "experiment_report"],
        "data": ["dataset", "tests", "readme"],
        "product_delivery": ["demo", "workflow_trace", "readme"],
        "frontend": ["demo", "tests", "code"],
        "llm_application": ["workflow_trace", "tests", "architecture_doc"],
        "recommendation": ["experiment_report", "evaluation_report", "code"],
        "retrieval_search": ["evaluation_report", "code", "dataset"],
        "ml_infra": ["architecture_doc", "tests", "workflow_trace"],
        "model_algorithm": ["experiment_report", "code", "evaluation_report"],
        "security": ["tests", "evaluation_report", "architecture_doc"],
        "backend": ["code", "tests", "architecture_doc"],
    }
    options = by_category.get(skill_category, ["code", "tests", "readme"])
    return options[offset % len(options)]


def build_candidates() -> List[CandidateProfile]:
    candidates: List[CandidateProfile] = []
    candidate_number = 0
    for blueprint in CANDIDATE_BLUEPRINTS:
        variant_order = VARIANT_PERMUTATIONS[blueprint["archetype"]]
        for candidate_position, variant_index in enumerate(variant_order):
            variant = VARIANTS[variant_index]
            candidate_number += 1
            candidate_id = f"cand_{candidate_number:03d}"
            seniority = variant["seniority"]
            if blueprint["archetype"] == "early_career_strong_project":
                seniority = "early_career"

            candidate_skills = _candidate_skills(blueprint, candidate_position)
            alternate_family = ALTERNATE_PROJECT_FAMILIES[blueprint["archetype"]]
            family = (
                {
                    "names": blueprint["project_names"],
                    "summaries": blueprint["project_summaries"],
                }
                if candidate_position in {0, 2}
                else alternate_family
            )
            projects: List[Dict[str, Any]] = []
            for project_index in range(2):
                project_id = f"prj_{candidate_id}_{project_index + 1:02d}"
                if blueprint["archetype"] == "overclaim_candidate":
                    outcomes = [
                        "Recorded claimed concepts and outstanding artifact gaps without asserting an implementation result."
                    ]
                else:
                    outcomes = [
                        "Implemented a reproducible local workflow with reviewer-visible checks and limitations."
                        if project_index == 0
                        else "Recorded deterministic checks, trade-offs, and an architecture note for inspection."
                    ]
                if "project_outcomes" in variant["missing"]:
                    outcomes = ["Outcome detail was not present in the source profile."]
                demonstrated = [
                    skill_name
                    for skill_index, (skill_name, _) in enumerate(candidate_skills)
                    if skill_index % 2 == project_index
                ]
                technology_extra = TECHNOLOGY_EXTRAS[
                    (variant_index + project_index) % len(TECHNOLOGY_EXTRAS)
                ]
                project_qualifier = PROJECT_NAME_QUALIFIERS[candidate_position]
                scope_note = PROJECT_SCOPE_NOTES[candidate_position]
                if blueprint["archetype"] == "overclaim_candidate":
                    project_qualifier = [
                        "Capability Inventory",
                        "Claim Review",
                        "Artifact Audit",
                        "Integration Outline",
                    ][candidate_position]
                    scope_note = (
                        "The artifact review records claimed scope without treating "
                        "descriptions as executable proof."
                    )
                projects.append(
                    {
                        "project_id": project_id,
                        "name": (
                            f"{family['names'][project_index]} — "
                            f"{project_qualifier}"
                        ),
                        "summary": (
                            f"{family['summaries'][project_index]} "
                            f"{scope_note}"
                        ),
                        "role": {
                            0: "Lead sandbox builder",
                            1: "Feature owner in a structured team",
                            2: "Independent project owner",
                            3: "Concept contributor",
                        }[variant_index],
                        "technologies": _unique_strings(
                            [*blueprint["technologies"], technology_extra]
                        ),
                        "outcomes": outcomes,
                        "skills_demonstrated": demonstrated,
                    }
                )

            evidence_statuses = _evidence_statuses(
                blueprint["archetype"], variant_index, len(candidate_skills)
            )
            evidence: List[Dict[str, Any]] = []
            for evidence_index, ((skill_name, skill_category), status) in enumerate(
                zip(candidate_skills, evidence_statuses)
            ):
                project_index = evidence_index % 2
                evidence_type = _evidence_type(
                    skill_category, evidence_index + candidate_position
                )
                evidence.append(
                    {
                        "evidence_id": f"ev_{candidate_id}_{evidence_index + 1:02d}",
                        "project_id": projects[project_index]["project_id"],
                        "supports_skills": [skill_name],
                        "evidence_type": evidence_type,
                        "statement": (
                            f"The {evidence_type.replace('_', ' ')} artifact documents "
                            f"how {skill_name} was used "
                            f"inside {projects[project_index]['name']}."
                        ),
                        "artifact_ref": (
                            f"sandbox://candidate/{candidate_id}/project/"
                            f"{projects[project_index]['project_id']}/{evidence_type}"
                        ),
                        "verification_status": status,
                    }
                )

            city, remote_policy, relocation_open = variant["location"]
            work_arrangement_article = "an" if remote_policy == "onsite" else "a"
            available_count = evidence_statuses.count("available")
            if available_count == len(evidence_statuses):
                evidence_summary = "Executable artifacts are linked for the core claims."
            elif available_count:
                evidence_summary = (
                    "One or more narrow artifacts are available, while other claims remain "
                    "described or unsupported."
                )
            else:
                evidence_summary = (
                    "The profile describes artifacts, but none is directly available for review."
                )
            raw_text = (
                NARRATIVE_OPENERS[variant_index].format(
                    discipline=blueprint["discipline"]
                )
                + f" The candidate presents {projects[0]['name']} as the clearest example: "
                + blueprint["project_summaries"][0]
                + f" A second piece, {projects[1]['name']}, is described as follows: "
                + projects[1]["summary"]
                + f" The stated preference is {city} with {work_arrangement_article} "
                + f"{remote_policy} work arrangement, "
                + f"and the profile targets {', '.join(blueprint['targets'])}. "
                + evidence_summary
            )

            candidates.append(
                CandidateProfile.model_validate(
                    {
                        "candidate_id": candidate_id,
                        "name": f"Candidate {candidate_number:03d}",
                        "archetype": blueprint["archetype"],
                        "raw_text": raw_text,
                        "skills": [
                            {
                                "name": name,
                                "category": category,
                                "self_reported_level": variant["level"],
                            }
                            for name, category in candidate_skills
                        ],
                        "projects": projects,
                        "project_evidence": evidence,
                        "github_url": None
                        if "github_url" in variant["missing"]
                        else f"https://example.invalid/candidate/{candidate_id}",
                        "ai_tools": blueprint["tools"],
                        "target_roles": blueprint["targets"],
                        "preferred_locations": {
                            "cities": [city],
                            "remote_policy": remote_policy,
                            "relocation_open": relocation_open,
                        },
                        "seniority": seniority,
                        "work_style": {
                            "team_stage_preference": variant["stages"],
                            "collaboration_style": variant["collaboration"],
                        },
                        "missing_fields": variant["missing"],
                        "overclaim_risk": _candidate_risk(
                            blueprint["archetype"], variant_index
                        ),
                        "data_origin": DATA_ORIGIN,
                        "schema_version": SCHEMA_VERSION,
                    }
                )
            )
    return candidates





def _all_job_blueprints() -> List[Dict[str, Any]]:
    blueprints = [dict(item) for item in JOB_BLUEPRINTS]
    for variant in ADDITIONAL_JOB_VARIANTS:
        item = dict(JOB_BLUEPRINTS[variant["base"]])
        item.update({key: value for key, value in variant.items() if key != "base"})
        blueprints.append(item)
    return blueprints


def build_jobs() -> List[JobProfile]:
    jobs: List[JobProfile] = []
    for job_number, blueprint in enumerate(_all_job_blueprints(), start=1):
        job_id = f"job_{job_number:03d}"
        requirement_specs = [
            (
                f"Demonstrated work in {blueprint['focus']}",
                "role_direction",
                "A project narrative and artifact showing direct ownership in this work direction",
            ),
            (
                f"Practical use of {blueprint['skills'][0]}",
                "skill",
                "Code, tests, or an experiment report tied to a named project",
            ),
            (
                f"Practical use of {blueprint['skills'][1]}",
                "skill",
                "A reviewable implementation or evaluation artifact",
            ),
            (
                f"Evaluation evidence involving {blueprint['skills'][2]}",
                "project_evidence",
                "A dataset, test suite, or evaluation report with stated limitations",
            ),
            (
                f"Comfort working in a {blueprint['stage'].replace('_', '-')} product stage",
                "work_style",
                "Project context describing ownership and collaboration under that stage",
            ),
            (
                f"Availability for the stated {blueprint['city']} {blueprint['remote']} arrangement",
                "location",
                "A declared location, remote-policy preference, or relocation decision",
            ),
            (
                "Seniority evidence consistent with "
                + " or ".join(blueprint["seniority"]),
                "seniority",
                "Project ownership and responsibility scope consistent with the role level",
            ),
        ]
        must_have = [
            {
                "requirement_id": f"req_{job_id}_{index:02d}",
                "text": text,
                "category": category,
                "evidence_expectation": expectation,
            }
            for index, (text, category, expectation) in enumerate(
                requirement_specs, start=1
            )
        ]
        nice_to_have = [
            {
                "requirement_id": f"req_{job_id}_08",
                "text": f"Experience communicating {blueprint['focus']} to product partners",
                "category": "experience",
                "evidence_expectation": "Architecture notes, decision records, or a project readme",
            },
            {
                "requirement_id": f"req_{job_id}_09",
                "text": "Familiarity with typed AI tooling and reproducible local workflows",
                "category": "ai_tooling",
                "evidence_expectation": "A described or available sandbox artifact",
            },
        ]
        article = "an" if blueprint["title"].startswith(("AI", "LLM", "ML", "NLP")) else "a"
        arrangement_article = "an" if blueprint["remote"] == "onsite" else "a"
        raw_jd = (
            f"{blueprint['company']} is a fictional sandbox company hiring {article} {blueprint['title']}. "
            f"The team is focused on {blueprint['focus']}.\n\n"
            "Responsibilities\n"
            f"- Own a reviewable slice of {blueprint['direction'][0].replace('_', ' ')} work from problem framing through validation.\n"
            "- Keep claimed capability separate from project artifacts and document failure cases.\n"
            "- Collaborate with engineering and product partners on scoped local experiments.\n\n"
            "Requirements\n"
            f"- Demonstrated {blueprint['skills'][0]} and {blueprint['skills'][1]} work.\n"
            f"- Evidence of {blueprint['skills'][2]} through code, tests, datasets, or written evaluation.\n"
            f"- Working style suited to a {blueprint['stage'].replace('_', '-')} team.\n\n"
            f"- Availability for {blueprint['city']} under {arrangement_article} "
            f"{blueprint['remote']} arrangement and "
            f"scope consistent with {', '.join(blueprint['seniority'])}.\n\n"
            "Nice to have\n"
            "- Clear technical writing and experience explaining trade-offs to cross-functional reviewers."
        )
        jobs.append(
            JobProfile.model_validate(
                {
                    "job_id": job_id,
                    "company_name": blueprint["company"],
                    "role_title": blueprint["title"],
                    "archetype": blueprint["archetype"],
                    "raw_jd": raw_jd,
                    "must_have": must_have,
                    "nice_to_have": nice_to_have,
                    "role_direction": blueprint["direction"],
                    "team_tags": [
                        "fictional_company",
                        f"{blueprint['stage']}_team",
                        "evidence_review",
                    ],
                    "location": {
                        "cities": [blueprint["city"]],
                        "remote_policy": blueprint["remote"],
                        "relocation_supported": blueprint["relocation"],
                    },
                    "seniority_requirement": blueprint["seniority"],
                    "product_stage": blueprint["stage"],
                    "evaluation_focus": [
                        blueprint["skills"][2],
                        "project evidence",
                        "constraint reasoning",
                    ],
                    "data_origin": DATA_ORIGIN,
                    "schema_version": SCHEMA_VERSION,
                }
            )
        )
    return jobs


def build_query_splits(jobs: Sequence[JobProfile]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "split_policy": "job_query_grouped",
        "description": "Every job query and all of its labels remain in one split.",
        "splits": {
            "train": [job.job_id for job in jobs[:14]],
            "dev": [job.job_id for job in jobs[14:19]],
            "test": [job.job_id for job in jobs[19:24]],
        },
    }


def _split_lookup(split_manifest: Dict[str, Any]) -> Dict[str, str]:
    return {
        job_id: split
        for split, job_ids in split_manifest["splits"].items()
        for job_id in job_ids
    }


def _rotated(items: Sequence[CandidateProfile], offset: int) -> List[CandidateProfile]:
    if not items:
        return []
    normalized = offset % len(items)
    return list(items[normalized:]) + list(items[:normalized])


def _take_unique(
    pool: Sequence[CandidateProfile],
    count: int,
    selected_ids: set[str],
    offset: int,
) -> List[CandidateProfile]:
    selected: List[CandidateProfile] = []
    for candidate in _rotated(pool, offset):
        if candidate.candidate_id in selected_ids:
            continue
        selected.append(candidate)
        selected_ids.add(candidate.candidate_id)
        if len(selected) == count:
            break
    if len(selected) != count:
        raise RuntimeError(f"unable to choose {count} unique candidates from label pool")
    return selected


def _diverse_weak_pool(
    archetypes: Sequence[str],
    candidates_by_archetype: Dict[str, List[CandidateProfile]],
    job: JobProfile,
) -> List[CandidateProfile]:
    groups = [
        sorted(
            candidates_by_archetype[archetype],
            key=lambda candidate: (
                len(qualifying_hard_negative_terms(candidate, job)),
                int(candidate.overclaim_risk.level.value == "high"),
                candidate.candidate_id,
            ),
            reverse=True,
        )
        for archetype in archetypes
    ]
    interleaved: List[CandidateProfile] = []
    for position in range(max(len(group) for group in groups)):
        for group in groups:
            if position < len(group):
                interleaved.append(group[position])
    return interleaved


def _constraint_mismatches(
    candidate: CandidateProfile, job: JobProfile
) -> List[str]:
    codes: List[str] = []
    candidate_cities = set(candidate.preferred_locations.cities)
    job_cities = set(job.location.cities)
    if (
        candidate_cities.isdisjoint(job_cities)
        and not candidate.preferred_locations.relocation_open
        and job.location.remote_policy.value != "remote"
    ):
        codes.append("LOCATION_MISMATCH")
    if candidate.seniority not in job.seniority_requirement:
        codes.append("SENIORITY_MISMATCH")
    if (
        job.product_stage.value == "zero_to_one"
        and "mature" in candidate.work_style.team_stage_preference
        and "zero_to_one" not in candidate.work_style.team_stage_preference
    ):
        codes.append("WORK_STYLE_MISMATCH")
    return codes


def _is_strong_candidate(candidate: CandidateProfile, job: JobProfile) -> bool:
    required_skills = evidence_backed_requirement_skills(job)
    return (
        required_skills <= available_evidence_skills(candidate)
        and not _constraint_mismatches(candidate, job)
    )


def _semantic_supporting_evidence_ids(
    candidate: CandidateProfile, job: JobProfile, limit: int
) -> List[str]:
    job_signals = job_signal_terms(job)
    selected: List[str] = []
    for evidence in candidate.project_evidence:
        if evidence.verification_status.value != "available":
            continue
        evidence_signals = semantic_signal_terms(evidence.supports_skills)
        if evidence_signals & job_signals:
            selected.append(evidence.evidence_id)
        if len(selected) == limit:
            break
    return selected


def _candidate_fit_key(
    candidate: CandidateProfile,
    job: JobProfile,
    preferred_archetypes: Sequence[str],
) -> tuple[int, int, int, int, str]:
    exact_coverage = len(
        evidence_backed_requirement_skills(job) & available_evidence_skills(candidate)
    )
    semantic_overlap = len(hard_negative_overlap_terms(candidate, job))
    preferred = int(candidate.archetype.value in preferred_archetypes)
    constraint_penalty = -len(_constraint_mismatches(candidate, job))
    return (
        exact_coverage,
        preferred,
        semantic_overlap,
        constraint_penalty,
        candidate.candidate_id,
    )


def _mismatch_codes(
    candidate: CandidateProfile,
    job: JobProfile,
    blueprint: Dict[str, Any],
    grade: int,
    hard_negative: bool,
) -> List[str]:
    codes: List[str] = []
    required_skills = evidence_backed_requirement_skills(job)
    available_skills = available_evidence_skills(candidate)
    missing_skills = required_skills - available_skills
    direction_aligned = candidate.archetype.value in blueprint["preferred"]
    semantic_overlap = hard_negative_overlap_terms(candidate, job)

    if grade == 2:
        if not direction_aligned:
            codes.append("DIRECTION_MISMATCH")
        if missing_skills:
            codes.extend(["MUST_HAVE_MISSING", "PROJECT_DEPTH_GAP"])
            if semantic_overlap:
                codes.append("EVIDENCE_INSUFFICIENT")
        codes.extend(_constraint_mismatches(candidate, job))
        if not codes:
            codes.append("PROJECT_DEPTH_GAP")
    elif grade == 1:
        if not direction_aligned:
            codes.append("DIRECTION_MISMATCH")
        if missing_skills:
            codes.extend(["MUST_HAVE_MISSING", "PROJECT_DEPTH_GAP"])
        if candidate.overclaim_risk.level.value == "high":
            codes.append("OVERCLAIM_RISK")
        if missing_skills or any(
            evidence.verification_status.value != "available"
            for evidence in candidate.project_evidence
        ):
            codes.append("EVIDENCE_INSUFFICIENT")
        if hard_negative:
            codes.append("KEYWORD_FALSE_POSITIVE")
        codes.extend(_constraint_mismatches(candidate, job))
    elif grade == 0:
        codes.extend(["MUST_HAVE_MISSING", "DIRECTION_MISMATCH"])
        codes.extend(_constraint_mismatches(candidate, job))
    return list(dict.fromkeys(codes))


def _affected_requirement_ids(
    job: JobProfile, mismatch_codes: Sequence[str], grade: int
) -> List[str]:
    category_by_code = {
        "DIRECTION_MISMATCH": "role_direction",
        "EVIDENCE_INSUFFICIENT": "project_evidence",
        "KEYWORD_FALSE_POSITIVE": "skill",
        "MUST_HAVE_MISSING": "skill",
        "LOCATION_MISMATCH": "location",
        "SENIORITY_MISMATCH": "seniority",
        "WORK_STYLE_MISMATCH": "work_style",
        "OVERCLAIM_RISK": "project_evidence",
        "AI_TOOLING_GAP": "ai_tooling",
        "PROJECT_DEPTH_GAP": "project_evidence",
    }
    requirements = [*job.must_have, *job.nice_to_have]
    ids_by_category: Dict[str, List[str]] = defaultdict(list)
    for requirement in requirements:
        ids_by_category[requirement.category.value].append(
            requirement.requirement_id
        )
    affected: List[str] = []
    for code in mismatch_codes:
        category = category_by_code.get(code)
        if category is not None:
            affected.extend(ids_by_category.get(category, []))
        if code in {"MUST_HAVE_MISSING", "PROJECT_DEPTH_GAP"}:
            affected.extend(ids_by_category.get("project_evidence", []))
    if not affected and grade <= 1:
        affected = [job.must_have[0].requirement_id, job.must_have[1].requirement_id]
    return list(dict.fromkeys(affected))


def _rationale(
    candidate: CandidateProfile,
    job: JobProfile,
    grade: int,
    mismatch_codes: Sequence[str],
    supporting_count: int,
    hard_negative: bool,
) -> str:
    discipline = candidate.archetype.value.replace("_", " ")
    direction = job.role_direction[0].replace("_", " ")
    required_skills = evidence_backed_requirement_skills(job)
    available_skills = available_evidence_skills(candidate)
    covered = sorted(required_skills & available_skills)
    missing = sorted(required_skills - available_skills)
    overlap = hard_negative_overlap_terms(candidate, job)
    covered_text = ", ".join(covered) if covered else "no direct must-have"
    missing_text = ", ".join(missing) if missing else "none"
    gap_text = ", ".join(code.lower().replace("_", " ") for code in mismatch_codes)
    if grade == 3:
        return (
            f"{candidate.name} aligns with the {direction} direction of {job.role_title}; "
            f"{supporting_count} available sandbox artifacts cover {covered_text}, "
            "and no material location or work-style conflict is recorded."
        )
    if grade == 2:
        adjacent = ", ".join(overlap) if overlap else "reviewable adjacent engineering"
        return (
            f"{candidate.name} remains plausible for {job.role_title} because available "
            f"artifacts cover {covered_text} and adjacent evidence signals include {adjacent}. "
            f"It is not a strong match: {missing_text} lacks direct available evidence, and "
            f"the recorded gaps are {gap_text}."
        )
    if grade == 1:
        if hard_negative:
            return (
                f"Overlapping terms: {', '.join(overlap)}. Actual mismatch: {candidate.name} "
                f"is centered on {discipline}; available evidence covers {covered_text}, while "
                f"{missing_text} remains unsupported and the recorded gaps are {gap_text}."
            )
        return (
            f"{candidate.name} has weak fit for {job.role_title}: the profile is centered on "
            f"{discipline}, {missing_text} lacks available evidence, and the recorded gaps are "
            f"{gap_text}."
        )
    return (
        f"{candidate.name} is primarily oriented toward {discipline}, not the {direction} "
        f"work required by {job.role_title}; the documented gaps are {gap_text}."
    )


def build_labels_and_preferences(
    candidates: Sequence[CandidateProfile],
    jobs: Sequence[JobProfile],
    split_manifest: Dict[str, Any],
) -> tuple[List[RelevanceLabel], List[PairwisePreference]]:
    candidates_by_archetype: Dict[str, List[CandidateProfile]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_archetype[candidate.archetype.value].append(candidate)

    split_by_job = _split_lookup(split_manifest)
    labels: List[RelevanceLabel] = []
    preferences: List[PairwisePreference] = []
    label_number = 0
    preference_number = 0
    job_blueprints = _all_job_blueprints()

    distributions = [(2, 3, 4, 3), (2, 2, 3, 5), (2, 2, 5, 3)]
    for job_index, (job, blueprint) in enumerate(zip(jobs, job_blueprints)):
        strong_count, plausible_count, weak_count, nonmatch_count = distributions[
            job_index % len(distributions)
        ]
        selected_ids: set[str] = set()
        preferred_pool = sorted(
            [
            candidate
            for archetype in blueprint["preferred"]
            for candidate in candidates_by_archetype[archetype]
            if _is_strong_candidate(candidate, job)
            ],
            key=lambda candidate: candidate.candidate_id,
        )
        plausible_pool = sorted(
            [
                candidate
                for archetype in [*blueprint["preferred"], *blueprint["plausible"]]
                for candidate in candidates_by_archetype[archetype]
                if _semantic_supporting_evidence_ids(candidate, job, 1)
            ],
            key=lambda candidate: _candidate_fit_key(
                candidate, job, blueprint["preferred"]
            ),
            reverse=True,
        )
        hard_archetypes = list(
            dict.fromkeys([*blueprint["hard"], "overclaim_candidate"])
        )
        weak_pool = _diverse_weak_pool(
            hard_archetypes, candidates_by_archetype, job
        )
        nonmatch_pool = [
            candidate
            for candidate in candidates
            if candidate.archetype.value
            not in set(
                [
                    *blueprint["preferred"],
                    *blueprint["plausible"],
                    *blueprint["hard"],
                ]
            )
        ]

        if job.job_id in CURATED_JOB_GRADE_CANDIDATES:
            candidate_lookup = {
                candidate.candidate_id: candidate for candidate in candidates
            }
            chosen_by_grade = {
                grade: [candidate_lookup[candidate_id] for candidate_id in candidate_ids]
                for grade, candidate_ids in CURATED_JOB_GRADE_CANDIDATES[
                    job.job_id
                ].items()
            }
        else:
            chosen_by_grade = {
                3: _take_unique(preferred_pool, strong_count, selected_ids, job_index),
                2: _take_unique(
                    plausible_pool, plausible_count, selected_ids, job_index + 1
                ),
                1: _take_unique(weak_pool, weak_count, selected_ids, 0),
                0: _take_unique(
                    nonmatch_pool, nonmatch_count, selected_ids, job_index + 3
                ),
            }

        labels_for_job: List[RelevanceLabel] = []
        for grade in (3, 2, 1, 0):
            for candidate in chosen_by_grade[grade]:
                label_number += 1
                overlap_terms = hard_negative_overlap_terms(candidate, job)
                hard_negative = grade == 1 and bool(
                    qualifying_hard_negative_terms(candidate, job)
                )
                if grade == 3:
                    required_skills = evidence_backed_requirement_skills(job)
                    supporting = evidence_ids_covering_skills(
                        candidate, required_skills
                    )
                elif grade == 2:
                    supporting = _semantic_supporting_evidence_ids(candidate, job, 2)
                elif hard_negative:
                    supporting = _semantic_supporting_evidence_ids(candidate, job, 1)
                else:
                    supporting = []

                mismatch_codes = _mismatch_codes(
                    candidate, job, blueprint, grade, hard_negative
                )
                affected = _affected_requirement_ids(job, mismatch_codes, grade)
                label = RelevanceLabel.model_validate(
                    {
                        "label_id": f"lbl_{label_number:04d}",
                        "query_type": "job_to_candidate",
                        "job_id": job.job_id,
                        "candidate_id": candidate.candidate_id,
                        "relevance_grade": grade,
                        "hard_negative": hard_negative,
                        "mismatch_reasons": mismatch_codes,
                        "rationale": _rationale(
                            candidate,
                            job,
                            grade,
                            mismatch_codes,
                            len(supporting),
                            hard_negative,
                        ),
                        "supporting_evidence_ids": supporting,
                        "affected_requirement_ids": affected,
                        "confidence": {3: 0.92, 2: 0.82, 1: 0.89, 0: 0.95}[grade],
                        "annotation_source": ANNOTATION_SOURCE,
                        "split": split_by_job[job.job_id],
                        "schema_version": SCHEMA_VERSION,
                    }
                )
                labels.append(label)
                labels_for_job.append(label)

        grade_groups: Dict[int, List[RelevanceLabel]] = defaultdict(list)
        for label in labels_for_job:
            grade_groups[int(label.relevance_grade)].append(label)
        candidate_lookup = {
            candidate.candidate_id: candidate for candidate in candidates
        }
        grade_two_ranked = sorted(
            grade_groups[2],
            key=lambda label: _candidate_fit_key(
                candidate_lookup[label.candidate_id], job, blueprint["preferred"]
            ),
            reverse=True,
        )
        hard_losers = sorted(
            [label for label in grade_groups[1] if label.hard_negative],
            key=lambda label: len(
                hard_negative_overlap_terms(candidate_lookup[label.candidate_id], job)
            ),
            reverse=True,
        )
        if not hard_losers:
            raise RuntimeError(f"{job.job_id} has no semantic hard negative")
        comparison_pairs = [
            (grade_groups[3][0], hard_losers[0]),
            (grade_two_ranked[0], hard_losers[min(1, len(hard_losers) - 1)]),
        ]
        for winner, loser in comparison_pairs:
            preference_number += 1
            winner_candidate = candidate_lookup[winner.candidate_id]
            loser_candidate = candidate_lookup[loser.candidate_id]
            reason_codes = loser.mismatch_reasons[:3] or ["PROJECT_DEPTH_GAP"]
            required_skills = evidence_backed_requirement_skills(job)
            winner_coverage = sorted(
                required_skills & available_evidence_skills(winner_candidate)
            )
            loser_missing = sorted(
                required_skills - available_evidence_skills(loser_candidate)
            )
            loser_overlap = hard_negative_overlap_terms(loser_candidate, job)
            preferences.append(
                PairwisePreference.model_validate(
                    {
                        "preference_id": f"pref_{preference_number:03d}",
                        "job_id": job.job_id,
                        "winner_candidate_id": winner.candidate_id,
                        "loser_candidate_id": loser.candidate_id,
                        "reason_codes": [code.value for code in reason_codes],
                        "rationale": (
                            f"For {job.role_title}, {winner_candidate.name} is preferred over "
                            f"{loser_candidate.name}. Available winner artifacts cover "
                            f"{', '.join(winner_coverage) if winner_coverage else 'adjacent reviewable evidence'}. "
                            f"The loser overlaps on {', '.join(loser_overlap)} but lacks available "
                            f"evidence for {', '.join(loser_missing) if loser_missing else 'the required depth'}; "
                            f"the decisive gap is {reason_codes[0].value.lower().replace('_', ' ')}."
                        ),
                        "confidence": 0.9
                        if winner.relevance_grade == 3
                        else 0.84,
                        "annotation_source": ANNOTATION_SOURCE,
                        "split": split_by_job[job.job_id],
                        "schema_version": SCHEMA_VERSION,
                    }
                )
            )
    return labels, preferences


def _write_jsonl(path: Path, records: Sequence[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(
                json.dumps(
                    record.model_dump(mode="json"),
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )


def main() -> int:
    candidates = build_candidates()
    jobs = build_jobs()
    split_manifest = build_query_splits(jobs)
    labels, preferences = build_labels_and_preferences(
        candidates, jobs, split_manifest
    )

    _write_jsonl(
        REPOSITORY_ROOT / "data" / "samples" / "candidates.jsonl", candidates
    )
    _write_jsonl(REPOSITORY_ROOT / "data" / "samples" / "jobs.jsonl", jobs)
    _write_jsonl(
        REPOSITORY_ROOT / "data" / "samples" / "labels.jsonl", labels
    )
    _write_jsonl(
        REPOSITORY_ROOT / "data" / "eval" / "pairwise_preferences.jsonl",
        preferences,
    )
    split_path = REPOSITORY_ROOT / "data" / "eval" / "query_splits.json"
    split_path.parent.mkdir(parents=True, exist_ok=True)
    split_path.write_text(
        json.dumps(split_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "Generated "
        f"{len(candidates)} candidates, {len(jobs)} jobs, {len(labels)} labels, "
        f"and {len(preferences)} pairwise preferences."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
