from __future__ import annotations

from copy import deepcopy

import pytest

from app.schemas.explanations import CandidateExplanationOutput
from app.services.explanation.evidence import EvidenceBundleBuilder
from test_explanation_evidence_engine import _run, _refresh_candidate_snapshot_fingerprint, _refresh_result_fingerprint


def _source():
    bundle = EvidenceBundleBuilder().build(_run())
    candidate = bundle.candidates[0]
    skill = candidate.skills[0].evidence_id
    project = candidate.projects[0].evidence_id
    requirement = next(
        item.evidence_id for item in bundle.job.requirements
        if item.requirement_id == "req_python"
    )
    output = CandidateExplanationOutput.model_validate(
        {
            "output_schema_version": "explanation_output_v1",
            "candidate_id": candidate.candidate_id,
            "result_rank": candidate.result_rank,
            "summary": {"text": "Recorded matching evidence is available.", "evidence_refs": [skill]},
            "match_reasons": [
                {"category": "skill_alignment", "text": "Recorded skill evidence is available.", "evidence_refs": [requirement, skill]},
                {"category": "project_evidence", "text": "Recorded project evidence is available.", "evidence_refs": [project]},
            ],
            "risk_points": [],
            "missing_skills": [],
            "interview_questions": [],
            "why_not_top1": None,
            "profile_rewrite_suggestion": None,
        }
    )
    return bundle, output, skill, project, requirement


def _narrative(skill: str, project: str, requirement: str) -> dict:
    return {
        "contract_version": "recruiter_narrative_v1",
        "candidate_id": "candidate_001",
        "result_rank": 1,
        "candidate_summary": {
            "text": "候选人有 Python 项目实践。", "evidence_links": sorted([skill, project])
        },
        "recommendation_summary": {
            "text": "Python 与岗位要求有关，建议进一步技术复核。",
            "evidence_links": sorted([skill, requirement]),
        },
        "strengths": [
            {"text": "项目记录涉及 Python。", "evidence_links": [project]}
        ],
        "risks": [],
        "interview_focus": [
            {"text": "建议面试确认 Python 项目设计过程。", "evidence_links": [project]}
        ],
        "evidence_links": sorted([skill, project, requirement]),
    }


def test_narrative_is_independent_and_cited_to_validated_history():
    from app.services.explanation.presentation.contracts import RecruiterNarrativeV1
    from app.services.explanation.presentation.validator import validate_recruiter_narrative

    bundle, output, skill, project, requirement = _source()
    before = deepcopy(output.model_dump(mode="json"))
    narrative = RecruiterNarrativeV1.model_validate(_narrative(skill, project, requirement))

    validate_recruiter_narrative(narrative, bundle=bundle, source=output)

    assert output.model_dump(mode="json") == before
    assert bundle.source.match_run_id == "run_001"


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value["strengths"][0].update(text="熟悉 Kubernetes 和 Python。"),
        lambda value: value["strengths"][0].update(text="服务百万用户，使用 Python。"),
        lambda value: value["strengths"][0].update(text="使用 Python 提升效率 50%。"),
        lambda value: value["strengths"][0].update(text="候选人缺少 Python 能力。"),
        lambda value: value["strengths"][0].update(text="曾担任高级专家，使用 Python。"),
        lambda value: value["strengths"][0].update(text="项目记录涉及 Python，曾获得国家级科研大奖。"),
        lambda value: value["strengths"][0].update(text="候选人曾负责百万用户系统，并使用 Python。"),
        lambda value: value["strengths"][0].update(text="候选人具备 Kubernetes 生产经验，并使用 Python。"),
        lambda value: value["strengths"][0].update(text="候选人曾负责银河检索平台项目，并使用 Python。"),
        lambda value: value["recommendation_summary"].update(text="候选人已经证明适合岗位，具备 Python 能力。"),
        lambda value: value["strengths"][0].update(evidence_links=["candidate:1:skill:" + "a" * 64]),
        lambda value: value["recommendation_summary"].update(text="建议录用，具备 Python 能力。"),
    ],
    ids=["invented_skill", "invented_scale", "invented_metric", "unsupported_gap", "invented_seniority", "unsupported_achievement", "million_user_claim", "unsupported_kubernetes_experience", "invented_project", "unverified_fitness_claim", "unknown_reference", "hiring_decision"],
)
def test_unsupported_narrative_fails_closed(change):
    from app.services.explanation.presentation.contracts import RecruiterNarrativeV1
    from app.services.explanation.presentation.validator import NarrativeValidationError, validate_recruiter_narrative

    bundle, output, skill, project, requirement = _source()
    value = _narrative(skill, project, requirement)
    change(value)
    value["evidence_links"] = sorted({
        ref for item in (
            value["candidate_summary"], value["recommendation_summary"],
            *value["strengths"], *value["risks"], *value["interview_focus"],
        ) for ref in item["evidence_links"]
    })
    narrative = RecruiterNarrativeV1.model_validate(value)

    with pytest.raises(NarrativeValidationError):
        validate_recruiter_narrative(narrative, bundle=bundle, source=output)


