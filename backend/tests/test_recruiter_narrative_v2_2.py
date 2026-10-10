from __future__ import annotations

from copy import deepcopy
import json

import pytest

from narrative_v2_comparison_fixture import build_comparison_group


def _case():
    case = build_comparison_group(1)
    return case, case["projections"][0]


def test_v2_2_enriches_project_scope_without_inventing_personal_work():
    from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2

    _, projection = _case()
    package = build_evidence_package_v2_2(projection)
    assert package.project_practice
    assert package.technical_scope
    assert package.requirement_alignment
    assert package.interview_verification
    assert any({"rag", "fastapi"} <= set(item.terms) for item in package.project_practice)
    assert all(item.evidence_refs <= projection.positive_refs for item in package.project_practice)
    assert all("负责" not in item.allowed_inference and "上线" not in item.allowed_inference
               for item in package.technical_scope)


def test_v2_2_does_not_merge_unrelated_project_refs_or_foreign_candidate():
    from dataclasses import replace
    from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2

    _, projection = _case()
    own_project = next(ref for ref in projection.facts if ":project:" in ref)
    split = replace(projection, facts={**projection.facts, own_project: ("RAG",),
                                       "candidate:2:project:other": ("FastAPI",)},
                    positive_refs=projection.positive_refs | {"candidate:2:project:other"})
    package = build_evidence_package_v2_2(split)
    assert all("candidate:2:project:other" not in item.evidence_refs for item in package.project_practice)
    assert not any({"rag", "fastapi"} <= set(item.terms) for item in package.project_practice)


def test_v2_2_prompt_sends_structured_evidence_not_approved_copy():
    from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
    from app.services.explanation.presentation.prompt_v2_2 import build_narrative_v2_2_request

    _, projection = _case()
    package = build_evidence_package_v2_2(projection)
    request = build_narrative_v2_2_request(package, projection=projection, max_output_tokens=2048)
    payload = json.loads(request.user_instruction)
    assert set(payload["candidate_evidence_package"]) == {
        "skills", "project_practice", "technical_scope", "requirement_alignment", "uncertainties",
        "interview_verification",
    }
    assert "approved_copy" not in request.user_instruction
    assert request.output_contract_version == "recruiter_narrative_v2_2"


def test_v2_2_diagnostic_and_repair_are_bounded_without_logging_prose():
    from app.services.explanation.presentation.contracts_v2_2 import RecruiterNarrativeV2_2
    from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
    from app.services.explanation.presentation.prompt_v2_2 import (
        build_narrative_v2_2_repair_request, build_narrative_v2_2_request,
    )
    from app.services.explanation.presentation.validator_v2_2 import validation_error_summary_v2_2

    _, projection = _case()
    package = build_evidence_package_v2_2(projection)
    alignment = package.requirement_alignment[0]
    scope = next(item for item in package.technical_scope if "rag" in item.terms)
    question = next(item for item in package.interview_verification if "rag" in item.terms)
    payload = {
        "contract_version": "recruiter_narrative_v2_2", "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "candidate_snapshot": {"text": "候选人的项目材料覆盖 RAG 与 FastAPI。", "fact_ids": [scope.fact_id]},
        "why_consider": {"text": "RAG 项目范围与岗位需求有关，值得继续了解。", "fact_ids": [alignment.fact_id, scope.fact_id]},
        "key_strengths": [{"title": "RAG 项目范围", "explanation": "项目材料覆盖 Kubernetes 与 RAG。", "fact_ids": [scope.fact_id]}],
        "trade_offs": [],
        "interview_focus": [{"topic": "RAG 检索设计", "question": "请说明 RAG 检索方案如何选择？", "reason": "有助于了解实际设计取舍。", "fact_ids": [question.fact_id]}],
    }
    narrative = RecruiterNarrativeV2_2.model_validate(payload)
    summary = validation_error_summary_v2_2(narrative, projection=projection)
    assert summary["category"] == "claim_validation_failed"
    assert summary["invalid_sections"][0]["section"] == "key_strengths"
    assert summary["invalid_sections"][0]["unsupported_terms"] == ["kubernetes"]
    assert "项目材料" not in str(summary)
    request = build_narrative_v2_2_request(package, projection=projection, max_output_tokens=2048)
    repair = build_narrative_v2_2_repair_request(request, narrative, summary)
    assert repair.output_contract_version == request.output_contract_version
    assert "Kubernetes" not in repair.system_instruction


