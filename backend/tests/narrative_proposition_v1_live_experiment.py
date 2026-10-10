"""Opt-in six-sample, synthetic-only Proposition V1 controlled generation.

Run from repository root with the backend virtualenv. Prints one JSON record per
candidate, including every success/failure. Never persists product narratives.
"""

from __future__ import annotations

import asyncio
import argparse
import json
import time

from pydantic import ValidationError

from app.core.config import Settings
from app.services.explanation.generation.provider import ExplanationProviderError
from app.services.explanation.presentation.claims_v4 import build_recruiter_claim_graph_v4
from app.services.explanation.presentation.contracts_v4 import RecruiterNarrativeV4
from app.services.explanation.presentation.decision_frame_v4_1 import (
    build_hiring_decision_frame_v4_1, diagnose_narrative_frame_v4_1,
)
from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3
from app.services.explanation.presentation.generation_proposition_v1 import (
    FIELDS, build_proposition_binding_v1, build_proposition_generation_request_v1,
    parse_proposition_provider_output_v1, resolve_proposition_output_v1,
)
from app.services.explanation.presentation.propositions_v1 import build_recruiter_propositions_v1
from app.services.explanation.presentation.semantic_audit_proposition_v1 import (
    BlindNarrativeAuditOutputV1, build_blind_semantic_audit_request_v1,
    evaluate_blind_semantic_audit_v1,
)
from app.services.explanation.presentation.validator_v4 import diagnose_narrative_v4
from app.services.llm.configuration import ProviderMode, ProviderTask, resolve_provider_selection
from narrative_v2_comparison_fixture import build_comparison_group


_LEGACY_ROLES = {
    "decision_summary": ("summary", {"review_recommendation"}),
    "why_consider": ("strengths[0]", {"technical_alignment", "skill_requirement_match"}),
    "technical_signal": ("strengths[0]", {"technical_alignment", "skill_requirement_match"}),
    "interview_focus": ("interview_focus[0]", {"interview_focus", "project_depth_validation"}),
    "uncertainty": ("risks[0]", {"interview_focus", "project_depth_validation"}),
}


def _shadow_rows(narrative, propositions, projection):
    """Legacy V4 rules are observation only; unmappable paragraphs are explicit."""
    graph = build_recruiter_claim_graph_v4(build_atomic_fact_graph_v3(projection))
    try:
        frame = build_hiring_decision_frame_v4_1(graph)
    except ValueError:
        return [{"field": field, "status": "NOT_COMPARABLE", "reason": "legacy_frame_unavailable"}
                for field in FIELDS]
    claims = {item.claim_id: item for item in graph.claims}
    props = {item.proposition_id: item for item in propositions.propositions}
    review = next(item for item in graph.claims if item.claim_type == "review_recommendation")
    align = next(item for item in graph.claims if item.claim_type == "technical_alignment")
    focus = next(item for item in graph.claims if item.claim_type == "interview_focus")
    base = {
        "contract_version": "recruiter_narrative_v4", "candidate_id": narrative.candidate_id,
        "result_rank": narrative.result_rank,
        "summary": {"text": "建议安排人工技术复核，确认项目参与范围。", "claim_refs": [review.claim_id]},
        "strengths": [{"text": f"候选材料中的 {align.concepts[0]} 与岗位方向相关。",
                       "claim_refs": [align.claim_id]}],
        "risks": [{"text": "项目范围仍需面试确认。", "claim_refs": [focus.claim_id]}],
        "interview_focus": [{"text": "下一轮可确认项目中的实际参与范围。",
                             "claim_refs": [focus.claim_id]}],
    }
    rows = []
    for field in FIELDS:
        paragraphs = [narrative.decision_summary] if field == "decision_summary" else getattr(narrative, field)
        target, allowed = _LEGACY_ROLES[field]
        for index, item in enumerate(paragraphs):
            sources = {claim_id for ref in item.proposition_refs
                       for claim_id in props[ref].source_claim_ids
                       if claim_id in claims and claims[claim_id].claim_type in allowed}
            row = {"field": field, "item_index": index}
            if not sources or any(not props[ref].source_claim_ids for ref in item.proposition_refs):
                row.update(status="NOT_COMPARABLE", reason="no_equivalent_v4_claim_lineage")
                rows.append(row)
                continue
            payload = {**base, "strengths": list(base["strengths"]),
                       "risks": list(base["risks"]), "interview_focus": list(base["interview_focus"])}
            replacement = {"text": item.text, "claim_refs": sorted(sources)[:4]}
            if target == "summary":
                payload["summary"] = replacement
            else:
                section = target.split("[")[0]
                payload[section] = [replacement]
            bridge = RecruiterNarrativeV4.model_validate(payload)
            validator_reason = diagnose_narrative_v4(bridge, graph=graph).get(target)
            guard_reason = diagnose_narrative_frame_v4_1(bridge, frame=frame, graph=graph).get(target)
            row.update(status="FAIL" if validator_reason or guard_reason else "PASS",
                       validator_reason=validator_reason, guard_reason=guard_reason)
            rows.append(row)
    return rows


def _synthetic_narrative_fields(content: str) -> dict:
    """Retain only synthetic output fields, including rejected schema drafts."""
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return {"parse_status": "FAIL"}
    if not isinstance(payload, dict):
        return {"parse_status": "FAIL"}
    return {"parse_status": "PASS", **{
        field: payload.get(field) for field in FIELDS
    }}