def test_no_candidate_evidence_rejects_generation_before_provider():
    from app.services.explanation.presentation.adapter import build_narrative_projection
    from app.services.explanation.presentation.validator import NarrativeValidationError

    bundle, output, *_ = _source()
    output = output.model_copy(
        update={
            "summary": output.summary.model_copy(update={"evidence_refs": [bundle.job.requirements[0].evidence_id]}),
            "match_reasons": [],
        }
    )
    with pytest.raises(NarrativeValidationError):
        build_narrative_projection(bundle=bundle, source=output)


def test_prompt_contains_only_historical_projection_and_versioned_fingerprint():
    from app.services.explanation.presentation.adapter import build_narrative_projection
    from app.services.explanation.presentation.prompt import build_narrative_request, load_narrative_prompt

    bundle, output, *_ = _source()
    projection = build_narrative_projection(bundle=bundle, source=output)
    request = build_narrative_request(projection, max_output_tokens=1024)
    prompt = load_narrative_prompt()

    assert prompt.version == "recruiter_narrative_prompt_v1"
    assert len(prompt.fingerprint) == 64
    assert request.output_contract_version == "recruiter_narrative_v1"
    assert "Python" in request.user_instruction
    assert "raw_resume" not in request.user_instruction
    assert "ranking_input_snapshot" not in request.user_instruction


def test_other_candidate_evidence_cannot_support_this_candidate():
    from app.services.explanation.presentation.contracts import RecruiterNarrativeV1
    from app.services.explanation.presentation.validator import NarrativeValidationError, validate_recruiter_narrative

    bundle, output, skill, project, requirement = _source()
    value = _narrative(skill, project, requirement)
    value["strengths"][0]["evidence_links"] = [bundle.candidates[1].projects[0].evidence_id]
    value["evidence_links"] = sorted({
        ref for item in (value["candidate_summary"], value["recommendation_summary"], *value["strengths"], *value["interview_focus"])
        for ref in item["evidence_links"]
    })
    narrative = RecruiterNarrativeV1.model_validate(value)
    with pytest.raises(NarrativeValidationError):
        validate_recruiter_narrative(narrative, bundle=bundle, source=output)


def test_recommendation_needs_both_candidate_and_job_evidence():
    from app.services.explanation.presentation.contracts import RecruiterNarrativeV1
    from app.services.explanation.presentation.validator import NarrativeValidationError, validate_recruiter_narrative

    bundle, output, skill, project, requirement = _source()
    value = _narrative(skill, project, requirement)
    value["recommendation_summary"]["evidence_links"] = [skill]
    value["evidence_links"] = sorted([skill, project])
    narrative = RecruiterNarrativeV1.model_validate(value)

    with pytest.raises(NarrativeValidationError):
        validate_recruiter_narrative(narrative, bundle=bundle, source=output)


