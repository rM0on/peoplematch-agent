"""Opt-in, preregistered eight-case synthetic semantic-intent refinement.

One generation and at most one blind audit per case. The script creates its
output exclusively, so an interrupted run is retained, never overwritten.
No product runtime uses this module.
"""

from __future__ import annotations

import asyncio
from hashlib import sha256
import json
from pathlib import Path
import time

from pydantic import ValidationError

from app.core.config import Settings
from app.services.explanation.generation.provider import ExplanationProviderError
from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
from app.services.explanation.presentation.generation_proposition_v1 import (
    FIELDS, parse_proposition_provider_output_v1,
    resolve_proposition_output_v1,
)
from app.services.explanation.presentation.propositions_v1 import build_recruiter_propositions_for_interview_v1
from app.services.explanation.presentation.semantic_audit_proposition_v1 import (
    BlindNarrativeAuditOutputV1, build_blind_semantic_audit_request_v1,
    evaluate_blind_semantic_audit_v1,
)
from app.services.explanation.presentation.semantic_intent_proposition_v1 import (
    build_semantic_intent_binding_v1, build_semantic_intent_generation_request_v1,
    build_semantic_intent_plan_v1,
)
from app.services.llm.configuration import ProviderMode, ProviderTask, resolve_provider_selection
from narrative_proposition_v1_live_experiment import _shadow_rows, _synthetic_narrative_fields
from narrative_v2_comparison_fixture import build_comparison_group


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = (Path(__file__).parent / "fixtures"
          / "recruiter_proposition_phase2_final_refinement_20261007T1335Z.jsonl")
PREREG = (ROOT / "docs" / "superpowers" / "plans"
          / "2026-10-07-recruiter-proposition-phase2-final-refinement.md")
SAMPLES = (
    ("ai_agent_a", 1, 0, "development"),
    ("ai_agent_b", 1, 1, "development"),
    ("recommendation_a", 2, 0, "development"),
    ("recommendation_b", 2, 1, "development"),
    ("backend_a", 3, 0, "development"),
    ("backend_b", 3, 1, "development"),
    ("data_search_holdout", 6, 0, "holdout"),
    ("vision_api_holdout", 7, 0, "holdout"),
)


def _hash_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _append(stream, record: dict) -> None:
    stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    stream.flush()


def _safe_provider_error(error: ExplanationProviderError) -> dict:
    return {
        "safe_category": error.category,
        "http_status": getattr(error, "status_code", None),
        "safe_error_code": getattr(error, "provider_error_code", None),
    }


def _selected_handles(output) -> dict:
    return {
        field: [list(item.proposition_handles) for item in
                ([output.decision_summary] if field == "decision_summary" else getattr(output, field))]
        for field in FIELDS
    }


