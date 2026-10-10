"""Opt-in final Phase 2 triage experiment; never part of product runtime.

Freeze first, then run exactly one generation per case. A case_started marker
without case_result is ambiguous and is never retried automatically.
"""

from __future__ import annotations

import asyncio
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

from pydantic import ValidationError

from app.core.config import Settings
from app.services.explanation.generation.provider import ExplanationProviderError
from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
from app.services.explanation.presentation.generation_proposition_v1 import (
    FIELDS, parse_proposition_provider_output_v1,
)
from app.services.explanation.presentation.propositions_v1 import build_recruiter_propositions_v1
from app.services.explanation.presentation.semantic_audit_proposition_v1 import (
    BlindNarrativeAuditOutputV1, build_blind_semantic_audit_request_v1,
    evaluate_blind_semantic_audit_v1,
)
from app.services.explanation.presentation.triage_generation_proposition_v1 import (
    build_triage_generation_request_v1, build_triage_intent_plan_v1,
    resolve_triage_output_v1,
)
from app.services.llm.configuration import ProviderMode, ProviderTask, resolve_provider_selection
from narrative_proposition_v1_live_experiment import _shadow_rows
from narrative_triage_holdout_fixture import build_triage_holdout
from narrative_v2_comparison_fixture import build_comparison_group


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
PREREG = ROOT / "docs/superpowers/plans/2026-10-08-recruiter-phase2-final-convergence.md"
MODEL = "qwen3.7-flash-2026-07-15"
SAMPLES = (
    ("ai_agent_a", "development", 1, 0),
    ("ai_agent_b", "development", 1, 1),
    ("recommendation_a", "development", 2, 0),
    ("recommendation_b", "development", 2, 1),
    ("backend_a", "development", 3, 0),
    ("backend_b", "development", 3, 1),
    ("workflow_automation_holdout", "holdout", None, 0),
    ("geospatial_ml_holdout", "holdout", None, 0),
)