async def main(*, single_smoke: bool = False) -> int:
    settings = Settings()
    selection = resolve_provider_selection(settings, ProviderTask.EXPLANATION)
    if selection.mode is not ProviderMode.OPENAI_COMPATIBLE or selection.model != "qwen3.7-flash-2026-07-15":
        print(json.dumps({"gate": "BLOCKED", "reason": "wrong_runtime_provider_or_model"}))
        return 2
    provider = build_recruiter_narrative_provider(settings)
    failures = 0
    try:
        for group_number in ((1,) if single_smoke else (1, 2, 3)):
            group = build_comparison_group(group_number)
            run = group["run"]
            before = group["ranking_before"]
            for candidate_index, projection in enumerate(group["projections"]):
                if single_smoke and candidate_index > 0:
                    break
                propositions = build_recruiter_propositions_v1(projection)
                binding = build_proposition_binding_v1(propositions)
                request = build_proposition_generation_request_v1(
                    projection, propositions, max_output_tokens=4096)
                record = {
                    "scenario": group["role"], "candidate": "A" if candidate_index == 0 else "B",
                    "candidate_id": projection.candidate_id,
                    "provider": "openai_compatible", "model": selection.model,
                    "proposition_count": len(propositions.propositions),
                    "proposition_catalog": [
                        {"handle": entry.handle, "kind": item.kind, "modality": item.modality,
                         "topics": item.topic_terms, "job_terms": item.job_requirement_terms,
                         "source_fact_count": len(item.source_fact_ids),
                         "source_claim_count": len(item.source_claim_ids)}
                        for entry in binding.entries
                        for item in propositions.propositions if item.proposition_id == entry.proposition_id
                    ],
                    "repair": 0,
                }
                started = time.monotonic()
                try:
                    response = await provider.generate(request)
                    record["http_status"] = response.http_status_code
                    record["provider_narrative"] = _synthetic_narrative_fields(response.content)
                    output = parse_proposition_provider_output_v1(response.content)
                    record["schema"] = "PASS"
                    # Retain every synthetic field even when strict handle
                    # resolution rejects the result; no silent correction.
                    record["provider_narrative"] = output.model_dump(mode="json")
                    record["selected_handles"] = {
                        field: [[handle for handle, selected in item.proposition_handles.items() if selected]
                                for item in
                                ([output.decision_summary] if field == "decision_summary"
                                 else getattr(output, field))]
                        for field in FIELDS
                    }
                    try:
                        narrative = resolve_proposition_output_v1(output, binding)
                    except ValueError as error:
                        record.update(gate="HANDLE_FAIL", handle="FAIL", reason_code=str(error))
                        failures += 1
                    else:
                        record["handle"] = "PASS"
                        record["narrative"] = narrative.model_dump(mode="json")
                        record["legacy_shadow"] = _shadow_rows(narrative, propositions, projection)
                        audit_started = time.monotonic()
                        try:
                            audit_response = await provider.generate(
                                build_blind_semantic_audit_request_v1(
                                    narrative, max_output_tokens=4096))
                            record["audit_http_status"] = audit_response.http_status_code
                            audit_output = BlindNarrativeAuditOutputV1.model_validate_json(
                                audit_response.content)
                            record["audit_schema"] = "PASS"
                            audit_result = evaluate_blind_semantic_audit_v1(
                                audit_output, narrative=narrative, propositions=propositions)
                            record["semantic_audit"] = "PASS" if audit_result.passed else "FAIL"
                            record["semantic_atom_count"] = audit_result.atom_count
                            record["semantic_audit_issues"] = [
                                {"field": issue.field, "item_index": issue.item_index,
                                 "code": issue.code, "quote": issue.quote}
                                for issue in audit_result.issues]
                            record["semantic_atoms"] = [
                                {"field": row.field, "item_index": row.item_index,
                                 "atoms": [atom.model_dump(mode="json") for atom in row.atoms]}
                                for row in audit_output.paragraphs]
                            record["gate"] = "PASS" if audit_result.passed else "SEMANTIC_FAIL"
                            if not audit_result.passed:
                                failures += 1
                        except ExplanationProviderError as error:
                            record.update(gate="AUDIT_PROVIDER_FAIL", audit_provider_category=error.category,
                                          audit_http_status=getattr(error, "status_code", None),
                                          audit_safe_error_code=getattr(error, "provider_error_code", None))
                            failures += 1
                        except (ValidationError, ValueError, TypeError) as error:
                            record.update(gate="AUDIT_SCHEMA_FAIL", audit_schema="FAIL",
                                          audit_error_type=type(error).__name__)
                            failures += 1
                        record["audit_latency_seconds"] = round(time.monotonic() - audit_started, 3)
                except ExplanationProviderError as error:
                    record.update(gate="PROVIDER_FAIL", provider_category=error.category,
                                  http_status=getattr(error, "status_code", None),
                                  safe_error_code=getattr(error, "provider_error_code", None))
                    failures += 1
                except (ValidationError, ValueError, TypeError) as error:
                    record.update(gate="STRUCTURAL_FAIL", error_type=type(error).__name__,
                                  schema=record.get("schema", "FAIL"),
                                  handle=record.get("handle", "NOT_RUN"))
                    failures += 1
                record["latency_seconds"] = round(time.monotonic() - started, 3)
                record["ranking_unchanged"] = (
                    run.result_fingerprint == before["fingerprint"]
                    and [item.candidate_id for item in run.results] == before["order"]
                    and [item.ltr_score_raw for item in run.results] == before["ltr_scores"]
                )
                print(json.dumps(record, ensure_ascii=True, sort_keys=True), flush=True)
                if record["gate"] in {"PROVIDER_FAIL", "AUDIT_PROVIDER_FAIL"}:
                    return 2
    finally:
        await provider.aclose()
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-smoke", action="store_true")
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(main(single_smoke=arguments.single_smoke)))
