"""Opt-in, one-shot Fresh Top-3 trusted-chain validation; no Narrative call.

Run only against the existing local application with synthetic candidate data.
Every stage is appended to a new artifact. This script never resumes or retries.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import httpx


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "fresh_top3_trusted_jd_20261009.txt"
ARTIFACTS = ROOT / "tests" / "fixtures"
MODEL = "qwen3.7-flash-2026-07-15"
# Existing frozen sandbox cohort; excludes mock-parsed and user-created records.
COHORT_FILTERS = {"cities": ["Beijing"], "seniorities": ["mid"]}
IMPLEMENTATION = (
    ROOT / "app" / "api" / "dependencies.py",
    ROOT / "app" / "api" / "router.py",
    ROOT / "app" / "api" / "routes" / "recruiter_propositions.py",
    ROOT / "app" / "services" / "explanation" / "presentation" / "structured_service.py",
    ROOT / "app" / "services" / "explanation" / "presentation" / "propositions_v1.py",
    ROOT / "app" / "services" / "explanation" / "presentation" / "adapter.py",
    ROOT / "app" / "services" / "explanation" / "presentation" / "contracts_proposition_v1.py",
    ROOT / "app" / "schemas" / "recruiter_proposition.py",
    ROOT / "app" / "services" / "explanation" / "generation" / "semantic_selection.py",
    ROOT / "app" / "services" / "explanation" / "generation" / "reference_projection.py",
    ROOT / "app" / "services" / "explanation" / "generation" / "pipeline.py",
    ROOT / "app" / "services" / "explanation" / "generation" / "grounding.py",
    ROOT / "app" / "services" / "explanation" / "generation" / "prompts" / "explanation_prompt_v4.txt",
    Path(__file__).resolve(),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def health_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/health"


def _append(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as target:
        target.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def _safe_error_code(response: httpx.Response) -> str | None:
    try:
        value = response.json().get("error", {}).get("code")
    except (ValueError, AttributeError, TypeError):
        return None
    return value if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,79}", value) else None


async def _request(client: httpx.AsyncClient, method: str, path: str, *, payload=None) -> dict:
    response = await client.request(method, path, json=payload, timeout=300)
    if response.status_code >= 400:
        raise StageFailure(f"application_http_{response.status_code}", _safe_error_code(response))
    envelope = response.json()
    if envelope.get("success") is not True or not isinstance(envelope.get("data"), dict):
        raise StageFailure("application_response_invalid")
    return envelope["data"]


class StageFailure(Exception):
    def __init__(self, code: str, provider_code: str | None = None) -> None:
        self.code = code
        self.provider_code = provider_code
        super().__init__(code)


def _validate_candidate_cohort(items: list[dict]) -> tuple[tuple[str, ...], str]:
    ids = [item["candidate_id"] for item in items]
    if len(ids) != len(set(ids)):
        raise StageFailure("candidate_pool_duplicate")
    if len(ids) < 3:
        raise StageFailure("candidate_pool_too_small")
    for item in items:
        if (item["data_origin"] != "synthetic_sandbox"
                or item["dataset_version"] != "1.0.0"):
            raise StageFailure("candidate_pool_non_synthetic")
        if (item["seniority"] != "mid"
                or "Beijing" not in item["preferred_locations"]["cities"]):
            raise StageFailure("candidate_pool_filter_mismatch")
    return tuple(sorted(ids)), _fingerprint(sorted(items, key=lambda item: item["candidate_id"]))


def _candidate_record_hashes(items: list[dict]) -> dict[str, str]:
    return {item["candidate_id"]: _fingerprint(item)
            for item in sorted(items, key=lambda item: item["candidate_id"])}


async def _candidate_pool(client: httpx.AsyncClient) -> tuple[tuple[str, ...], str, dict[str, str]]:
    items = []
    offset = 0
    while True:
        page = await _request(client, "GET", f"/candidates?limit=100&offset={offset}"
                              "&seniority=mid&city=Beijing")
        batch = page["items"]
        items.extend(batch)
        offset += len(batch)
        if offset >= page["total"]:
            break
        if not batch:
            raise StageFailure("candidate_pool_pagination_invalid")
    ids, aggregate_hash = _validate_candidate_cohort(items)
    return ids, aggregate_hash, _candidate_record_hashes(items)


def _snapshot(run: dict) -> dict:
    return {
        "order": [item["candidate_id"] for item in run["results"]],
        "ltr_scores": [item["ltr_score_raw"] for item in run["results"]],
        "ranking_fingerprint": run["result_fingerprint"],
    }


def _check_explanation_readback(detail: dict, expected: list[dict]) -> tuple[int, ...]:
    actual = detail.get("explanations", [])
    if (detail.get("status") != "COMPLETED" or detail.get("explanation_count") != len(expected)
            or len(actual) != len(expected)):
        raise StageFailure("explanation_persistence_readback_mismatch")
    for item, result in zip(actual, expected):
        if any(item.get(key) != result.get(key) for key in (
                "match_explanation_id", "candidate_id", "result_rank")):
            raise StageFailure("explanation_persistence_readback_mismatch")
        rank = item["result_rank"]
        allowed = (f"candidate:{rank}:", f"feature:{rank}:", f"ranking:{rank}:",
                   f"retrieval:{rank}:", f"diagnostic:{rank}:", f"comparison:{rank}:",
                   "job_requirement:")
        pending = [item]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                for name, value in node.items():
                    if name == "evidence_refs" and isinstance(value, list):
                        if any(not isinstance(ref, str) or not ref.startswith(allowed)
                               for ref in value):
                            raise StageFailure("explanation_cross_candidate_reference")
                    else:
                        pending.append(value)
            elif isinstance(node, list):
                pending.extend(node)
    return tuple(item["match_explanation_id"] for item in actual)


def _check_brief(brief: dict, result: dict, run: dict, explanation_id: int) -> dict:
    if (brief["match_run_id"] != run["run_id"]
            or brief["ranking_fingerprint"] != run["result_fingerprint"]
            or brief["source_explanation_id"] != explanation_id
            or brief["candidate_id"] != result["candidate_id"]
            or brief["result_rank"] != result["result_rank"]
            or brief["review_status"] != "TRUSTED_STRUCTURED"):
        raise StageFailure("structured_brief_identity_or_ranking_mismatch")
    if not all(brief[name] for name in (
        "review_action", "why_review", "technical_signals", "unknowns", "verification_targets",
    )):
        raise StageFailure("structured_brief_required_role_missing")
    propositions = [brief["review_action"], *brief["why_review"], *brief["technical_signals"],
                    *brief["unknowns"], *brief["verification_targets"]]
    owner = f"candidate:{result['result_rank']}:"
    for item in propositions:
        if (item["candidate_id"] != result["candidate_id"]
                or item["result_rank"] != result["result_rank"]
                or not item["source_fact_ids"] or not item["evidence_refs"]):
            raise StageFailure("structured_brief_provenance_invalid")
        if any(not ref.startswith((owner, "job_requirement:")) for ref in item["evidence_refs"]):
            raise StageFailure("structured_brief_cross_candidate_reference")
    if (brief["review_action"]["kind"] != "human_review_recommendation"
            or any(item["modality"] != "alignment" for item in brief["why_review"])
            or any(item["modality"] != "unknown" or item["polarity"] != "undetermined"
                   for item in brief["unknowns"])
            or any(item["modality"] != "hypothesis" for item in brief["verification_targets"])):
        raise StageFailure("structured_brief_semantic_role_invalid")
    return {
        "candidate_id": result["candidate_id"], "result_rank": result["result_rank"],
        "review_action": brief["review_action"]["predicate"],
        "proposition_count": len(propositions), "brief": brief,
    }


async def run(experiment_id: str, base_url: str) -> None:
    if not re.fullmatch(r"fresh_top3_trusted_[A-Za-z0-9_]{8,64}", experiment_id):
        raise StageFailure("experiment_id_invalid")
    manifest_path = ARTIFACTS / f"{experiment_id}.manifest.json"
    artifact_path = ARTIFACTS / f"{experiment_id}.jsonl"
    if manifest_path.exists() or artifact_path.exists():
        raise StageFailure("experiment_artifact_exists_no_rerun")
    jd = FIXTURE.read_text(encoding="utf-8")
    async with httpx.AsyncClient(base_url=base_url.rstrip("/") + "/api/v1",
                                 trust_env=False, timeout=300) as client:
        health = await client.get(health_url(base_url), timeout=15)
        if health.status_code != 200:
            raise StageFailure("backend_health_unavailable")
        status = await _request(client, "GET", "/system/ai-provider-status")
        modes = {task: (status[task]["mode"], status[task]["configured_model"])
                 for task in ("extraction", "explanation")}
        if any(mode != ("openai_compatible", MODEL) for mode in modes.values()):
            raise StageFailure("real_provider_model_mismatch")
        pool, pool_record_hash, candidate_record_hashes = await _candidate_pool(client)
        manifest = {
            "experiment_id": experiment_id, "status": "FROZEN_BEFORE_PROVIDER",
            "synthetic_fixture_sha256": _sha(FIXTURE), "candidate_pool_count": len(pool),
            "candidate_pool_ids": pool,
            "candidate_pool_ids_sha256": _fingerprint(pool),
            "candidate_pool_records_sha256": pool_record_hash,
            "candidate_record_sha256": candidate_record_hashes,
            "candidate_cohort_filters": COHORT_FILTERS,
            "provider_modes": modes, "ranking_variant": "ltr", "top_k": 3,
            "candidate_pool_k": 20, "narrative_draft": "NOT_RUN",
            "implementation_sha256": {str(path.relative_to(ROOT)): _sha(path) for path in IMPLEMENTATION},
            "request_sha256": _fingerprint({"jd": jd, "persist": True, "ranking_variant": "ltr",
                                             "top_k": 3, "candidate_pool_k": 20,
                                             "filters": COHORT_FILTERS}),
        }
        with manifest_path.open("x", encoding="utf-8") as target:
            json.dump(manifest, target, sort_keys=True, indent=2)
            target.write("\n")
        artifact_path.open("x", encoding="utf-8").close()
        _append(artifact_path, {"stage": "started", "experiment_id": experiment_id,
                                "at_utc": datetime.now(timezone.utc).isoformat()})
        stage = "extraction"
        try:
            extracted = await _request(client, "POST", "/jobs/parse", payload={"text": jd, "persist": True})
            record = extracted["record"]
            if record is None or extracted["extraction"]["provider_kind"] != "openai_compatible":
                raise StageFailure("real_extraction_not_persisted")
            _append(artifact_path, {"stage": stage, "status": "PASS", "job_id": record["job_id"],
                                    "role_title": record["role_title"],
                                    "must_have": [item["text"] for item in record["must_have"]],
                                    "nice_to_have": [item["text"] for item in record["nice_to_have"]],
                                    "provider_kind": extracted["extraction"]["provider_kind"],
                                    "attempts": extracted["extraction"]["attempts"],
                                    "repaired": extracted["extraction"]["repaired"]})
            stage = "match_run"
            run = await _request(client, "POST", "/match-runs", payload={
                "job_id": record["job_id"], "ranking_variant": "ltr",
                "candidate_pool_k": 20, "top_k": 3, "filters": COHORT_FILTERS,
            })
            if run["status"] != "COMPLETED" or len(run["results"]) != 3:
                raise StageFailure("fresh_match_run_not_top3")
            if any(item["candidate_id"] not in pool for item in run["results"]):
                raise StageFailure("ranked_candidate_outside_synthetic_cohort")
            before = _snapshot(run)
            _append(artifact_path, {"stage": stage, "status": "PASS", "run_id": run["run_id"],
                                    "snapshot": before, "retrieval_provenance": run["retrieval_provenance"],
                                    "feature_version": run["feature_version"],
                                    "feature_fingerprint": run["feature_fingerprint"],
                                    "ranker_version": run["ranker_version"],
                                    "ranker_model_sha256": run["ranker_model_sha256"],
                                    "steps": run["steps"],
                                    "results": [{key: item[key] for key in (
                                        "candidate_id", "result_rank", "retrieval_rank", "matched_channels",
                                        "dense_rank", "sparse_rank", "ltr_rank", "ltr_score_raw",
                                        "semantic_score", "skill_fit_score", "project_evidence_score",
                                        "missing_penalty", "overclaim_penalty",
                                    )} for item in run["results"]]})
            stage = "explanation"
            explanations = await _request(client, "POST", f"/match-runs/{run['run_id']}/explanations",
                                          payload={"top_k": 3})
            if (explanations["status"] != "COMPLETED" or len(explanations["explanations"]) != 3
                    or explanations["provider_kind"] != "openai_compatible"):
                raise StageFailure("real_grounded_explanations_not_top3")
            _append(artifact_path, {"stage": stage, "status": "PASS",
                                    "explanation_run_id": explanations["explanation_run_id"],
                                    "provider_kind": explanations["provider_kind"],
                                    "configured_model": explanations["configured_model"],
                                    "attempt_count": explanations["attempt_count"],
                                    "repaired": explanations["repaired"],
                                    "source_ids": [item["match_explanation_id"]
                                                   for item in explanations["explanations"]]})
            stage = "explanation_readback"
            persisted = await _request(client, "GET", "/explanation-runs/"
                                       f"{explanations['explanation_run_id']}")
            if (persisted["explanation_run_id"] != explanations["explanation_run_id"]
                    or persisted["match_run_id"] != run["run_id"]):
                raise StageFailure("explanation_persistence_readback_mismatch")
            source_ids = _check_explanation_readback(persisted, explanations["explanations"])
            _append(artifact_path, {"stage": stage, "status": "PASS",
                                    "explanation_run_id": persisted["explanation_run_id"],
                                    "source_ids": source_ids,
                                    "explanations": persisted["explanations"]})
            stage = "propositions"
            briefs = []
            for result, explanation in zip(run["results"], explanations["explanations"]):
                if (result["candidate_id"] != explanation["candidate_id"]
                        or result["result_rank"] != explanation["result_rank"]):
                    raise StageFailure("explanation_candidate_or_rank_mismatch")
                brief = await _request(client, "GET", "/match-explanations/"
                                       f"{explanation['match_explanation_id']}/recruiter-propositions")
                checked = _check_brief(brief, result, run, explanation["match_explanation_id"])
                briefs.append(checked)
                _append(artifact_path, {"stage": stage, "status": "PASS", **checked})
            stage = "ranking_after"
            after_run = await _request(client, "GET", f"/match-runs/{run['run_id']}")
            after = _snapshot(after_run)
            if after_run["run_id"] != run["run_id"] or before != after:
                raise StageFailure("ranking_changed_after_explanation_or_propositions")
            _append(artifact_path, {"stage": stage, "status": "PASS", "snapshot": after})
            _append(artifact_path, {"stage": "summary", "status": "TRUSTED_CHAIN_PASS",
                                    "run_id": run["run_id"], "candidate_count": len(briefs),
                                    "narrative_draft": "NOT_RUN", "ranking_invariant": True})
        except Exception as error:
            _append(artifact_path, {"stage": stage, "status": "BLOCKED",
                                    "failure_code": error.code if isinstance(error, StageFailure)
                                    else type(error).__name__,
                                    "provider_error_code": error.provider_code if isinstance(error, StageFailure)
                                    else None})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_id")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.experiment_id, args.base_url))
    except Exception as error:
        print(json.dumps({"status": "BLOCKED", "error_category": type(error).__name__},
                         sort_keys=True))
        raise SystemExit(1)
    print(json.dumps({"status": "TRUSTED_CHAIN_PASS", "experiment_id": args.experiment_id},
                     sort_keys=True))
