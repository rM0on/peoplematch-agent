"""Model-facing epistemic guidance does not change V5 safety contracts."""

from __future__ import annotations

import json

import pytest

from app.services.explanation.presentation.claim_handle_binding_v5 import build_claim_handle_binding_v5
from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
from app.services.explanation.presentation.prompt_v5 import build_narrative_v5_request
from app.services.explanation.presentation.provider_output_v5 import build_provider_response_schema_v5
from test_recruiter_narrative_v5 import _inputs


def _request_and_catalog():
    projection, graph, frame = _inputs()
    context = build_hiring_context_v5(graph, frame)
    binding = build_claim_handle_binding_v5(graph, frame, context)
    request = build_narrative_v5_request(
        context, graph=graph, frame=frame, role_title=projection.role_title,
        max_output_tokens=2048, binding=binding,
    )
    payload = json.loads(request.user_instruction)
    return request, payload, binding


def test_model_catalog_exposes_existing_claim_epistemic_strength_without_changing_schema():
    request, payload, binding = _request_and_catalog()
    expected = {
        ("technical_alignment", "observed_requirement_overlap"): "ALIGNMENT",
        ("skill_requirement_match", "listed_skill_overlap"): "ALIGNMENT",
        ("project_depth_validation", "verify_observed_scope"): "INTERVIEW_TARGET",
        ("interview_focus", "verify_observed_scope"): "INTERVIEW_TARGET",
        ("interview_focus", "open_requirement"): "UNKNOWN",
        ("review_recommendation", "alignment_plus_interview_focus"): "ALIGNMENT",
    }
    catalog = payload["claim_catalog"]
    assert catalog
    for item in catalog:
        assert item["epistemic_role"] == expected[(item["claim_type"], item["relation_type"])]
        assert item["expression_boundary"]
        assert item["handle"] in {entry.handle for entry in binding.entries}
    assert request.response_schema == build_provider_response_schema_v5(binding)
    assert all(entry.claim_id not in request.user_instruction for entry in binding.entries)


@pytest.mark.parametrize(("claim_type", "relation_type", "boundary_terms"), [
    ("technical_alignment", "observed_requirement_overlap", ("岗位", "经验", "能力")),
    ("interview_focus", "verify_observed_scope", ("是否", "职责", "预设")),
    ("interview_focus", "open_requirement", ("未知", "缺少")),
    ("review_recommendation", "alignment_plus_interview_focus", ("人工", "录用")),
])
def test_catalog_boundaries_make_epistemic_upgrades_explicit(claim_type, relation_type, boundary_terms):
    _, payload, _ = _request_and_catalog()
    item = next(item for item in payload["claim_catalog"]
                if (item["claim_type"], item["relation_type"]) == (claim_type, relation_type))
    assert all(term in item["expression_boundary"] for term in boundary_terms)


def test_prompt_distinguishes_fact_alignment_target_unknown_and_question_presupposition():
    request, _, _ = _request_and_catalog()
    instruction = request.system_instruction
    assert all(role in instruction for role in ("FACT", "ALIGNMENT", "INTERVIEW_TARGET", "UNKNOWN"))
    assert "候选人具备的 RAG 相关经验" in instruction
    assert "请描述你负责的具体模块" in instruction
    assert "请说明你在该项目中的实际参与范围" in instruction
    assert "候选人缺少生产部署经验" in instruction
    assert "当前材料尚不能确认其是否参与生产环境部署" in instruction
    assert "静默" in instruction
    assert "不要输出" in instruction
