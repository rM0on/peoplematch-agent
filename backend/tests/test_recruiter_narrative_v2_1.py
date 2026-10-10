from __future__ import annotations

from copy import deepcopy
import asyncio

import pytest

from test_recruiter_narrative_v2 import _case


def _payload():
    from app.services.explanation.presentation.facts_v2 import build_atomic_facts
    from app.services.explanation.presentation.adapter import build_narrative_projection

    bundle, source, *_ = _case()
    projection = build_narrative_projection(bundle=bundle, source=source)
    facts = build_atomic_facts(projection)
    project = next(f for f in facts if f.kind == "project_practice" and f.term.casefold() == "python")
    alignment = next(f for f in facts if f.kind == "requirement_alignment" and f.term.casefold() == "python")
    payload = {
        "contract_version": "recruiter_narrative_v2_1",
        "candidate_id": source.candidate_id,
        "result_rank": source.result_rank,
        "candidate_snapshot": {"text": "这位候选人的项目记录涉及 Python，方向与当前岗位有交集。", "fact_ids": [project.fact_id, alignment.fact_id]},
        "why_consider": {"text": "Python 项目记录与岗位需求直接相关，值得了解其具体工作内容。", "fact_ids": [project.fact_id, alignment.fact_id]},
        "key_strengths": [{"title": "Python 相关项目", "explanation": "项目记录涉及 Python，与岗位关注的技术方向相连。", "fact_ids": [project.fact_id, alignment.fact_id]}],
        "trade_offs": [{"title": "实际职责待了解", "explanation": "当前材料未说明 Python 项目中的个人负责范围。", "validation_question": "请介绍 Python 项目中的实际职责与技术取舍？", "fact_ids": [project.fact_id]}],
        "interview_focus": [{"topic": "Python 工程实践", "question": "Python 项目中如何选择实现方案？", "reason": "这有助于了解项目记录背后的具体实践。", "fact_ids": [project.fact_id]}],
    }
    return bundle, source, projection, facts, payload


def test_v2_1_contract_and_prompt_keep_free_recruiting_prose():
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.prompt_v2_1 import build_narrative_v2_1_request, load_narrative_v2_1_prompt

    _, source, projection, facts, payload = _payload()
    assert RecruiterNarrativeV2_1.model_validate(payload).why_consider.text.startswith("Python")
    prompt = load_narrative_v2_1_prompt()
    request = build_narrative_v2_1_request(
        facts, candidate_id=source.candidate_id, result_rank=source.result_rank,
        role_title=projection.role_title, max_output_tokens=2048,
    )
    assert prompt.version == "recruiter_narrative_prompt_v2_1"
    assert request.output_contract_version == "recruiter_narrative_v2_1"
    assert "why_review_focus" not in request.user_instruction
    assert "approved_copy" not in request.user_instruction
    assert "why_consider" in request.system_instruction
    assert "trade_offs" in request.system_instruction


def test_v2_1_accepts_decision_language_and_preserves_source():
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.validator_v2_1 import validate_narrative_v2_1

    bundle, source, _, facts, payload = _payload()
    before = deepcopy(bundle.model_dump(mode="json"))
    validate_narrative_v2_1(RecruiterNarrativeV2_1.model_validate(payload), facts=facts, bundle=bundle, source=source)
    assert bundle.model_dump(mode="json") == before


