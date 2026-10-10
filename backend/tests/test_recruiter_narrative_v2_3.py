from __future__ import annotations

from copy import deepcopy
import json

import pytest

from narrative_v2_comparison_fixture import build_comparison_group


def _case():
    case = build_comparison_group(1)
    projection = case["projections"][0]
    from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2

    package = build_evidence_package_v2_2(projection)
    alignment = next(f for f in package.requirement_alignment if f.term.casefold() == "rag")
    scope = next(f for f in package.technical_scope if "rag" in f.terms)
    question = next(f for f in package.interview_verification if "rag" in f.terms)
    payload = {
        "contract_version": "recruiter_narrative_v2_3",
        "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "decision_summary": {
            "decision": "prioritize_review",
            "rationale": [{
                "statement": "项目材料覆盖 RAG 与 FastAPI，与岗位中的 RAG 要求直接相关，值得安排技术复核。",
                "supporting_facts": [alignment.fact_id, scope.fact_id],
                "verification_focus": "面试请确认 RAG 检索与 FastAPI 服务接口之间的具体设计取舍。",
            }],
        },
    }
    return case, projection, package, payload


def test_v2_3_action_contract_and_prompt_reuse_only_v2_2_facts():
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.prompt_v2_3 import build_narrative_v2_3_request

    _, projection, package, payload = _case()
    assert RecruiterNarrativeV2_3.model_validate(payload).decision_summary.decision == "prioritize_review"
    request = build_narrative_v2_3_request(package, projection=projection, max_output_tokens=2048)
    assert request.output_contract_version == "recruiter_narrative_v2_3"
    data = json.loads(request.user_instruction)
    assert data["candidate_evidence_package"]["technical_scope"]
    assert "approved_copy" not in request.user_instruction
    assert "decision_summary" in request.system_instruction


def test_v2_3_repair_is_bounded_to_failed_sections():
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.prompt_v2_3 import (
        build_narrative_v2_3_repair_request, build_narrative_v2_3_request,
    )

    _, projection, package, payload = _case()
    original = build_narrative_v2_3_request(package, projection=projection, max_output_tokens=2048)
    narrative = RecruiterNarrativeV2_3.model_validate(payload)
    summary = {"category": "claim_validation_failed", "invalid_sections": ["decision_summary.rationale[0]"]}
    repair = build_narrative_v2_3_repair_request(original, narrative, summary)
    assert repair.output_contract_version == original.output_contract_version
    assert repair.max_output_tokens == original.max_output_tokens
    assert json.loads(repair.user_instruction)["validation_error_summary"] == summary
    with pytest.raises(ValueError):
        build_narrative_v2_3_repair_request(original, narrative, {"category": "other", "invalid_sections": []})


def test_v2_3_prompt_distinguishes_interview_questions_from_personal_work_claims():
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.prompt_v2_3 import (
        build_narrative_v2_3_repair_request, build_narrative_v2_3_request,
    )

    _, projection, package, payload = _case()
    original = build_narrative_v2_3_request(package, projection=projection, max_output_tokens=2048)
    assert "疑问句" in original.system_instruction
    assert "个人职责" in original.system_instruction
    assert "只写一条" in original.system_instruction
    repair = build_narrative_v2_3_repair_request(
        original, RecruiterNarrativeV2_3.model_validate(payload),
        {"category": "claim_validation_failed", "invalid_sections": ["decision_summary.rationale[0]"]},
    )
    assert "完整 JSON 对象" in repair.system_instruction
    assert "不要输出 Markdown" in repair.system_instruction


def test_v2_3_hiring_action_is_grounded_and_ranking_is_untouched():
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.validator_v2_3 import validate_narrative_v2_3_projection

    case, projection, _, payload = _case()
    before = deepcopy(case["ranking_before"])
    validate_narrative_v2_3_projection(RecruiterNarrativeV2_3.model_validate(payload), projection=projection)
    assert case["ranking_before"] == before
    assert case["run"].result_fingerprint == before["fingerprint"]
    assert [item.candidate_id for item in case["run"].results] == before["order"]
    assert [item.ltr_score_raw for item in case["run"].results] == before["ltr_scores"]


@pytest.mark.parametrize("claim", [
    "候选人技术视野突出，值得进一步关注。",
    "候选人技术能力较强，综合能力突出。",
    "候选人匹配度较高，有较好基础。",
    "候选人熟悉 Kubernetes，并已负责企业级 RAG 平台。",
    "候选人将 RAG 效率提升了 50%。",
    "另一位候选人完成了 RAG 项目。",
])
def test_v2_3_rejects_abstract_or_unsupported_hiring_claim(claim):
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.validator_v2_3 import (
        NarrativeV2_3ValidationError, validate_narrative_v2_3_projection,
    )

    _, projection, _, payload = _case()
    payload["decision_summary"]["rationale"][0]["statement"] = claim
    with pytest.raises(NarrativeV2_3ValidationError):
        validate_narrative_v2_3_projection(RecruiterNarrativeV2_3.model_validate(payload), projection=projection)


