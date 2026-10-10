from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from narrative_v2_comparison_fixture import build_comparison_group


def _case():
    from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3

    case = build_comparison_group(2)
    projection = case["projections"][0]
    return case, projection, build_atomic_fact_graph_v3(projection)


def _narrative(projection, graph):
    from app.services.explanation.presentation.contracts_v3 import RecruiterNarrativeV3

    alignment = next(f for f in graph.facts if f.kind == "job_alignment" and "retrieval" in f.concepts)
    scope = next(f for f in graph.facts if f.kind == "technical_scope" and "retrieval" in f.concepts)
    interview = next(f for f in graph.facts if f.kind == "interview_validation" and "retrieval" in f.concepts)
    return RecruiterNarrativeV3.model_validate({
        "contract_version": "recruiter_narrative_v3",
        "candidate_id": projection.candidate_id,
        "result_rank": projection.result_rank,
        "decision": "prioritize_review",
        "decision_summary": {"text": "项目材料涉及 Retrieval 与 Ranking，和岗位检索排序方向相关，值得安排技术复核。",
                             "claim_type": "capability_inference", "fact_ids": [alignment.fact_id, scope.fact_id]},
        "strengths": [{"text": "材料覆盖 Retrieval 与 Ranking 的技术范围。",
                       "claim_type": "evidence_statement", "fact_ids": [scope.fact_id]}],
        "risks": [{"text": "具体负责范围尚需面试确认。",
                   "claim_type": "uncertainty_statement", "fact_ids": [interview.fact_id]}],
        "interview_focus": [{"text": "请询问 Retrieval 召回与 Ranking 排序方案如何取舍？",
                             "claim_type": "interview_validation", "fact_ids": [interview.fact_id]}],
    })


def test_v3_graph_derives_safe_relations_from_observed_synonyms():
    _, projection, graph = _case()
    assert any(f.kind == "technical_scope" and {"retrieval", "ranking", "evaluation"} <= set(f.concepts)
               for f in graph.facts)
    assert any(f.kind == "job_alignment" and "retrieval" in f.concepts for f in graph.facts)
    assert all(ref in projection.facts for f in graph.facts for ref in f.evidence_refs)
    assert not any("lambdamart" in f.concepts for f in graph.facts if f.kind == "technical_scope")
    assert graph.claim_candidates
    assert any(edge.relation == "listed_skill_overlaps_project_term" for edge in graph.edges)


def test_v3_graph_connects_distinct_project_coverage_without_same_project_claim():
    from app.services.explanation.presentation.adapter import NarrativeProjection
    from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3

    projection = NarrativeProjection(
        candidate_id="synthetic-candidate", result_rank=1, role_title="Recommendation Engineer",
        facts={"candidate:1:project:a": ("candidate retrieval", "learning to rank"),
               "candidate:1:project:b": ("feature engineering", "offline evaluation"),
               "job_requirement:evaluation": ("Feature Engineering and Offline Evaluation",)},
        verification_status={},
        positive_refs=frozenset({"candidate:1:project:a", "candidate:1:project:b",
                                 "job_requirement:evaluation"}),
        risk_refs=frozenset(), interview_refs=frozenset(),
    )
    graph = build_atomic_fact_graph_v3(projection)
    assert any(f.kind == "candidate_portfolio_scope" and
               {"retrieval", "ranking", "evaluation"} <= set(f.concepts)
               and len(f.evidence_refs) == 2 for f in graph.facts)
    assert not any(f.kind == "technical_scope" and
                   {"retrieval", "evaluation"} <= set(f.concepts) for f in graph.facts)


