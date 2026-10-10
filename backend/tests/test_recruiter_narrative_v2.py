from __future__ import annotations

from copy import deepcopy

import pytest

from test_recruiter_narrative_presentation import _source


def _case():
    from app.services.explanation.presentation.facts_v2 import build_atomic_facts
    from app.services.explanation.presentation.adapter import build_narrative_projection
    from app.services.explanation.presentation.contracts_v2 import RecruiterNarrativeV2

    bundle, source, *_ = _source()
    facts = build_atomic_facts(build_narrative_projection(bundle=bundle, source=source))
    skill = next(f for f in facts if f.kind == "candidate_skill" and f.term.casefold() == "python")
    project = next(f for f in facts if f.kind == "project_practice" and f.term.casefold() == "python")
    aligned = next(f for f in facts if f.kind == "requirement_alignment" and f.term.casefold() == "python")
    payload = {
        "contract_version": "recruiter_narrative_v2",
        "candidate_id": source.candidate_id,
        "result_rank": source.result_rank,
        "decision_summary": {"text": "这位候选人的 Python 项目实践与岗位需求直接相关，建议优先安排技术复核。", "fact_ids": [project.fact_id, aligned.fact_id]},
        "why_review": {"text": "资料显示 Python 项目实践；岗位也明确要求 Python，值得在下一轮了解实际设计过程。", "fact_ids": [project.fact_id, aligned.fact_id]},
        "strengths": [{"title": "Python 项目实践", "explanation": "候选人在项目中使用 Python，可进一步了解具体实现职责。", "fact_ids": [project.fact_id, skill.fact_id]}],
        "concerns": [],
        "interview_focus": [{"topic": "Python 项目深度", "question": "请介绍 Python 项目的架构选择与本人负责范围？", "reason": "目前资料记录了项目技术，实际职责仍需面试确认。", "fact_ids": [project.fact_id]}],
    }
    return bundle, source, facts, RecruiterNarrativeV2, payload


def test_v2_accepts_natural_recruiting_language_without_approved_copy():
    from app.services.explanation.presentation.validator_v2 import validate_narrative_v2

    bundle, source, facts, contract, payload = _case()
    before = deepcopy(bundle.model_dump(mode="json"))
    validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)
    assert bundle.model_dump(mode="json") == before


def test_v2_projection_validation_keeps_synthetic_live_probe_source_bounded():
    from app.services.explanation.presentation.adapter import build_narrative_projection
    from app.services.explanation.presentation.validator_v2 import validate_narrative_v2_projection

    bundle, source, facts, contract, payload = _case()
    projection = build_narrative_projection(bundle=bundle, source=source)
    validate_narrative_v2_projection(contract.model_validate(payload), projection=projection)


@pytest.mark.parametrize("claim", [
    "候选人熟悉 Kubernetes 和 Python。",
    "候选人主导 Python 平台研发。",
    "候选人负责百万用户规模的 Python 平台。",
    "候选人利用 Python 提升准确率 50%。",
    "候选人已经证明完全适合该岗位，建议录用。",
    "候选人拥有企业级 AI 平台经验，并使用 Python。",
    "候选人使用 Python 构建后端服务。",
    "候选人使用 Python 完成部署。",
    "候选人掌握 Python，具备扎实的编程语言基础。",
    "候选人的 Python 能力已经足以支撑岗位业务需求。",
    "候选人具备构建 Python 后端服务的相关技术实践。",
], ids=["invented_skill", "invented_responsibility", "invented_scale", "invented_impact", "hiring_decision", "unsupported_inference", "invented_build_action", "invented_deployment_action", "unsupported_depth", "unsupported_fitness", "invented_build_capability"])
def test_v2_rejects_unsupported_claim_even_with_valid_fact_id(claim):
    from app.services.explanation.presentation.validator_v2 import NarrativeV2ValidationError, validate_narrative_v2

    bundle, source, facts, contract, payload = _case()
    payload["strengths"][0]["explanation"] = claim
    with pytest.raises(NarrativeV2ValidationError):
        validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_rejects_other_candidate_fact_and_source_less_claim():
    from app.services.explanation.presentation.validator_v2 import NarrativeV2ValidationError, validate_narrative_v2

    bundle, source, facts, contract, payload = _case()
    payload["strengths"][0]["fact_ids"] = ["fact:" + "a" * 32]
    with pytest.raises(NarrativeV2ValidationError):
        validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)
    payload["strengths"][0]["fact_ids"] = []
    with pytest.raises(Exception):
        validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_prompt_has_no_approved_copy_and_is_versioned():
    from app.services.explanation.presentation.prompt_v2 import build_narrative_v2_request, load_narrative_v2_prompt

    _, _, facts, _, _ = _case()
    prompt = load_narrative_v2_prompt()
    request = build_narrative_v2_request(facts, candidate_id="candidate_001", result_rank=1, role_title="AI Engineer", max_output_tokens=2048)
    assert prompt.version == "recruiter_narrative_prompt_v2"
    assert len(prompt.fingerprint) == 64
    assert request.output_contract_version == "recruiter_narrative_v2"
    assert "approved_copy" not in request.user_instruction
    assert "raw_resume" not in request.user_instruction
    assert "allowed_inference" in request.user_instruction
    assert "required_fact_kinds" in request.user_instruction
    assert "term_to_fact_ids" in request.user_instruction
    assert "requirement_alignment" in request.user_instruction
    assert '"role_title":"AI Engineer"' in request.user_instruction
    import json
    payload = json.loads(request.user_instruction)
    focus = payload["why_review_focus"]
    assert focus["term"].casefold() == "python"
    assert focus["candidate_fact_id"] in {fact.fact_id for fact in facts if fact.kind in {"candidate_skill", "project_practice"}}
    assert focus["alignment_fact_id"] in {fact.fact_id for fact in facts if fact.kind == "requirement_alignment"}
    assert "why_review_focus" in request.system_instruction