def test_v2_3_rejects_priority_when_only_generic_python_alignment_exists():
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
    from app.services.explanation.presentation.validator_v2_3 import (
        NarrativeV2_3ValidationError, validate_narrative_v2_3_projection,
    )

    projection = build_comparison_group(1)["projections"][1]
    package = build_evidence_package_v2_2(projection)
    alignment = next(f for f in package.requirement_alignment if f.term.casefold() == "python")
    practice = package.project_practice[0]
    payload = {
        "contract_version": "recruiter_narrative_v2_3", "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "decision_summary": {"decision": "prioritize_review", "rationale": [{
            "statement": "项目材料覆盖 Python 和 LambdaMART，与岗位中的 Python 要求相关。",
            "supporting_facts": [alignment.fact_id, practice.fact_id],
            "verification_focus": "面试请确认 LambdaMART 排序项目与该岗位的具体关联。",
        }]},
    }
    narrative = RecruiterNarrativeV2_3.model_validate(payload)
    with pytest.raises(NarrativeV2_3ValidationError):
        validate_narrative_v2_3_projection(narrative, projection=projection)
    payload["decision_summary"]["decision"] = "needs_verification"
    validate_narrative_v2_3_projection(RecruiterNarrativeV2_3.model_validate(payload), projection=projection)


def test_v2_3_rejects_foreign_fact_and_generic_interview_question():
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.validator_v2_3 import (
        NarrativeV2_3ValidationError, validate_narrative_v2_3_projection,
    )

    _, projection, _, payload = _case()
    payload["decision_summary"]["rationale"][0]["supporting_facts"][0] = "fact:" + "a" * 32
    with pytest.raises(NarrativeV2_3ValidationError):
        validate_narrative_v2_3_projection(RecruiterNarrativeV2_3.model_validate(payload), projection=projection)
    _, projection, _, payload = _case()
    payload["decision_summary"]["rationale"][0]["verification_focus"] = "建议进一步验证候选人能力。"
    with pytest.raises(NarrativeV2_3ValidationError):
        validate_narrative_v2_3_projection(RecruiterNarrativeV2_3.model_validate(payload), projection=projection)


@pytest.mark.parametrize("claim", [
    "候选人熟悉 Kubernetes，并具备 RAG 项目经验。",
    "候选人曾负责 RAG 系统的设计与交付。",
    "候选人负责百万用户规模的 RAG 系统。",
    "候选人将 RAG 检索效率提升了 50%。",
    "候选人基于 RAG 构建企业级平台。",
])
def test_v2_3_rejects_each_unsupported_claim_class_independently(claim):
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.validator_v2_3 import (
        NarrativeV2_3ValidationError, validate_narrative_v2_3_projection,
    )

    _, projection, _, payload = _case()
    payload["decision_summary"]["rationale"][0]["statement"] = claim
    with pytest.raises(NarrativeV2_3ValidationError):
        validate_narrative_v2_3_projection(RecruiterNarrativeV2_3.model_validate(payload), projection=projection)


def test_v2_3_rejects_existing_fact_from_another_candidate():
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
    from app.services.explanation.presentation.validator_v2_3 import (
        NarrativeV2_3ValidationError, validate_narrative_v2_3_projection,
    )

    case, projection, _, payload = _case()
    foreign = build_evidence_package_v2_2(case["projections"][1]).project_practice[0]
    payload["decision_summary"]["rationale"][0]["supporting_facts"][1] = foreign.fact_id
    with pytest.raises(NarrativeV2_3ValidationError):
        validate_narrative_v2_3_projection(RecruiterNarrativeV2_3.model_validate(payload), projection=projection)


def test_v2_3_allows_concrete_recruiter_interview_question_without_new_facts():
    from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
    from app.services.explanation.presentation.validator_v2_3 import validate_narrative_v2_3_projection

    _, projection, _, payload = _case()
    payload["decision_summary"]["rationale"][0]["verification_focus"] = (
        "面试请询问 RAG 检索策略、召回质量衡量方式及 FastAPI 接口边界的取舍。"
    )
    validate_narrative_v2_3_projection(RecruiterNarrativeV2_3.model_validate(payload), projection=projection)