def canonical_hash(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _artifact_paths(experiment_id: str) -> tuple[Path, Path]:
    if not experiment_id.startswith("triage_phase2_final_") or not experiment_id.replace("_", "").isalnum():
        raise ValueError("invalid_experiment_id")
    return (FIXTURES / f"{experiment_id}.manifest.json",
            FIXTURES / f"{experiment_id}.jsonl")


def build_frozen_cases() -> list[dict]:
    cases = []
    for scenario_id, split, group_number, index in SAMPLES:
        group = (build_comparison_group(group_number) if group_number is not None
                 else build_triage_holdout(scenario_id))
        projection = group["projections"][index]
        propositions = build_recruiter_propositions_v1(projection)
        plan = build_triage_intent_plan_v1(projection, propositions)
        request = build_triage_generation_request_v1(
            projection, propositions, plan, max_output_tokens=2048)
        cases.append({
            "scenario_id": scenario_id, "split": split, "group": group,
            "projection": projection, "propositions": propositions,
            "plan": plan, "request": request,
        })
    return cases


def build_manifest(experiment_id: str, cases: list[dict]) -> dict:
    source = ROOT / "backend/app/services/explanation/presentation"
    return {
        "experiment_id": experiment_id, "status": "FROZEN", "provider": "openai_compatible",
        "model": MODEL, "generation_budget": len(cases), "repair_enabled": False,
        "samples": [case["scenario_id"] for case in cases],
        "prereg_sha256": _file_hash(PREREG),
        "fixture_sha256": canonical_hash({
            "comparison": _file_hash(Path(__file__).parent / "narrative_v2_comparison_fixture.py"),
            "holdout": _file_hash(Path(__file__).parent / "narrative_triage_holdout_fixture.py"),
        }),
        "implementation_sha256": canonical_hash({
            "triage": _file_hash(source / "triage_generation_proposition_v1.py"),
            "propositions": _file_hash(source / "propositions_v1.py"),
            "intent_contract": _file_hash(source / "semantic_intent_proposition_v1.py"),
            "handle_schema": _file_hash(source / "generation_proposition_v1.py"),
            "runner": _file_hash(Path(__file__)),
        }),
        "recovered_result_sha256": _file_hash(
            FIXTURES / "recruiter_proposition_phase2_semantic_intent_recovered_20261007T0858Z.jsonl"),
        "recovered_gold_sha256": _file_hash(
            FIXTURES / "recruiter_proposition_phase2_semantic_intent_recovered_gold_v1.json"),
        "cases": [{
            "scenario_id": case["scenario_id"], "split": case["split"],
            "candidate_id": case["projection"].candidate_id,
            "run_id": case["group"]["run"].run_id,
            "ranking_fingerprint": case["group"]["ranking_before"]["fingerprint"],
            "proposition_sha256": canonical_hash(case["propositions"].model_dump(mode="json")),
            "plan_sha256": canonical_hash(case["plan"].model_dump(mode="json")),
            "request_sha256": canonical_hash({
                "system": case["request"].system_instruction,
                "user": case["request"].user_instruction,
                "schema": case["request"].response_schema,
                "tokens": case["request"].max_output_tokens,
            }),
        } for case in cases],
    }


def verify_manifest(recorded: dict, expected: dict) -> bool:
    if canonical_hash(recorded) != canonical_hash(expected):
        raise ValueError("manifest_changed")
    return True


def verify_record_sequence(records: list[dict], case_ids: list[str]) -> tuple[str, ...]:
    completed = []
    started = None
    for record in records:
        kind = record.get("record_type")
        case_id = record.get("scenario_id")
        if kind == "case_started":
            if started is not None:
                raise ValueError("ambiguous_interrupted_attempt")
            if case_id in completed:
                raise ValueError("duplicate_case")
            if len(completed) >= len(case_ids) or case_id != case_ids[len(completed)]:
                raise ValueError("case_order_changed")
            started = case_id
        elif kind == "case_result":
            if started != case_id:
                raise ValueError("case_result_without_start")
            completed.append(case_id)
            started = None
        elif kind in {"audit_started", "audit_result"}:
            if case_id not in completed:
                raise ValueError("audit_before_case_result")
        else:
            raise ValueError("unknown_experiment_record")
    if started is not None:
        raise ValueError("ambiguous_interrupted_attempt")
    return tuple(completed)


def _append(stream, record: dict) -> None:
    stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    stream.flush()


def _read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def freeze(experiment_id: str) -> dict:
    manifest_path, artifact_path = _artifact_paths(experiment_id)
    if manifest_path.exists() or artifact_path.exists():
        raise ValueError("experiment_already_exists")
    cases = build_frozen_cases()
    manifest = build_manifest(experiment_id, cases)
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    with artifact_path.open("x", encoding="utf-8"):
        pass
    return manifest


def _checked_state(experiment_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    manifest_path, artifact_path = _artifact_paths(experiment_id)
    cases = build_frozen_cases()
    expected = build_manifest(experiment_id, cases)
    recorded = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_manifest(recorded, expected)
    records = _read_records(artifact_path)
    verify_record_sequence(records, [case["scenario_id"] for case in cases])
    return cases, recorded, records


def _safe_error(error: ExplanationProviderError) -> dict:
    return {"category": error.category,
            "http_status": getattr(error, "status_code", None),
            "provider_error_code": getattr(error, "provider_error_code", None)}


def _runtime_provider(settings: Settings):
    selection = resolve_provider_selection(settings, ProviderTask.EXPLANATION)
    if selection.mode is not ProviderMode.OPENAI_COMPATIBLE or selection.model != MODEL:
        raise ValueError("wrong_provider_or_model")
    return build_recruiter_narrative_provider(settings)


async def run(experiment_id: str) -> int:
    cases, _, records = _checked_state(experiment_id)
    completed = verify_record_sequence(records, [case["scenario_id"] for case in cases])
    if len(completed) == len(cases):
        raise ValueError("experiment_already_complete")
    provider = _runtime_provider(Settings())
    _, artifact_path = _artifact_paths(experiment_id)
    try:
        with artifact_path.open("a", encoding="utf-8") as stream:
            for case in cases[len(completed):]:
                scenario_id = case["scenario_id"]
                _append(stream, {"record_type": "case_started", "scenario_id": scenario_id,
                                 "request_sha256": canonical_hash({
                                     "system": case["request"].system_instruction,
                                     "user": case["request"].user_instruction,
                                     "schema": case["request"].response_schema,
                                     "tokens": case["request"].max_output_tokens,
                                 })})
                record = {
                    "record_type": "case_result", "scenario_id": scenario_id,
                    "split": case["split"], "model": MODEL,
                    "candidate_id": case["projection"].candidate_id,
                    "result_rank": case["projection"].result_rank,
                    "role": case["group"]["role"],
                    "run_id": case["group"]["run"].run_id,
                    "propositions": [p.model_dump(mode="json") for p in case["propositions"].propositions],
                    "intent_plan": case["plan"].model_dump(mode="json"),
                    "ranking_before": case["group"]["ranking_before"],
                    "schema": "NOT_RUN", "handle": "NOT_RUN", "repair": 0,
                }
                started = time.monotonic()
                stop = False
                try:
                    response = await provider.generate(case["request"])
                    record["http_status"] = response.http_status_code
                    output = parse_proposition_provider_output_v1(response.content)
                    record["schema"] = "PASS"
                    record["selected_handles"] = {
                        field: [list(item.proposition_handles) for item in
                                ([output.decision_summary] if field == "decision_summary"
                                 else getattr(output, field))] for field in FIELDS
                    }
                    narrative = resolve_triage_output_v1(
                        output, case["propositions"], case["plan"])
                    record["handle"] = "PASS"
                    record["narrative"] = narrative.model_dump(mode="json")
                    try:
                        record["legacy_shadow"] = _shadow_rows(
                            narrative, case["propositions"], case["projection"])
                    except (ValueError, StopIteration) as error:
                        record["legacy_shadow"] = {
                            "status": "NOT_COMPARABLE", "error_type": type(error).__name__}
                    record["gate"] = "STRUCTURAL_PASS"
                except ExplanationProviderError as error:
                    record.update(gate="PROVIDER_FAIL", provider_error=_safe_error(error))
                    stop = True
                except (ValidationError, ValueError, TypeError) as error:
                    record.update(gate="STRUCTURAL_FAIL", error_type=type(error).__name__)
                    stop = True
                record["generation_latency_seconds"] = round(time.monotonic() - started, 3)
                run_snapshot = case["group"]["run"]
                before = case["group"]["ranking_before"]
                record["ranking_unchanged"] = (
                    run_snapshot.result_fingerprint == before["fingerprint"]
                    and [item.candidate_id for item in run_snapshot.results] == before["order"]
                    and [item.ltr_score_raw for item in run_snapshot.results] == before["ltr_scores"])
                _append(stream, record)
                print(f"{scenario_id}: {record['gate']} schema={record['schema']} "
                      f"handle={record['handle']} latency={record['generation_latency_seconds']}s", flush=True)
                if stop:
                    return 2
    finally:
        await provider.aclose()
    return 0


async def audit(experiment_id: str) -> int:
    cases, _, records = _checked_state(experiment_id)
    results = {item["scenario_id"]: item for item in records if item["record_type"] == "case_result"}
    if len(results) != len(cases) or any(item.get("gate") != "STRUCTURAL_PASS" for item in results.values()):
        raise ValueError("audit_requires_complete_structural_batch")
    audited = {item["scenario_id"] for item in records if item["record_type"] == "audit_started"}
    provider = _runtime_provider(Settings())
    _, artifact_path = _artifact_paths(experiment_id)
    try:
        with artifact_path.open("a", encoding="utf-8") as stream:
            for case in cases:
                scenario_id = case["scenario_id"]
                if scenario_id in audited:
                    continue
                _append(stream, {"record_type": "audit_started", "scenario_id": scenario_id})
                from app.services.explanation.presentation.generation_proposition_v1 import ResolvedPropositionNarrativeV1
                narrative = ResolvedPropositionNarrativeV1.model_validate(results[scenario_id]["narrative"])
                started = time.monotonic()
                record = {"record_type": "audit_result", "scenario_id": scenario_id}
                try:
                    response = await provider.generate(build_blind_semantic_audit_request_v1(
                        narrative, max_output_tokens=4096))
                    parsed = BlindNarrativeAuditOutputV1.model_validate_json(response.content)
                    evaluation = evaluate_blind_semantic_audit_v1(
                        parsed, narrative=narrative, propositions=case["propositions"])
                    record.update(status="PASS" if evaluation.passed else "FAIL",
                                  http_status=response.http_status_code,
                                  issues=[{"field": issue.field, "item_index": issue.item_index,
                                           "code": issue.code, "quote": issue.quote}
                                          for issue in evaluation.issues],
                                  atoms=[{"field": para.field, "item_index": para.item_index,
                                          "atoms": [atom.model_dump(mode="json") for atom in para.atoms]}
                                         for para in parsed.paragraphs])
                except ExplanationProviderError as error:
                    record.update(status="PROVIDER_FAIL", provider_error=_safe_error(error))
                except (ValidationError, ValueError, TypeError) as error:
                    record.update(status="AUDIT_FAIL", error_type=type(error).__name__)
                record["latency_seconds"] = round(time.monotonic() - started, 3)
                _append(stream, record)
                print(f"audit {scenario_id}: {record['status']}", flush=True)
    finally:
        await provider.aclose()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in {"freeze", "run", "audit"}:
        raise SystemExit("usage: narrative_triage_final_live_experiment.py freeze|run|audit EXPERIMENT_ID")
    command, selected_id = sys.argv[1:]
    if command == "freeze":
        print(json.dumps(freeze(selected_id), ensure_ascii=False, sort_keys=True), flush=True)
    elif command == "run":
        raise SystemExit(asyncio.run(run(selected_id)))
    else:
        raise SystemExit(asyncio.run(audit(selected_id)))