def test_v2_accepts_direct_interview_question_without_fixed_phrase():
    from app.services.explanation.presentation.validator_v2 import validate_narrative_v2

    bundle, source, facts, contract, payload = _case()
    payload["interview_focus"][0]["question"] = "Python 项目里如何选择架构并界定职责？"
    payload["interview_focus"][0]["reason"] = "资料包含 Python 项目记录。"
    validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_allows_generic_project_label_but_not_unrecorded_technology():
    from app.services.explanation.presentation.validator_v2 import validate_narrative_v2

    bundle, source, facts, contract, payload = _case()
    payload["strengths"][0]["title"] = "Python Project 实践"
    validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_can_name_verified_job_role_as_context_not_candidate_history():
    from app.services.explanation.presentation.validator_v2 import validate_narrative_v2

    bundle, source, facts, contract, payload = _case()
    payload["decision_summary"]["text"] = "对于 AI Engineer 岗位，候选人的 Python 项目实践值得进一步技术复核。"
    validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_allows_cautious_question_about_ownership_scope_not_asserted_ownership():
    from app.services.explanation.presentation.validator_v2 import validate_narrative_v2

    bundle, source, facts, contract, payload = _case()
    project = next(f for f in facts if f.kind == "project_practice" and f.term.casefold() == "python")
    payload["concerns"] = [{
        "title": "Python 项目职责待核实",
        "explanation": "候选人负责范围仍需面试确认，现有资料只记录了 Python 项目技术。",
        "validation_question": "请说明 Python 项目中的个人职责范围。",
        "fact_ids": [project.fact_id],
    }]
    validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_allows_unknown_project_scope_and_scale_as_questions_only():
    from app.services.explanation.presentation.validator_v2 import validate_narrative_v2

    bundle, source, facts, contract, payload = _case()
    project = next(f for f in facts if f.kind == "project_practice" and f.term.casefold() == "python")
    payload["concerns"] = [{
        "title": "Python 项目范围待核实",
        "explanation": "候选人在 Python 项目中负责的具体模块仍需确认。",
        "validation_question": "请说明是否有大规模 Python 服务经验，以及个人实际职责。",
        "fact_ids": [project.fact_id],
    }]
    validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_rejects_asserted_ownership_even_if_followed_by_cautious_words():
    from app.services.explanation.presentation.validator_v2 import NarrativeV2ValidationError, validate_narrative_v2

    bundle, source, facts, contract, payload = _case()
    project = next(f for f in facts if f.kind == "project_practice" and f.term.casefold() == "python")
    payload["concerns"] = [{
        "title": "Python 项目范围待核实",
        "explanation": "候选人在 Python 项目中负责了核心模块，仍需确认规模。",
        "validation_question": "请说明 Python 项目个人职责。",
        "fact_ids": [project.fact_id],
    }]
    with pytest.raises(NarrativeV2ValidationError):
        validate_narrative_v2(contract.model_validate(payload), facts=facts, bundle=bundle, source=source)