async def main(*, output_path: Path = OUTPUT,
               experiment_id: str = "semantic_intent_final_refinement_20261007T1335Z") -> int:
    settings = Settings()
    selection = resolve_provider_selection(settings, ProviderTask.EXPLANATION)
    if selection.mode is not ProviderMode.OPENAI_COMPATIBLE or selection.model != "qwen3.7-flash-2026-07-15":
        print("BLOCKED: wrong runtime provider or model", flush=True)
        return 2
    cases = []
    for sample_id, group_number, index, split in SAMPLES:
        group = build_comparison_group(group_number)
        projection = group["projections"][index]
        propositions = build_recruiter_propositions_for_interview_v1(projection)
        plan = build_semantic_intent_plan_v1(projection, propositions)
        request = build_semantic_intent_generation_request_v1(
            projection, propositions, plan, max_output_tokens=4096)
        cases.append((sample_id, split, group, projection, propositions, plan, request))
    if output_path.exists():
        print("BLOCKED: experiment artifact already exists; never overwrite or resample", flush=True)
        return 2
    manifest = {
        "record_type": "manifest", "experiment": experiment_id,
        "previous_batch": ("BLOCKED_BY_TRANSPORT"
                           if experiment_id != "semantic_intent_v1_phase2" else None),
        "preregistered_samples": [entry[0] for entry in cases],
        "provider": "openai_compatible", "model": selection.model,
        "generation_calls_budget": len(cases), "audit_calls_budget": len(cases),
        "repair_enabled": False,
        "archived_gold_sha256": _hash_file(Path(__file__).parent / "fixtures"
                                              / "recruiter_proposition_phase2_semantic_gold_v1.json"),
        "recovered_result_sha256": _hash_file(Path(__file__).parent / "fixtures"
                                                 / "recruiter_proposition_phase2_semantic_intent_recovered_20261007T0858Z.jsonl"),
        "recovered_gold_sha256": _hash_file(Path(__file__).parent / "fixtures"
                                               / "recruiter_proposition_phase2_semantic_intent_recovered_gold_v1.json"),
        "prereg_sha256": _hash_file(PREREG),
        "intent_source_sha256": _hash_file(ROOT / "backend" / "app" / "services" / "explanation"
                                              / "presentation" / "semantic_intent_proposition_v1.py"),
        "old_generation_source_sha256": _hash_file(ROOT / "backend" / "app" / "services"
                                                      / "explanation" / "presentation"
                                                      / "generation_proposition_v1.py"),
    }
    provider = build_recruiter_narrative_provider(settings)
    with output_path.open("x", encoding="utf-8") as stream:
        _append(stream, manifest)
        try:
            for sample_id, split, group, projection, propositions, plan, request in cases:
                run = group["run"]
                before = group["ranking_before"]
                record = {
                    "record_type": "case", "scenario_id": sample_id, "split": split,
                    "role": group["role"], "candidate_id": projection.candidate_id,
                    "result_rank": projection.result_rank, "run_id": run.run_id,
                    "provider": "openai_compatible", "model": selection.model,
                    "repair": 0, "schema": "NOT_RUN", "handle": "NOT_RUN",
                    "audit": "NOT_RUN", "request_sha256": sha256(
                        request.user_instruction.encode("utf-8")).hexdigest(),
                    "intent_plan": plan.model_dump(mode="json"),
                    "propositions": [p.model_dump(mode="json") for p in propositions.propositions],
                    "evidence_terms": {ref: list(projection.facts[ref]) for p in propositions.propositions
                                       for ref in p.evidence_refs if ref in projection.facts},
                    "ranking_before": before,
                }
                binding = build_semantic_intent_binding_v1(propositions, plan)
                started = time.monotonic()
                stop = False
                try:
                    response = await provider.generate(request)
                    record["http_status"] = response.http_status_code
                    record["provider_narrative"] = _synthetic_narrative_fields(response.content)
                    output = parse_proposition_provider_output_v1(response.content)
                    record["schema"] = "PASS"
                    record["provider_narrative"] = output.model_dump(mode="json")
                    record["selected_handles"] = _selected_handles(output)
                    narrative = resolve_proposition_output_v1(output, binding)
                    record["handle"] = "PASS"
                    record["narrative"] = narrative.model_dump(mode="json")
                    try:
                        record["legacy_shadow"] = _shadow_rows(narrative, propositions, projection)
                    except (ValueError, StopIteration) as error:
                        record["legacy_shadow"] = {"status": "NOT_COMPARABLE",
                                                   "error_type": type(error).__name__}
                    audit_started = time.monotonic()
                    try:
                        audit_response = await provider.generate(
                            build_blind_semantic_audit_request_v1(narrative, max_output_tokens=4096))
                        record["audit_http_status"] = audit_response.http_status_code
                        audit_output = BlindNarrativeAuditOutputV1.model_validate_json(audit_response.content)
                        audit_result = evaluate_blind_semantic_audit_v1(
                            audit_output, narrative=narrative, propositions=propositions)
                        record["audit"] = "PASS" if audit_result.passed else "FAIL"
                        record["audit_issues"] = [
                            {"field": x.field, "item_index": x.item_index, "code": x.code, "quote": x.quote}
                            for x in audit_result.issues]
                        record["audit_atoms"] = [
                            {"field": x.field, "item_index": x.item_index,
                             "atoms": [atom.model_dump(mode="json") for atom in x.atoms]}
                            for x in audit_output.paragraphs]
                    except ExplanationProviderError as error:
                        record.update(gate="AUDIT_PROVIDER_FAIL", audit_provider_error=_safe_provider_error(error))
                        stop = True
                    except (ValidationError, ValueError, TypeError) as error:
                        record.update(gate="AUDIT_SCHEMA_FAIL", audit_error_type=type(error).__name__)
                        stop = True
                    record["audit_latency_seconds"] = round(time.monotonic() - audit_started, 3)
                    if not stop:
                        record["gate"] = "STRUCTURAL_PASS"
                except ExplanationProviderError as error:
                    record.update(gate="PROVIDER_FAIL", provider_error=_safe_provider_error(error))
                    stop = True
                except (ValidationError, ValueError, TypeError) as error:
                    record.update(gate="STRUCTURAL_FAIL", structural_error_type=type(error).__name__)
                    stop = True
                record["generation_plus_audit_latency_seconds"] = round(time.monotonic() - started, 3)
                record["generation_latency_seconds"] = round(
                    record["generation_plus_audit_latency_seconds"] - record.get("audit_latency_seconds", 0), 3)
                record["ranking_unchanged"] = (
                    run.result_fingerprint == before["fingerprint"]
                    and [item.candidate_id for item in run.results] == before["order"]
                    and [item.ltr_score_raw for item in run.results] == before["ltr_scores"])
                _append(stream, record)
                print(f"{sample_id}: {record['gate']} schema={record['schema']} handle={record['handle']} "
                      f"audit={record['audit']} latency={record['generation_plus_audit_latency_seconds']}s",
                      flush=True)
                if stop:
                    return 2
        finally:
            await provider.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
