"""Controlled, opt-in proposition generation; no product runtime integration."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from narrative_v2_comparison_fixture import build_comparison_group

from app.services.explanation.presentation.propositions_v1 import build_recruiter_propositions_v1
from app.services.explanation.presentation.generation_proposition_v1 import (
    PropositionProviderOutputV1, build_proposition_binding_v1,
    build_proposition_generation_request_v1, parse_proposition_provider_output_v1,
    resolve_proposition_output_v1,
)


def _inputs():
    projection = build_comparison_group(1)["projections"][0]
    propositions = build_recruiter_propositions_v1(projection)
    return projection, propositions, build_proposition_binding_v1(propositions)


def _payload(binding):
    def paragraph(field):
        return {"text": "这名候选人的项目方向值得技术面继续了解。",
                "proposition_handles": {binding.allowed_handles(field)[0]: True}}
    return {
        "contract_version": "recruiter_proposition_generation_v1",
        "candidate_id": binding.candidate_id, "result_rank": binding.result_rank,
        "decision_summary": paragraph("decision_summary"),
        **{field: [paragraph(field)] for field in
           ("why_consider", "technical_signal", "interview_focus", "uncertainty")},
    }


def test_native_schema_has_field_specific_proposition_handle_enums():
    projection, propositions, binding = _inputs()
    request = build_proposition_generation_request_v1(
        projection, propositions, max_output_tokens=2048)
    assert request.response_schema is not None
    assert request.response_schema["title"] == "PropositionProviderOutputV1"
    assert "$defs" not in request.response_schema
    for field in ("decision_summary", "why_consider", "technical_signal",
                  "interview_focus", "uncertainty"):
        item = request.response_schema["properties"][field]
        if field != "decision_summary":
            assert item["type"] == "array"
            item = item["items"]
        handle_map = item["properties"]["proposition_handles"]
        assert set(handle_map["properties"]) == set(binding.allowed_handles(field))
        assert handle_map.get("required", []) == []
        assert handle_map["additionalProperties"] is False
    catalog = json.loads(request.user_instruction)["proposition_catalog"]
    assert catalog and all(item["handle"].startswith("P") for item in catalog)
    assert all("proposition:" not in json.dumps(item) for item in catalog)
    assert "hiring_context" not in request.user_instruction
    assert "decision_frame" not in request.user_instruction


def test_exact_binding_and_candidate_isolation():
    _, propositions, binding = _inputs()
    second = build_recruiter_propositions_v1(build_comparison_group(1)["projections"][1])
    second_binding = build_proposition_binding_v1(second)
    assert binding == build_proposition_binding_v1(propositions)
    assert binding.allowed_handles("why_consider")
    handle = binding.allowed_handles("why_consider")[0]
    assert binding.resolve([handle], field="why_consider") == [
        next(entry.proposition_id for entry in binding.entries if entry.handle == handle)]
    with pytest.raises(ValueError, match="invalid_proposition_handles"):
        binding.resolve([handle, handle], field="why_consider")
    for invalid in ("P99", handle.lower(), "claim:" + handle):
        with pytest.raises(ValueError):
            binding.resolve([invalid], field="why_consider")
    with pytest.raises(ValueError):
        binding.resolve([binding.allowed_handles("uncertainty")[0]], field="why_consider")
    assert {entry.proposition_id for entry in binding.entries}.isdisjoint(
        entry.proposition_id for entry in second_binding.entries)
    assert {entry.candidate_id for entry in binding.entries} == {binding.candidate_id}
    assert {entry.candidate_id for entry in second_binding.entries} == {second_binding.candidate_id}


def test_provider_output_is_strict_and_resolution_preserves_text():
    _, _, binding = _inputs()
    payload = _payload(binding)
    raw = PropositionProviderOutputV1.model_validate(payload)
    internal = resolve_proposition_output_v1(raw, binding)
    assert internal.why_consider[0].text == payload["why_consider"][0]["text"]
    assert internal.why_consider[0].proposition_refs == binding.resolve(
        [handle for handle, selected in payload["why_consider"][0]["proposition_handles"].items()
         if selected], field="why_consider")
    for field in ("why_consider", "technical_signal"):
        wrong = {**payload, field: payload[field][0]}
        with pytest.raises(ValidationError):
            PropositionProviderOutputV1.model_validate(wrong)
    wrong_candidate = raw.model_copy(update={"candidate_id": "foreign"})
    with pytest.raises(ValueError):
        resolve_proposition_output_v1(wrong_candidate, binding)


def test_handle_selection_object_rejects_duplicates_in_raw_json_and_invalid_values():
    projection, propositions, binding = _inputs()
    payload = _payload(binding)
    handle = binding.allowed_handles("decision_summary")[0]
    raw = json.dumps(payload, ensure_ascii=False)
    duplicate_raw = raw.replace(f'"{handle}": true', f'"{handle}": true, "{handle}": true', 1)
    with pytest.raises(ValueError, match="duplicate_json_key"):
        parse_proposition_provider_output_v1(duplicate_raw)
    payload["decision_summary"]["proposition_handles"] = [handle, handle]
    with pytest.raises(ValidationError):
        PropositionProviderOutputV1.model_validate(payload)
    payload = _payload(binding)
    payload["decision_summary"]["proposition_handles"][handle] = False
    with pytest.raises(ValidationError):
        PropositionProviderOutputV1.model_validate(payload)
    schema = build_proposition_generation_request_v1(
        projection, propositions, max_output_tokens=2048).response_schema
    assert schema["properties"]["decision_summary"]["properties"]["proposition_handles"]["type"] == "object"
    for field in ("why_consider", "technical_signal", "interview_focus", "uncertainty"):
        assert schema["properties"][field]["items"]["properties"]["proposition_handles"]["type"] == "object"


def test_request_builder_rebuilds_provenance_before_exposing_propositions_to_model():
    projection, propositions, _ = _inputs()
    first = propositions.propositions[0]
    forged = first.model_copy(update={"topic_terms": ("unverified_skill",)})
    changed = propositions.model_copy(update={
        "propositions": (forged, *propositions.propositions[1:]),
    })
    with pytest.raises(ValueError, match="noncanonical_recruiter_propositions"):
        build_proposition_generation_request_v1(projection, changed, max_output_tokens=2048)


def test_model_sees_conditional_review_boundary_for_thin_job_overlap():
    projection = build_comparison_group(1)["projections"][1]
    propositions = build_recruiter_propositions_v1(projection)
    request = build_proposition_generation_request_v1(
        projection, propositions, max_output_tokens=2048)
    catalog = json.loads(request.user_instruction)["proposition_catalog"]
    assert next(item["predicate"] for item in catalog
                if item["kind"] == "human_review_recommendation") == "consider_targeted_screen"
    assert "consider_targeted_screen" in request.system_instruction
    assert "不得写优先" in request.system_instruction


def test_no_ranking_or_evidence_mutation_from_request_build():
    group = build_comparison_group(2)
    before = group["ranking_before"]
    for projection in group["projections"]:
        props = build_recruiter_propositions_v1(projection)
        build_proposition_generation_request_v1(projection, props, max_output_tokens=2048)
    run = group["run"]
    assert run.result_fingerprint == before["fingerprint"]
    assert [item.candidate_id for item in run.results] == before["order"]
    assert [item.ltr_score_raw for item in run.results] == before["ltr_scores"]


def test_legacy_shadow_is_explicitly_non_authoritative_for_direct_observations():
    from narrative_proposition_v1_live_experiment import _shadow_rows

    projection, propositions, binding = _inputs()
    direct_id = next(item.proposition_id for item in propositions.propositions
                     if item.kind == "project_observation")
    direct_handle = next(entry.handle for entry in binding.entries
                         if entry.proposition_id == direct_id)
    payload = _payload(binding)
    payload["technical_signal"][0]["proposition_handles"] = {direct_handle: True}
    narrative = resolve_proposition_output_v1(
        PropositionProviderOutputV1.model_validate(payload), binding)
    rows = _shadow_rows(narrative, propositions, projection)
    assert any(row["field"] == "technical_signal"
               and row["status"] == "NOT_COMPARABLE" for row in rows)
    assert len(rows) == 5