def test_v3_graph_does_not_merge_unrelated_projects_or_invent_ownership():
    from app.services.explanation.presentation.adapter import NarrativeProjection
    from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3

    projection = NarrativeProjection(
        candidate_id="synthetic-candidate", result_rank=1, role_title="Search Engineer",
        facts={"candidate:1:project:a": ("vector retrieval",),
               "candidate:1:project:b": ("offline evaluation",),
               "job_requirement:search": ("Retrieval",)},
        verification_status={},
        positive_refs=frozenset({"candidate:1:project:a", "candidate:1:project:b", "job_requirement:search"}),
        risk_refs=frozenset(), interview_refs=frozenset(),
    )
    graph = build_atomic_fact_graph_v3(projection)
    assert not any(f.kind == "technical_scope" and {"retrieval", "evaluation"} <= set(f.concepts)
                   for f in graph.facts)
    assert all("负责" not in f.allowed_inference and "主导" not in f.allowed_inference
               for f in graph.facts if f.kind == "technical_scope")


def test_v3_accepts_natural_hiring_language_without_mutating_ranking():
    from app.services.explanation.presentation.validator_v3 import validate_narrative_v3_projection

    case, projection, graph = _case()
    before = deepcopy(case["ranking_before"])
    validate_narrative_v3_projection(_narrative(projection, graph), projection=projection)
    assert case["ranking_before"] == before
    assert case["run"].result_fingerprint == before["fingerprint"]
    assert [r.candidate_id for r in case["run"].results] == before["order"]
    assert [r.ltr_score_raw for r in case["run"].results] == before["ltr_scores"]


def test_v3_accepts_extra_cited_fact_on_the_same_observed_project_path():
    from app.services.explanation.presentation.validator_v3 import validate_narrative_v3_projection

    _, projection, graph = _case()
    narrative = _narrative(projection, graph)
    alignment = next(f for f in graph.facts if f.fact_id == narrative.decision_summary.fact_ids[0])
    project = next(f for f in graph.facts if f.fact_id in alignment.source_fact_ids or
                   f.fact_id in {edge.source_id for edge in graph.edges if edge.target_id == alignment.fact_id})
    expanded = narrative.model_copy(update={"decision_summary": narrative.decision_summary.model_copy(
        update={"fact_ids": [*narrative.decision_summary.fact_ids, project.fact_id]})})
    validate_narrative_v3_projection(expanded, projection=projection)


def test_v3_alignment_fact_can_trace_its_project_lineage_without_duplicate_citation():
    from app.services.explanation.presentation.validator_v3 import validate_narrative_v3_projection

    _, projection, graph = _case()
    narrative = _narrative(projection, graph)
    alignment = narrative.decision_summary.fact_ids[0]
    changed = narrative.model_copy(update={"decision_summary": narrative.decision_summary.model_copy(
        update={"fact_ids": [alignment],
                "text": "项目材料涉及 Retrieval，与岗位检索方向相关，值得安排技术复核。"})})
    validate_narrative_v3_projection(changed, projection=projection)


def test_v3_allows_unknown_responsibility_scope_as_a_question_not_a_claim():
    from app.services.explanation.presentation.validator_v3 import validate_narrative_v3_projection

    _, projection, graph = _case()
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"risks": [narrative.risks[0].model_copy(
        update={"text": "候选人的具体负责范围仍需面试确认。"})]})
    validate_narrative_v3_projection(changed, projection=projection)
    question = narrative.model_copy(update={"risks": [narrative.risks[0].model_copy(
        update={"text": "下一轮需要确认候选人是否负责 Retrieval 方案取舍。"})]})
    validate_narrative_v3_projection(question, projection=projection)


def test_v3_rejects_question_that_presupposes_unverified_personal_construction():
    from app.services.explanation.presentation.validator_v3 import NarrativeV3ValidationError, validate_narrative_v3_projection

    _, projection, graph = _case()
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"interview_focus": [narrative.interview_focus[0].model_copy(
        update={"text": "在构建 Retrieval 排序服务时，您是如何决定架构取舍的？"})]})
    with pytest.raises(NarrativeV3ValidationError):
        validate_narrative_v3_projection(changed, projection=projection)