def test_candidate_specific_evidence_yields_distinct_narrative_choices():
    from app.services.explanation.presentation.adapter import build_narrative_projection
    from app.services.explanation.presentation.copy_catalog import approved_copy

    run = _run()
    second = run.results[1].candidate_input_snapshot
    second["skills"] = [{"name": "Go", "category": "backend"}]
    second["projects"][0]["technologies"] = ["Go"]
    second["projects"][0]["skills_demonstrated"] = ["Go"]
    second["project_evidence"][0]["supports_skills"] = ["Go"]
    _refresh_candidate_snapshot_fingerprint(run.results[1])
    _refresh_result_fingerprint(run)
    bundle = EvidenceBundleBuilder().build(run)
    requirement = next(item.evidence_id for item in bundle.job.requirements if item.requirement_id == "req_python")

    def choices(index):
        candidate = bundle.candidates[index]
        skill = candidate.skills[0].evidence_id
        project = candidate.projects[0].evidence_id
        output = CandidateExplanationOutput.model_validate({
            "output_schema_version": "explanation_output_v1",
            "candidate_id": candidate.candidate_id,
            "result_rank": candidate.result_rank,
            "summary": {"text": "Recorded evidence is available.", "evidence_refs": [skill]},
            "match_reasons": [
                {"category": "skill_alignment", "text": "Requirement evidence is available.", "evidence_refs": [requirement, skill]},
                {"category": "project_evidence", "text": "Project evidence is available.", "evidence_refs": [project]},
            ],
            "risk_points": [], "missing_skills": [], "interview_questions": [],
            "why_not_top1": (
                None if index == 0 else {
                    "category": "ranking_comparison",
                    "text": "The Candidate is below the persisted top-ranked result.",
                    "evidence_refs": ["comparison:2:top1:skill_fit_score"],
                }
            ),
            "profile_rewrite_suggestion": None,
        })
        return approved_copy(build_narrative_projection(bundle=bundle, source=output))

    first, second_choices = choices(0), choices(1)
    assert first["strengths"] != second_choices["strengths"]
    assert any("Python" in item.text for item in first["strengths"])
    assert any("go" in item.text.casefold() for item in second_choices["strengths"])


def test_missing_project_evidence_never_becomes_a_positive_narrative_claim():
    from app.services.explanation.presentation.adapter import NarrativeProjection
    from app.services.explanation.presentation.copy_catalog import approved_copy

    skill = "candidate:1:skill:" + "a" * 64
    missing_record = "candidate:1:project_evidence:evidence_001"
    requirement = "job_requirement:req_python"
    projection = NarrativeProjection(
        candidate_id="candidate_001", result_rank=1, role_title="AI Engineer",
        facts={skill: ("Python",), missing_record: ("Kubernetes",), requirement: ("Python",)},
        verification_status={missing_record: "missing"},
        positive_refs=frozenset({skill, missing_record, requirement}),
        risk_refs=frozenset(), interview_refs=frozenset(),
    )
    catalog = approved_copy(projection)
    positive = (
        catalog["candidate_summary"] + catalog["recommendation_summary"] + catalog["strengths"]
    )
    assert all("Kubernetes" not in statement.text for statement in positive)


def test_unrelated_candidate_term_cannot_be_presented_as_requirement_match():
    from app.services.explanation.presentation.adapter import NarrativeProjection
    from app.services.explanation.presentation.copy_catalog import approved_copy

    skill = "candidate:1:skill:" + "a" * 64
    requirement = "job_requirement:req_python"
    projection = NarrativeProjection(
        candidate_id="candidate_001", result_rank=1, role_title="AI Engineer",
        facts={skill: ("AI Agent",), requirement: ("Python",)},
        verification_status={}, positive_refs=frozenset({skill, requirement}),
        risk_refs=frozenset(), interview_refs=frozenset(),
    )
    assert approved_copy(projection)["recommendation_summary"] == []


