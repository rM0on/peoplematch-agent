"""Opt-in, frozen, eight-case synthetic Interview Semantics experiment.

Freeze first, run once after the existing provider health probe. No semantic
retry, artifact overwrite, mock fallback, or in-batch implementation changes.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import time

from pydantic import ValidationError

from app.core.config import Settings
from app.services.explanation.generation.provider import ExplanationProviderError
from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
from app.services.explanation.presentation.generation_proposition_v1 import (
    parse_proposition_provider_output_v1, resolve_proposition_output_v1,
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
from narrative_semantic_intent_v1_live_experiment import (
    _append, _hash_file, _safe_provider_error, _selected_handles,
)
from narrative_v2_comparison_fixture import build_comparison_group


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
PREREG = ROOT / "docs/superpowers/plans/2026-10-07-recruiter-proposition-interview-semantics-next-experiment.md"
SAMPLES = (
    ("ai_agent_a", 1, 0, "development"),
    ("ai_agent_b", 1, 1, "development"),
    ("recommendation_a", 2, 0, "development"),
    ("recommendation_b", 2, 1, "development"),
    ("backend_a", 3, 0, "development"),
    ("backend_b", 3, 1, "development"),
    ("mlops_requirement_holdout", 8, 0, "holdout"),
    ("streaming_data_holdout", 9, 0, "holdout"),
)
SOURCE_FILES = (
    "backend/tests/narrative_interview_semantics_v1_live_experiment.py",
    "backend/tests/narrative_v2_comparison_fixture.py",
    "backend/app/services/explanation/presentation/facts_v2.py",
    "backend/app/services/explanation/presentation/propositions_v1.py",
    "backend/app/services/explanation/presentation/interview_semantics_proposition_v1.py",
    "backend/app/services/explanation/presentation/semantic_intent_proposition_v1.py",
    "backend/app/services/explanation/presentation/generation_proposition_v1.py",
    "backend/app/services/explanation/presentation/semantic_audit_proposition_v1.py",
    "backend/app/services/explanation/generation/openai_compatible.py",
)


def _digest(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _request_digest(request) -> str:
    return _digest({
        "system_instruction": request.system_instruction,
        "user_instruction": request.user_instruction,
        "output_contract_version": request.output_contract_version,
        "max_output_tokens": request.max_output_tokens,
        "response_schema": request.response_schema,
    })


def _cases():
    cases = []
    for sample_id, group_number, index, split in SAMPLES:
        group = build_comparison_group(group_number)
        projection = group["projections"][index]
        propositions = build_recruiter_propositions_for_interview_v1(projection)
        plan = build_semantic_intent_plan_v1(projection, propositions)
        request = build_semantic_intent_generation_request_v1(
            projection, propositions, plan, max_output_tokens=4096)
        cases.append((sample_id, split, group, projection, propositions, plan, request))
    return cases


def _frozen_case(case) -> dict:
    sample_id, split, group, projection, propositions, plan, request = case
    projection_dict = asdict(projection)
    for field in ("positive_refs", "risk_refs", "interview_refs"):
        projection_dict[field] = sorted(projection_dict[field])
    return {
        "sample_id": sample_id, "split": split,
        "role": group["role"], "requirements": group["requirements"],
        "projection_sha256": _digest(projection_dict),
        "propositions_sha256": _digest(propositions.model_dump(mode="json")),
        "intent_sha256": _digest(plan.model_dump(mode="json")),
        "request_sha256": _request_digest(request),
        "ranking_sha256": _digest(group["ranking_before"]),
    }


def _manifest(experiment_id: str) -> dict:
    settings = Settings()
    selection = resolve_provider_selection(settings, ProviderTask.EXPLANATION)
    if selection.mode is not ProviderMode.OPENAI_COMPATIBLE or selection.model != "qwen3.7-flash-2026-07-15":
        raise ValueError("wrong_runtime_provider_or_model")
    return {
        "record_type": "freeze_manifest", "experiment_id": experiment_id,
        "prior_batches": "archived_unchanged",
        "previous_experiment": "interview_semantics_phase2_20261007T1503Z",
        "previous_status": "BLOCKED_BY_TRANSPORT", "provider": "openai_compatible",
        "model": selection.model, "repair_enabled": False,
        "generation_calls_budget": 8, "audit_calls_budget": 8,
        "stop_rule": "infrastructure_or_protocol_failure_stops;semantic_failure_continues",
        "prereg_sha256": _hash_file(PREREG),
        "source_sha256": {path: _hash_file(ROOT / path) for path in SOURCE_FILES},
        "archived_refinement_sha256": _hash_file(
            FIXTURES / "recruiter_proposition_phase2_final_refinement_20261007T1335Z.jsonl"),
        "archived_refinement_gold_sha256": _hash_file(
            FIXTURES / "recruiter_proposition_phase2_final_refinement_gold_v1.json"),
        "cases": [_frozen_case(case) for case in _cases()],
    }


def freeze(experiment_id: str) -> Path:
    path = FIXTURES / f"{experiment_id}.manifest.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(_manifest(experiment_id), stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return path


async def run(experiment_id: str) -> int:
    manifest_path = FIXTURES / f"{experiment_id}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if _digest(manifest) != _digest(_manifest(experiment_id)):
        print("BLOCKED: freeze manifest, fixture, request, or implementation changed", flush=True)
        return 2
    output_path = FIXTURES / f"{experiment_id}.jsonl"
    provider = build_recruiter_narrative_provider(Settings())
    with output_path.open("x", encoding="utf-8") as stream:
        _append(stream, {"record_type": "manifest", "experiment_id": experiment_id,
                         "freeze_manifest_sha256": _hash_file(manifest_path),
                         "model": manifest["model"], "sample_ids": [x["sample_id"] for x in manifest["cases"]]})
        try:
            for case in _cases():
                sample_id, split, group, projection, propositions, plan, request = case
                run_snapshot = group["run"]
                before = group["ranking_before"]
                record = {
                    "record_type": "case", "scenario_id": sample_id, "split": split,
                    "role": group["role"], "candidate_id": projection.candidate_id,
                    "result_rank": projection.result_rank, "run_id": run_snapshot.run_id,
                    "provider": "openai_compatible", "model": manifest["model"],
                    "repair": 0, "schema": "NOT_RUN", "handle": "NOT_RUN", "audit": "NOT_RUN",
                    "request_sha256": _request_digest(request),
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
                    run_snapshot.result_fingerprint == before["fingerprint"]
                    and [item.candidate_id for item in run_snapshot.results] == before["order"]
                    and [item.ltr_score_raw for item in run_snapshot.results] == before["ltr_scores"])
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
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("freeze", "run"))
    parser.add_argument("experiment_id")
    args = parser.parse_args()
    if args.operation == "freeze":
        print(freeze(args.experiment_id))
    else:
        raise SystemExit(asyncio.run(run(args.experiment_id)))