def test_v2_2_natural_recruiter_claim_is_source_bound_and_ranking_immutable():
    from app.services.explanation.presentation.contracts_v2_2 import RecruiterNarrativeV2_2
    from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
    from app.services.explanation.presentation.validator_v2_2 import validate_narrative_v2_2_projection

    case, projection = _case()
    package = build_evidence_package_v2_2(projection)
    alignment = package.requirement_alignment[0]
    scope = next(item for item in package.technical_scope if "rag" in item.terms)
    question = next(item for item in package.interview_verification if "rag" in item.terms)
    before = deepcopy(case["ranking_before"])
    payload = {
        "contract_version": "recruiter_narrative_v2_2", "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "candidate_snapshot": {"text": "候选人的项目材料覆盖 RAG 与 FastAPI，方向集中在 AI 应用。", "fact_ids": [scope.fact_id]},
        "why_consider": {"text": "RAG 项目范围与岗位需求有关，值得安排下一轮了解具体工作。", "fact_ids": [alignment.fact_id, scope.fact_id]},
        "key_strengths": [{"title": "RAG 项目范围", "explanation": "同一项目材料覆盖 RAG 与 FastAPI，可围绕 AI 应用工程展开讨论。", "fact_ids": [scope.fact_id]}],
        "trade_offs": [],
        "interview_focus": [{"topic": "RAG 检索设计", "question": "请说明 RAG 检索方案如何权衡召回与服务接口？", "reason": "可进一步了解项目中的实际设计取舍。", "fact_ids": [question.fact_id, scope.fact_id]}],
    }
    validate_narrative_v2_2_projection(RecruiterNarrativeV2_2.model_validate(payload), projection=projection)
    assert case["ranking_before"] == before


@pytest.mark.parametrize("unsupported", [
    "候选人熟悉 Kubernetes，并有 RAG 经验。",
    "候选人主导 RAG 平台建设。",
    "候选人负责百万用户 RAG 系统。",
    "候选人将 RAG 召回率提升了 50%。",
    "另一位候选人拥有 RAG 项目。",
])
def test_v2_2_rejects_unverified_skill_responsibility_scale_outcome_or_cross_candidate(unsupported):
    from app.services.explanation.presentation.contracts_v2_2 import RecruiterNarrativeV2_2
    from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
    from app.services.explanation.presentation.validator_v2_2 import NarrativeV2_2ValidationError, validate_narrative_v2_2_projection

    _, projection = _case()
    package = build_evidence_package_v2_2(projection)
    alignment = package.requirement_alignment[0]
    scope = next(item for item in package.technical_scope if "rag" in item.terms)
    question = next(item for item in package.interview_verification if "rag" in item.terms)
    payload = {
        "contract_version": "recruiter_narrative_v2_2", "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "candidate_snapshot": {"text": "候选人的项目材料覆盖 RAG 与 FastAPI。", "fact_ids": [scope.fact_id]},
        "why_consider": {"text": unsupported, "fact_ids": [alignment.fact_id, scope.fact_id]},
        "key_strengths": [{"title": "RAG 项目范围", "explanation": "项目材料覆盖 RAG 与 FastAPI。", "fact_ids": [scope.fact_id]}],
        "trade_offs": [],
        "interview_focus": [{"topic": "RAG 检索设计", "question": "请说明 RAG 检索方案如何选择？", "reason": "有助于了解实际设计取舍。", "fact_ids": [question.fact_id]}],
    }
    with pytest.raises(NarrativeV2_2ValidationError):
        validate_narrative_v2_2_projection(RecruiterNarrativeV2_2.model_validate(payload), projection=projection)