def test_agent_and_rag_project_can_use_natural_cautious_recruiter_language():
    from app.services.explanation.presentation.adapter import NarrativeProjection
    from app.services.explanation.presentation.copy_catalog import approved_copy

    project = "candidate:1:project:project_001"
    requirement = "job_requirement:req_agent"
    projection = NarrativeProjection(
        candidate_id="candidate_001", result_rank=1, role_title="AI Agent Engineer",
        facts={project: ("ai agent", "rag"), requirement: ("AI Agent",)},
        verification_status={}, positive_refs=frozenset({project, requirement}),
        risk_refs=frozenset(), interview_refs=frozenset({project}),
    )
    candidate_copy = approved_copy(projection)["candidate_summary"]
    assert any(
        item.text == "候选人在 AI Agent 与 RAG 应用方向已有项目实践，可进一步验证系统设计能力。"
        and item.evidence_links == [project]
        for item in candidate_copy
    )


def test_natural_agent_rag_summary_passes_full_narrative_validator_with_project_evidence():
    from app.services.explanation.presentation.adapter import build_narrative_projection
    from app.services.explanation.presentation.contracts import RecruiterNarrativeV1
    from app.services.explanation.presentation.copy_catalog import approved_copy
    from app.services.explanation.presentation.validator import validate_recruiter_narrative

    run = _run()
    first = run.results[0].candidate_input_snapshot
    first["skills"] += [
        {"name": "AI Agent", "category": "llm_application"},
        {"name": "RAG", "category": "llm_application"},
    ]
    first["projects"][0]["technologies"] = ["AI Agent", "RAG"]
    first["projects"][0]["skills_demonstrated"] = ["AI Agent", "RAG"]
    first["project_evidence"][0]["supports_skills"] = ["AI Agent", "RAG"]
    _refresh_candidate_snapshot_fingerprint(run.results[0])
    _refresh_result_fingerprint(run)
    bundle = EvidenceBundleBuilder().build(run)
    candidate = bundle.candidates[0]
    skill = next(item.evidence_id for item in candidate.skills if item.name.casefold() == "python")
    project = candidate.projects[0].evidence_id
    requirement = next(item.evidence_id for item in bundle.job.requirements if item.requirement_id == "req_python")
    output = CandidateExplanationOutput.model_validate({
        "output_schema_version": "explanation_output_v1", "candidate_id": candidate.candidate_id,
        "result_rank": 1,
        "summary": {"text": "Recorded candidate evidence is available.", "evidence_refs": [skill]},
        "match_reasons": [
            {"category": "skill_alignment", "text": "Recorded skill relates to requirement.", "evidence_refs": [skill, requirement]},
            {"category": "project_evidence", "text": "Recorded project has related skills.", "evidence_refs": [project]},
        ],
        "risk_points": [], "missing_skills": [], "interview_questions": [],
        "why_not_top1": None, "profile_rewrite_suggestion": None,
    })
    catalog = approved_copy(build_narrative_projection(bundle=bundle, source=output))
    summary = next(
        item for item in catalog["candidate_summary"]
        if "AI Agent 与 RAG 应用方向" in item.text
    )
    selected = [summary, catalog["recommendation_summary"][0], catalog["strengths"][0]]
    narrative = RecruiterNarrativeV1(
        contract_version="recruiter_narrative_v1", candidate_id=candidate.candidate_id,
        result_rank=1, candidate_summary=selected[0], recommendation_summary=selected[1],
        strengths=[selected[2]], risks=[], interview_focus=[],
        evidence_links=sorted({ref for item in selected for ref in item.evidence_links}),
    )
    validate_recruiter_narrative(narrative, bundle=bundle, source=output)
    assert bundle.source.result_fingerprint == run.result_fingerprint
