"""Exact synthetic V5 prose regressions from the resolved-reference live audit."""

from __future__ import annotations

import pytest

from app.services.explanation.presentation.contracts_v5 import RecruiterNarrativeV5
from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
from app.services.explanation.presentation.service_v5 import diagnose_narrative_v5
from test_recruiter_narrative_v5 import _inputs, _payload


def _diagnose(field: str, text: str, *, open_focus: bool = False,
              project_scope: bool = False) -> dict[str, str]:
    _, graph, frame = _inputs()
    payload = _payload(graph)
    if open_focus:
        claim = next(item for item in graph.claims if item.relation_type == "open_requirement")
        payload[field].append({"text": text, "claim_refs": [claim.claim_id]})
    else:
        payload[field][0]["text"] = text
        if project_scope:
            payload[field][0]["claim_refs"] = [
                item.claim_id for item in graph.claims
                if item.claim_type in {"interview_focus", "project_depth_validation"}
                and item.relation_type == "verify_observed_scope"
            ]
    narrative = RecruiterNarrativeV5.model_validate(payload)
    return diagnose_narrative_v5(
        narrative, graph=graph, frame=frame,
        context=build_hiring_context_v5(graph, frame),
    )


def test_live_hypothetical_ability_does_not_assert_ability():
    failures = _diagnose(
        "technical_signal",
        "候选人的技术背景明确指向 RAG 领域，这是评估其是否具备相关工程实践能力的核心信号。",
    )
    assert "technical_signal[0]" not in failures


def test_live_material_unknown_does_not_require_interview_verb():
    failures = _diagnose(
        "uncertainty",
        "目前材料尚无法确定候选人在 RAG 系统中的具体实施深度及参与边界。",
        project_scope=True,
    )
    assert "uncertainty[0]" not in failures


def test_live_interview_action_tantao_is_not_factual_claim():
    failures = _diagnose(
        "interview_focus",
        "针对岗位开放需求，探讨候选人过往经验中可迁移的技术细节。",
        open_focus=True,
    )
    assert "interview_focus[1]" not in failures


def test_ownership_question_is_not_ownership_assertion():
    failures = _diagnose(
        "interview_focus", "下一轮可确认候选人是否负责过 RAG 架构设计。",
    )
    assert "interview_focus[0]" not in failures


def test_recruiter_assessment_verb_is_not_unlisted_evaluation_technology():
    failures = _diagnose(
        "technical_signal",
        "候选人的 RAG 项目值得评估其是否具备进一步面试的价值。",
    )
    assert "technical_signal[0]" not in failures


def test_unlisted_offline_evaluation_remains_unsupported():
    failures = _diagnose(
        "technical_signal",
        "候选材料包含 RAG 项目与离线评估实践。",
    )
    assert failures.get("technical_signal[0]") == "technical_concept_outside_claim_scope"


def test_discussed_as_candidate_fact_is_not_an_interview_directive():
    failures = _diagnose(
        "interview_focus", "候选人探讨了 RAG 项目技术细节。",
    )
    assert failures.get("interview_focus[0]") == "verification_modality_missing"


def test_hypothetical_ability_cannot_hide_a_following_ability_assertion():
    failures = _diagnose(
        "technical_signal", "候选人是否具备 RAG 能力，且拥有丰富经验。",
    )
    assert failures.get("technical_signal[0]") == "unsupported_ability_conclusion"


@pytest.mark.parametrize(("field", "text"), [
    ("why_consider", "候选人负责 RAG 架构设计。"),
    ("interview_focus", "候选人是否负责过 RAG 架构设计，但候选人主导了该系统。"),
    ("technical_signal", "候选人具备成熟 RAG 工程实践能力。"),
    ("uncertainty", "候选人拥有大规模生产部署经验。"),
    ("uncertainty", "候选人缺少生产部署能力。"),
    ("why_consider", "候选人通过 RAG 将准确率提高 50%。"),
    ("why_consider", "候选人负责 Retrieval 和 RAG 项目。"),
])
def test_factual_upgrade_still_fails(field: str, text: str):
    failures = _diagnose(field, text)
    assert f"{field}[0]" in failures or f"{field}[0].frame" in failures