def test_v3_graph_groups_multiple_open_requirements_without_candidate_absence_claim():
    from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3

    _, original, _ = _case()
    risk_refs = {"job_requirement:scale", "job_requirement:reliability"}
    projection = replace(original,
                         facts={**original.facts,
                                "job_requirement:scale": ("Production scale to verify",),
                                "job_requirement:reliability": ("Reliability to verify",)},
                         risk_refs=frozenset(risk_refs))
    graph = build_atomic_fact_graph_v3(projection)
    assert any(f.kind == "open_requirement_group" and set(f.evidence_refs) == risk_refs
               for f in graph.facts)


def test_v3_accepts_chinese_expression_of_cited_technical_concepts():
    from app.services.explanation.presentation.validator_v3 import validate_narrative_v3_projection

    _, projection, graph = _case()
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"strengths": [narrative.strengths[0].model_copy(
        update={"text": "材料覆盖检索与排序的技术范围。"})]})
    validate_narrative_v3_projection(changed, projection=projection)


def test_v3_rejects_combining_distinct_projects_into_one_project_claim():
    from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3
    from app.services.explanation.presentation.validator_v3 import NarrativeV3ValidationError, validate_narrative_v3_projection

    _, original, _ = _case()
    other_ref = "candidate:1:project:other"
    projection = replace(original,
                         facts={**original.facts, other_ref: ("offline evaluation", "embedding")},
                         positive_refs=original.positive_refs | {other_ref})
    graph = build_atomic_fact_graph_v3(projection)
    portfolio = next(f for f in graph.facts if f.kind == "candidate_portfolio_scope")
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"strengths": [narrative.strengths[0].model_copy(update={
        "text": "同一项目材料覆盖 Retrieval 与 Evaluation。", "fact_ids": [portfolio.fact_id],
    })]})
    with pytest.raises(NarrativeV3ValidationError):
        validate_narrative_v3_projection(changed, projection=projection)


@pytest.mark.parametrize("claim", [
    "候选人熟悉 Kubernetes，并涉及 Retrieval。",
    "候选人主导开发企业级 Retrieval 平台。",
    "候选人负责百万用户的 Retrieval 系统。",
    "候选人将 Retrieval 准确率提升 50%。",
    "候选人已经证明完全胜任岗位。",
    "另一位候选人完成了 Retrieval 项目。",
])
def test_v3_rejects_unsupported_claims(claim):
    from app.services.explanation.presentation.validator_v3 import NarrativeV3ValidationError, validate_narrative_v3_projection

    _, projection, graph = _case()
    narrative = _narrative(projection, graph)
    changed = narrative.model_copy(update={"decision_summary": narrative.decision_summary.model_copy(update={"text": claim})})
    with pytest.raises(NarrativeV3ValidationError):
        validate_narrative_v3_projection(changed, projection=projection)


def test_v3_rejects_fact_from_another_candidate_and_unsupported_relation():
    from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3
    from app.services.explanation.presentation.validator_v3 import NarrativeV3ValidationError, validate_narrative_v3_projection

    case, projection, graph = _case()
    narrative = _narrative(projection, graph)
    foreign = build_atomic_fact_graph_v3(case["projections"][1]).facts[0].fact_id
    changed = narrative.model_copy(update={"strengths": [narrative.strengths[0].model_copy(update={"fact_ids": [foreign]})]})
    with pytest.raises(NarrativeV3ValidationError):
        validate_narrative_v3_projection(changed, projection=projection)
    wrong_kind = narrative.model_copy(update={"decision_summary": narrative.decision_summary.model_copy(
        update={"claim_type": "evidence_statement"})})
    with pytest.raises(NarrativeV3ValidationError):
        validate_narrative_v3_projection(wrong_kind, projection=projection)


