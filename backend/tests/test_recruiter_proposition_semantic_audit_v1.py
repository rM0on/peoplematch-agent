"""Blind semantic extraction is compared to canonical propositions, not self-citations."""

from __future__ import annotations

import json

from narrative_v2_comparison_fixture import build_comparison_group

from app.services.explanation.presentation.generation_proposition_v1 import ResolvedPropositionNarrativeV1
from app.services.explanation.presentation.propositions_v1 import build_recruiter_propositions_v1
from app.services.explanation.presentation.semantic_audit_proposition_v1 import (
    BlindNarrativeAuditOutputV1, build_blind_semantic_audit_request_v1,
    evaluate_blind_semantic_audit_v1,
)


def _fixture(group=2, candidate_index=0):
    projection = build_comparison_group(group)["projections"][candidate_index]
    propositions = build_recruiter_propositions_v1(projection)
    priority = group == 2 and candidate_index == 0
    texts = {
        "decision_summary": ("建议优先安排人工技术复核。" if priority
                             else "建议安排定向人工技术筛查。"),
        "why_consider": ("项目材料与岗位的排序要求相关。" if priority
                         else "项目材料与岗位的 Python 要求相关。"),
        "technical_signal": ("项目材料列出 LambdaMART 技术。" if priority
                             else "项目材料列出 Python 技术。"),
        "interview_focus": ("下一轮可确认排序项目的实际参与范围。" if priority
                            else "下一轮可确认项目的实际参与范围。"),
        "uncertainty": "当前材料无法确认该项目的具体职责范围。",
    }
    narrative = ResolvedPropositionNarrativeV1.model_validate({
        "contract_version": "recruiter_proposition_generation_v1",
        "candidate_id": projection.candidate_id, "result_rank": projection.result_rank,
        "decision_summary": {"text": texts["decision_summary"],
                             "proposition_refs": ["intentionally-not-a-real-proposition"]},
        **{field: [{"text": texts[field], "proposition_refs": ["also-not-a-real-proposition"]}]
           for field in ("why_consider", "technical_signal", "interview_focus", "uncertainty")},
    })
    labels = {
        "decision_summary": ("human_review_action", [], "priority" if priority else "conditional"),
        "why_consider": ("job_alignment", ["排序"] if priority else ["Python"], "none"),
        "technical_signal": ("project_technology", ["LambdaMART"] if priority else ["Python"], "none"),
        "interview_focus": ("interview_target", ["排序"] if priority else [], "none"),
        "uncertainty": ("material_unknown", [], "none"),
    }
    audit = BlindNarrativeAuditOutputV1.model_validate({
        "contract_version": "blind_narrative_semantics_v1",
        "candidate_id": narrative.candidate_id, "result_rank": narrative.result_rank,
        "paragraphs": [
            {"field": field, "item_index": 0, "atoms": [
                {"quote": texts[field], "category": labels[field][0],
                 "topics": labels[field][1], "review_strength": labels[field][2]},
            ]}
            for field in ("decision_summary", "why_consider", "technical_signal",
                          "interview_focus", "uncertainty")
        ],
    })
    return narrative, propositions, audit


def _replace_atom(audit, field, *, quote=None, category=None, topics=None, strength=None):
    payload = audit.model_dump(mode="json")
    row = next(item for item in payload["paragraphs"] if item["field"] == field)
    atom = row["atoms"][0]
    if quote is not None:
        atom["quote"] = quote
    if category is not None:
        atom["category"] = category
    if topics is not None:
        atom["topics"] = topics
    if strength is not None:
        atom["review_strength"] = strength
    return BlindNarrativeAuditOutputV1.model_validate(payload)


def test_blind_audit_request_contains_only_prose_not_model_selected_references():
    narrative, _, _ = _fixture()
    request = build_blind_semantic_audit_request_v1(narrative, max_output_tokens=2048)
    payload = json.loads(request.user_instruction)
    assert request.response_schema is not None
    assert request.response_schema["title"] == "BlindNarrativeAuditOutputV1"
    assert "$defs" not in request.response_schema
    assert len(payload["paragraphs"]) == 5
    assert "proposition" not in request.user_instruction.casefold()
    assert "handle" not in request.user_instruction.casefold()
    assert "claim_ref" not in request.user_instruction.casefold()


def test_safe_atoms_pass_even_when_model_selected_references_are_fabricated():
    narrative, propositions, audit = _fixture()
    result = evaluate_blind_semantic_audit_v1(audit, narrative=narrative, propositions=propositions)
    assert result.passed
    assert result.issues == ()