def test_hiring_decision_overreach_still_fails():
    _, graph, frame = _inputs()
    payload = _payload(graph)
    payload["decision_summary"]["text"] = "建议直接录用，不需要技术面试。"
    failures = diagnose_narrative_v5(
        RecruiterNarrativeV5.model_validate(payload), graph=graph, frame=frame,
        context=build_hiring_context_v5(graph, frame),
    )
    assert "decision_summary" in failures


def _responsibility_diagnostic(field: str, text: str, *, technology: str = "RAG") -> dict[str, str]:
    _, graph, frame = _inputs(technology=technology)
    payload = _payload(graph)
    if technology != "RAG":
        for section in ("why_consider", "technical_signal", "interview_focus"):
            for paragraph in payload[section]:
                paragraph["text"] = paragraph["text"].replace("LambdaMART", technology)
    payload[field][0]["text"] = text
    if field in {"uncertainty", "interview_focus"}:
        payload[field][0]["claim_refs"] = [
            claim.claim_id for claim in graph.claims
            if claim.claim_type in {"interview_focus", "project_depth_validation"}
        ]
    return diagnose_narrative_v5(
        RecruiterNarrativeV5.model_validate(payload), graph=graph, frame=frame,
        context=build_hiring_context_v5(graph, frame),
    )


@pytest.mark.parametrize(("field", "text", "technology"), [
    ("uncertainty", "目前尚不清楚候选人在 RAG 系统中的具体贡献边界，需通过面试确认其是主导设计还是仅参与局部实现。", "RAG"),
    ("uncertainty", "需通过面试确认其是主导设计还是仅参与。", "RAG"),
    ("interview_focus", "下一轮需确认候选人在该项目中是主导方案设计，还是参与具体实现。", "RAG"),
    ("interview_focus", "建议进一步了解候选人在该项目中的职责范围。", "RAG"),
    ("uncertainty", "当前材料尚不能确认其具体负责哪些模块。", "RAG"),
    ("interview_focus", "面试时可确认候选人是否负责过检索链路设计。", "Retrieval"),
    ("uncertainty", "当前无法判断其在该项目中承担的是架构设计还是实现工作。", "RAG"),
    ("interview_focus", "需确认其是否具有主导设计经验。", "RAG"),
])
def test_responsibility_verification_does_not_assert_a_role(field, text, technology):
    failures = _responsibility_diagnostic(field, text, technology=technology)
    assert f"{field}[0]" not in failures
    assert f"{field}[0].frame" not in failures


@pytest.mark.parametrize(("field", "text"), [
    ("uncertainty", "候选人主导了 RAG 系统设计。"),
    ("uncertainty", "候选人负责检索链路设计。"),
    ("uncertainty", "候选人在项目中承担核心架构职责。"),
    ("interview_focus", "候选人参与了生产系统部署。"),
    ("uncertainty", "候选人主导设计，下一轮可以确认具体细节。"),
    ("uncertainty", "候选人负责 RAG 系统，是否达到生产规模仍需确认。"),
    ("interview_focus", "需要确认候选人主导设计的具体范围。"),
    ("uncertainty", "需确认其主导设计经验是否足够深入。"),
    ("interview_focus", "候选人是否负责过 RAG 架构设计，且候选人主导了系统开发。"),
    ("interview_focus", "候选人是否负责过 RAG 项目，但也主导了系统开发。"),
    ("interview_focus", "候选人是否负责过 RAG 项目并主导了系统开发。"),
])
def test_responsibility_assertion_dominates_verification_language(field, text):
    failures = _responsibility_diagnostic(field, text)
    assert failures.get(f"{field}[0]") == "forbidden_responsibility_scale_outcome_or_hiring_decision"


@pytest.mark.parametrize("field", ["why_consider", "technical_signal"])
def test_responsibility_question_does_not_serve_as_positive_signal(field):
    failures = _responsibility_diagnostic(
        field, "下一轮需确认候选人是否负责过 RAG 架构设计。",
    )
    assert failures.get(f"{field}[0]") == "forbidden_responsibility_scale_outcome_or_hiring_decision"