def test_v3_job_requirement_does_not_grant_unsupported_candidate_skill():
    from app.services.explanation.presentation.adapter import NarrativeProjection
    from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3

    projection = NarrativeProjection(
        candidate_id="synthetic-candidate", result_rank=1, role_title="RAG Engineer",
        facts={"candidate:1:project:rag": ("RAG", "Qdrant"),
               "job_requirement:rag": ("RAG and Kubernetes",)},
        verification_status={},
        positive_refs=frozenset({"candidate:1:project:rag", "job_requirement:rag"}),
        risk_refs=frozenset(), interview_refs=frozenset(),
    )
    graph = build_atomic_fact_graph_v3(projection)
    alignment = next(f for f in graph.facts if f.kind == "job_alignment")
    assert "rag" in alignment.concepts
    assert "kubernetes" not in alignment.term.casefold()


def test_v3_search_relevance_label_alone_does_not_invent_retrieval_experience():
    from app.services.explanation.presentation.adapter import NarrativeProjection
    from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3

    projection = NarrativeProjection(
        candidate_id="synthetic-candidate", result_rank=1, role_title="Search Engineer",
        facts={"candidate:1:project:relevance": ("search relevance",),
               "job_requirement:retrieval": ("retrieval",)},
        verification_status={},
        positive_refs=frozenset({"candidate:1:project:relevance", "job_requirement:retrieval"}),
        risk_refs=frozenset(), interview_refs=frozenset(),
    )
    graph = build_atomic_fact_graph_v3(projection)
    assert not any("retrieval" in fact.concepts for fact in graph.facts)


def test_v3_skill_list_alone_cannot_be_rephrased_as_project_evidence():
    from app.services.explanation.presentation.adapter import NarrativeProjection
    from app.services.explanation.presentation.contracts_v3 import RecruiterNarrativeV3
    from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3
    from app.services.explanation.presentation.validator_v3 import NarrativeV3ValidationError, validate_narrative_v3_projection

    projection = NarrativeProjection(
        candidate_id="synthetic-candidate", result_rank=1, role_title="FastAPI Engineer",
        facts={"candidate:1:skill:fastapi": ("FastAPI",),
               "candidate:1:project:python": ("Python",),
               "job_requirement:fastapi": ("FastAPI",)},
        verification_status={},
        positive_refs=frozenset({"candidate:1:skill:fastapi", "candidate:1:project:python",
                                 "job_requirement:fastapi"}),
        risk_refs=frozenset(), interview_refs=frozenset(),
    )
    graph = build_atomic_fact_graph_v3(projection)
    skill = next(f for f in graph.facts if f.kind == "candidate_capability")
    align = next(f for f in graph.facts if f.kind == "job_alignment")
    project = next(f for f in graph.facts if f.kind == "project_evidence")
    focus = next(f for f in graph.facts if f.kind == "interview_validation")
    narrative = RecruiterNarrativeV3.model_validate({
        "contract_version": "recruiter_narrative_v3", "candidate_id": projection.candidate_id,
        "result_rank": 1, "decision": "needs_verification",
        "decision_summary": {"text": "项目材料覆盖 FastAPI，与岗位要求相关，建议人工复核。",
                             "claim_type": "capability_inference", "fact_ids": [skill.fact_id, align.fact_id]},
        "strengths": [{"text": "资料列出 Python 技术。", "claim_type": "evidence_statement",
                       "fact_ids": [project.fact_id]}],
        "risks": [{"text": "Python 项目的具体深度仍需确认。", "claim_type": "uncertainty_statement",
                   "fact_ids": [focus.fact_id]}],
        "interview_focus": [{"text": "请询问 Python 项目中的方案取舍？", "claim_type": "interview_validation",
                             "fact_ids": [focus.fact_id]}],
    })
    with pytest.raises(NarrativeV3ValidationError):
        validate_narrative_v3_projection(narrative, projection=projection)


def test_v3_prompt_exposes_graph_without_approved_copy():
    from app.services.explanation.presentation.prompt_v3 import build_narrative_v3_request

    _, projection, graph = _case()
    request = build_narrative_v3_request(graph, projection=projection, max_output_tokens=2048)
    assert request.output_contract_version == "recruiter_narrative_v3"
    assert "claim_candidates" in request.user_instruction
    assert "approved_copy" not in request.user_instruction