def test_blind_semantic_support_is_not_limited_by_legacy_output_field_roles():
    narrative, propositions, audit = _fixture()
    text = "项目材料列出 LambdaMART 技术。建议优先安排人工技术复核。"
    narrative = narrative.model_copy(update={"decision_summary":
        narrative.decision_summary.model_copy(update={"text": text})})
    payload = audit.model_dump(mode="json")
    row = next(item for item in payload["paragraphs"] if item["field"] == "decision_summary")
    row["atoms"] = [
        {"quote": "项目材料列出 LambdaMART 技术。", "category": "project_technology",
         "topics": ["LambdaMART"], "review_strength": "none"},
        {"quote": "建议优先安排人工技术复核。", "category": "human_review_action",
         "topics": [], "review_strength": "priority"},
    ]
    audit = BlindNarrativeAuditOutputV1.model_validate(payload)
    assert evaluate_blind_semantic_audit_v1(
        audit, narrative=narrative, propositions=propositions).passed


def test_personal_docker_deployment_is_not_project_technology_observation():
    narrative, propositions, audit = _fixture()
    text = "候选人在过往项目中使用 Docker 进行容器化部署。"
    narrative = narrative.model_copy(update={"technical_signal": [
        narrative.technical_signal[0].model_copy(update={"text": text})]})
    audit = _replace_atom(audit, "technical_signal", quote=text,
                          category="candidate_action_or_responsibility", topics=["Docker"])
    result = evaluate_blind_semantic_audit_v1(audit, narrative=narrative, propositions=propositions)
    assert "UNSUPPORTED_SEMANTIC_CATEGORY" in {item.code for item in result.issues}


def test_technical_topics_cannot_be_promoted_into_unrelated_job_alignment():
    narrative, propositions, audit = _fixture(group=1, candidate_index=1)
    text = "评估、排序和检索项目与 AI Agent 岗位要求直接相关。"
    narrative = narrative.model_copy(update={"why_consider": [
        narrative.why_consider[0].model_copy(update={"text": text})]})
    audit = _replace_atom(audit, "why_consider", quote=text,
                          topics=["评估", "排序", "检索"])
    result = evaluate_blind_semantic_audit_v1(audit, narrative=narrative, propositions=propositions)
    assert "TOPIC_OUTSIDE_PROPOSITION_SCOPE" in {item.code for item in result.issues}


def test_strong_or_complete_job_match_is_not_ordinary_alignment():
    narrative, propositions, audit = _fixture()
    text = "该项目方向与岗位中的排序要求高度匹配。"
    narrative = narrative.model_copy(update={"why_consider": [
        narrative.why_consider[0].model_copy(update={"text": text})]})
    payload = audit.model_dump(mode="json")
    row = next(item for item in payload["paragraphs"] if item["field"] == "why_consider")
    row["atoms"] = [{"quote": text, "category": "strong_alignment",
                     "topics": ["排序"], "review_strength": "none"}]
    parsed = BlindNarrativeAuditOutputV1.model_validate(payload)
    result = evaluate_blind_semantic_audit_v1(parsed, narrative=narrative, propositions=propositions)
    assert "UNSUPPORTED_SEMANTIC_CATEGORY" in {item.code for item in result.issues}


def test_priority_review_cannot_be_backed_by_conditional_review_proposition():
    narrative, propositions, audit = _fixture(group=1, candidate_index=1)
    text = "建议优先安排人工技术复核。"
    narrative = narrative.model_copy(update={"decision_summary":
        narrative.decision_summary.model_copy(update={"text": text})})
    audit = _replace_atom(audit, "decision_summary", quote=text, strength="priority")
    result = evaluate_blind_semantic_audit_v1(audit, narrative=narrative, propositions=propositions)
    assert "REVIEW_STRENGTH_EXCEEDS_SUPPORT" in {item.code for item in result.issues}


def test_incomplete_extraction_or_foreign_candidate_fails_closed():
    narrative, propositions, audit = _fixture()
    extended = narrative.model_copy(update={"technical_signal": [
        narrative.technical_signal[0].model_copy(update={
            "text": narrative.technical_signal[0].text + "候选人负责生产部署。",
        })]})
    result = evaluate_blind_semantic_audit_v1(audit, narrative=extended, propositions=propositions)
    assert "UNEXTRACTED_SEMANTIC_TEXT" in {item.code for item in result.issues}
    foreign = audit.model_copy(update={"candidate_id": "foreign-candidate"})
    result = evaluate_blind_semantic_audit_v1(foreign, narrative=narrative, propositions=propositions)
    assert "CANDIDATE_IDENTITY_MISMATCH" in {item.code for item in result.issues}


def test_quote_and_topic_must_actually_appear_in_the_body():
    narrative, propositions, audit = _fixture()
    wrong_quote = _replace_atom(audit, "technical_signal", quote="不存在于正文的句子。")
    result = evaluate_blind_semantic_audit_v1(wrong_quote, narrative=narrative, propositions=propositions)
    assert "QUOTE_NOT_IN_PARAGRAPH" in {item.code for item in result.issues}
    invented_topic = _replace_atom(audit, "technical_signal", topics=["Qdrant"])
    result = evaluate_blind_semantic_audit_v1(invented_topic, narrative=narrative, propositions=propositions)
    assert "TOPIC_NOT_IN_QUOTE" in {item.code for item in result.issues}