@pytest.mark.parametrize("text", [
    "候选人熟悉 Kubernetes，并有 Python 项目记录。",
    "候选人主导了 Python 系统开发。",
    "候选人负责百万用户规模的 Python 平台。",
    "候选人利用 Python 提升准确率 50%。",
    "候选人一定适合岗位，建议直接录用。",
    "候选人曾在另一个候选人的项目中使用 Python。",
])
def test_v2_1_rejects_unsupported_or_cross_candidate_claim(text):
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.validator_v2_1 import NarrativeV2_1ValidationError, validate_narrative_v2_1

    bundle, source, _, facts, payload = _payload()
    payload["why_consider"]["text"] = text
    with pytest.raises(NarrativeV2_1ValidationError):
        validate_narrative_v2_1(RecruiterNarrativeV2_1.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_1_repair_diagnostic_identifies_unsupported_term_without_raw_prose():
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.validator_v2_1 import validation_error_summary_v2_1

    _, _, projection, _, payload = _payload()
    payload["key_strengths"][0]["explanation"] = "项目记录涉及 Python 与 Kubernetes。"
    summary = validation_error_summary_v2_1(RecruiterNarrativeV2_1.model_validate(payload), projection=projection)
    assert summary["category"] == "claim_validation_failed"
    assert summary["invalid_sections"][0]["section"] == "key_strengths"
    assert summary["invalid_sections"][0]["unsupported_terms"] == ["kubernetes"]
    assert "Python" in summary["invalid_sections"][0]["supported_terms"] or "python" in summary["invalid_sections"][0]["supported_terms"]
    assert "项目记录" not in str(summary)


def test_v2_1_diagnostic_reports_missing_direction_and_per_text_role_tokens():
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.validator_v2_1 import validation_error_summary_v2_1

    _, _, projection, _, payload = _payload()
    payload["candidate_snapshot"]["text"] = "推荐系统方向的 Python 项目值得讨论。"
    payload["key_strengths"][0]["title"] = "AI Engineer 方向"
    payload["key_strengths"][0]["explanation"] = "Python 项目还体现 AI 能力。"
    summary = validation_error_summary_v2_1(RecruiterNarrativeV2_1.model_validate(payload), projection=projection)
    by_section = {entry["section"]: entry for entry in summary["invalid_sections"]}
    assert by_section["candidate_snapshot"]["missing_direction_terms"] == ["推荐系统"]
    assert "ai" in by_section["key_strengths"]["unsupported_terms"]


def test_v2_1_direction_inference_requires_multiple_project_facts():
    from app.services.explanation.presentation.facts_v2_1 import build_atomic_facts_v2_1
    from narrative_v2_comparison_fixture import build_comparison_group

    recommendation = build_comparison_group(2)["projections"][0]
    facts = build_atomic_facts_v2_1(recommendation)
    direction = next(f for f in facts if f.kind == "direction_inference" and f.term == "推荐系统")
    assert direction.evidence_refs
    assert len({f.term.casefold() for f in facts if f.kind == "project_practice" and f.term.casefold() in {"lambdamart", "retrieval", "evaluation"}}) >= 2
    assert any(f.kind == "project_practice" and f.term.casefold() == "lambdamart" for f in facts)
    python_only = _payload()[2]
    assert not any(f.kind == "direction_inference" for f in build_atomic_facts_v2_1(python_only))


def test_v2_1_direction_fact_is_self_contained_source_bound_for_tradeoff():
    from app.services.explanation.presentation.facts_v2_1 import build_atomic_facts_v2_1
    from app.services.explanation.presentation.validator_v2_1 import _unsupported_direction
    from narrative_v2_comparison_fixture import build_comparison_group

    projection = build_comparison_group(2)["projections"][0]
    direction = next(f for f in build_atomic_facts_v2_1(projection) if f.kind == "direction_inference" and f.term == "推荐系统")
    assert not _unsupported_direction(("推荐系统相关实践的职责范围待了解。",), [direction])


def test_v2_1_rejects_direction_claim_without_derived_fact():
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.validator_v2_1 import NarrativeV2_1ValidationError, validate_narrative_v2_1

    bundle, source, _, facts, payload = _payload()
    payload["candidate_snapshot"]["text"] = "这位候选人具有推荐系统方向的 Python 项目实践。"
    with pytest.raises(NarrativeV2_1ValidationError):
        validate_narrative_v2_1(RecruiterNarrativeV2_1.model_validate(payload), facts=facts, bundle=bundle, source=source)


@pytest.mark.parametrize("claim", [
    "候选人已有高可用后端服务的工程实践。",
    "候选人上线后的 Python 系统取得业务收益。",
])
def test_v2_1_rejects_unrecorded_production_or_outcome_claim(claim):
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.validator_v2_1 import NarrativeV2_1ValidationError, validate_narrative_v2_1

    bundle, source, _, facts, payload = _payload()
    payload["interview_focus"][0]["reason"] = claim
    with pytest.raises(NarrativeV2_1ValidationError):
        validate_narrative_v2_1(RecruiterNarrativeV2_1.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_1_allows_unknown_scale_as_tradeoff_but_not_asserted_scale():
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.validator_v2_1 import NarrativeV2_1ValidationError, validate_narrative_v2_1

    bundle, source, _, facts, payload = _payload()
    payload["trade_offs"][0]["explanation"] = "当前材料未体现大规模 Python 系统经验，需面试确认。"
    payload["trade_offs"][0]["validation_question"] = "请说明是否参与过大规模 Python 系统？"
    validate_narrative_v2_1(RecruiterNarrativeV2_1.model_validate(payload), facts=facts, bundle=bundle, source=source)
    payload["trade_offs"][0]["explanation"] = "候选人具备大规模 Python 系统经验，仍需确认。"
    with pytest.raises(NarrativeV2_1ValidationError):
        validate_narrative_v2_1(RecruiterNarrativeV2_1.model_validate(payload), facts=facts, bundle=bundle, source=source)


@pytest.mark.parametrize("claim", [
    "候选人结合 Python 技术进行了应用开发与部署。",
    "在 Python 生态下使用 Python 构建后端服务。",
    "候选人掌握 Python，具备后端工程能力。",
    "Python 项目体现了候选人的数据库工程经验。",
    "候选人在项目中结合了 Python 与数据库技术。",
    "候选人在项目中实践了基于 Python 的系统架构。",
])
def test_v2_1_rejects_project_technology_upgraded_to_personal_work_or_mastery(claim):
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.validator_v2_1 import NarrativeV2_1ValidationError, validate_narrative_v2_1

    bundle, source, _, facts, payload = _payload()
    payload["key_strengths"][0]["explanation"] = claim
    with pytest.raises(NarrativeV2_1ValidationError):
        validate_narrative_v2_1(RecruiterNarrativeV2_1.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_1_rejects_foreign_fact_and_missing_requirement_relation():
    from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
    from app.services.explanation.presentation.validator_v2_1 import NarrativeV2_1ValidationError, validate_narrative_v2_1

    bundle, source, _, facts, payload = _payload()
    payload["why_consider"]["fact_ids"] = ["fact:" + "a" * 32]
    with pytest.raises(NarrativeV2_1ValidationError):
        validate_narrative_v2_1(RecruiterNarrativeV2_1.model_validate(payload), facts=facts, bundle=bundle, source=source)
    project = next(f for f in facts if f.kind == "project_practice" and f.term.casefold() == "python")
    payload["why_consider"]["fact_ids"] = [project.fact_id]
    with pytest.raises(NarrativeV2_1ValidationError):
        validate_narrative_v2_1(RecruiterNarrativeV2_1.model_validate(payload), facts=facts, bundle=bundle, source=source)


def test_v2_1_service_persists_separate_validated_artifact_without_ranking_change():
    from app.services.explanation.presentation.service_v2_1 import RecruiterNarrativeV2_1Service
    from test_recruiter_narrative_service import _service

    _, _, _, _, payload = _payload()
    _, repository, transport, source = _service(payload)
    before = deepcopy(source.bundle.model_dump(mode="json"))
    record = asyncio.run(RecruiterNarrativeV2_1Service(repository=repository, provider=transport).generate(42))
    assert record.prompt_version == "recruiter_narrative_prompt_v2_1"
    assert record.validated_content_json["contract_version"] == "recruiter_narrative_v2_1"
    assert record.ranking_fingerprint == source.bundle.source.result_fingerprint
    assert source.bundle.model_dump(mode="json") == before
    assert asyncio.run(RecruiterNarrativeV2_1Service(repository=repository).get(record.narrative_id)).status == "COMPLETED"


def test_v2_1_service_fails_closed_on_unsupported_claim():
    from app.services.explanation.presentation.service import NarrativeGenerationFailedError
    from app.services.explanation.presentation.service_v2_1 import RecruiterNarrativeV2_1Service
    from test_recruiter_narrative_service import _service

    _, _, _, _, payload = _payload()
    payload["why_consider"]["text"] = "候选人负责百万用户规模的 Python 平台。"
    _, repository, transport, _ = _service(payload)
    with pytest.raises(NarrativeGenerationFailedError):
        asyncio.run(RecruiterNarrativeV2_1Service(repository=repository, provider=transport).generate(42))
    assert repository.saved[0].validated_content_json is None


def test_v2_1_api_creates_and_reads_versioned_narrative():
    from fastapi.testclient import TestClient
    from app.api.dependencies import get_recruiter_narrative_v2_1_query_service, get_recruiter_narrative_v2_1_service
    from app.main import create_app
    from app.services.explanation.presentation.service_v2_1 import RecruiterNarrativeV2_1Service
    from test_recruiter_narrative_service import _service

    _, _, _, _, payload = _payload()
    _, repository, transport, _ = _service(payload)
    service = RecruiterNarrativeV2_1Service(repository=repository, provider=transport)
    app = create_app()
    app.dependency_overrides[get_recruiter_narrative_v2_1_service] = lambda: service
    app.dependency_overrides[get_recruiter_narrative_v2_1_query_service] = lambda: service
    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post("/api/v1/match-explanations/42/recruiter-narratives-v2-1")
        assert created.status_code == 201
        detail = client.get(f"/api/v1/recruiter-narratives-v2-1/{created.json()['data']['narrative_id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["narrative"]["contract_version"] == "recruiter_narrative_v2_1"
    assert "api_key" not in detail.text.lower()
