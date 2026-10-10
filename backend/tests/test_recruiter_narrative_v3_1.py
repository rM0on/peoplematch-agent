"""V3.1 hiring-language semantics over the unchanged V3 atomic fact graph."""

from __future__ import annotations

import pytest

from app.services.explanation.presentation.adapter import NarrativeProjection
from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3


def _case(technology: str, role: str) -> tuple[NarrativeProjection, object]:
    projection = NarrativeProjection(
        candidate_id=f"synthetic-{technology.lower()}", result_rank=1, role_title=role,
        facts={"candidate:1:project:sample": (f"{technology} project practice",),
               "job_requirement:direction": (technology,)},
        verification_status={},
        positive_refs=frozenset({"candidate:1:project:sample", "job_requirement:direction"}),
        risk_refs=frozenset(), interview_refs=frozenset(),
    )
    return projection, build_atomic_fact_graph_v3(projection)


def _narrative(projection, graph):
    from app.services.explanation.presentation.contracts_v3_1 import RecruiterNarrativeV3_1

    project = next(f for f in graph.facts if f.kind == "project_evidence")
    alignment = next(f for f in graph.facts if f.kind == "job_alignment")
    interview = next(f for f in graph.facts if f.kind == "interview_validation")
    return RecruiterNarrativeV3_1.model_validate({
        "contract_version": "recruiter_narrative_v3_1",
        "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "decision": "prioritize_review",
        "decision_summary": {
            "text": "基于候选材料与岗位技术方向的关联，建议进行下一轮人工复核。",
            "claim_type": "review_recommendation", "fact_ids": [alignment.fact_id, project.fact_id],
        },
        "strengths": [{"text": f"候选材料包含 {project.concepts[0]} 相关项目实践。",
                       "claim_type": "evidence_summary", "fact_ids": [project.fact_id]},
                      {"text": f"材料中的 {project.concepts[0]} 实践与岗位方向存在关联。",
                       "claim_type": "job_alignment_observation",
                       "fact_ids": [alignment.fact_id, project.fact_id]}],
        "risks": [{"text": f"仍需确认候选人在 {project.concepts[0]} 项目中的实际参与范围。",
                   "claim_type": "interview_validation", "fact_ids": [interview.fact_id]}],
        "interview_focus": [{"text": f"下一轮确认 {project.concepts[0]} 方案设计中的参与范围。",
                             "claim_type": "interview_validation", "fact_ids": [interview.fact_id]}],
    })


def _changed(narrative, section: str, text: str):
    if section == "strengths":
        return narrative.model_copy(update={"strengths": [narrative.strengths[0].model_copy(
            update={"text": text}), *narrative.strengths[1:]]})
    return narrative.model_copy(update={section: [narrative.interview_focus[0].model_copy(
        update={"text": text})]})


@pytest.mark.parametrize("technology,role,section,text,accepted", [
    ("RAG", "AI Agent Engineer", "strengths", "候选人负责企业 RAG 平台建设。", False),
    ("RAG", "AI Agent Engineer", "interview_focus", "下一轮确认候选人在 RAG 架构设计中的参与范围。", True),
    ("LambdaMART", "Recommendation Engineer", "strengths", "候选人具备推荐系统专家能力。", False),
    ("LambdaMART", "Recommendation Engineer", "interview_focus", "面试确认 LambdaMART 排序特征设计和评估方法。", True),
])
def test_v3_1_claim_semantics(technology, role, section, text, accepted):
    from app.services.explanation.presentation.validator_v3_1 import (
        invalid_narrative_v3_1_sections,
    )

    projection, graph = _case(technology, role)
    narrative = _changed(_narrative(projection, graph), section, text)
    invalid = invalid_narrative_v3_1_sections(narrative, projection=projection)
    assert (not invalid) is accepted, invalid


def test_v3_1_prompt_has_independent_contract_and_no_approved_copy():
    from app.services.explanation.presentation.prompt_v3_1 import (
        build_narrative_v3_1_request, load_narrative_v3_1_prompt,
    )

    projection, graph = _case("RAG", "AI Agent Engineer")
    artifact = load_narrative_v3_1_prompt()
    request = build_narrative_v3_1_request(graph, projection=projection, max_output_tokens=2048)
    assert artifact.version == "recruiter_narrative_prompt_v3_1"
    assert request.output_contract_version == "recruiter_narrative_v3_1"
    assert "approved_copy" not in request.user_instruction
    assert "job_alignment fact_id" in request.system_instruction
    assert "岗位关联观察的主语" in request.system_instruction


def test_v3_1_risk_can_state_unresolved_scope_without_a_question():
    from app.services.explanation.presentation.validator_v3_1 import (
        invalid_narrative_v3_1_sections,
    )

    projection, graph = _case("RAG", "AI Agent Engineer")
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"risks": [narrative.risks[0].model_copy(
        update={"text": "RAG 项目的实际参与范围尚待说明。"})]})
    assert not invalid_narrative_v3_1_sections(changed, projection=projection)
