"""Opt-in fresh full-chain, three-candidate real Qwen V5 quality gate."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
import json
from pathlib import Path
import sys
import time

import httpx
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.repositories.recruiter_narrative_repository import RecruiterNarrativeRepository
from app.services.explanation.generation.provider import ExplanationProviderError
from app.services.explanation.presentation.adapter import build_narrative_projection
from app.services.explanation.presentation.claims_v4 import build_recruiter_claim_graph_v4
from app.services.explanation.presentation.decision_frame_v4_1 import build_hiring_decision_frame_v4_1
from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3
from app.services.explanation.presentation.hiring_context_v5 import build_hiring_context_v5
from app.services.explanation.presentation.service_v5 import (
    NarrativeV5GenerationError, generate_validated_narrative_v5,
)
from app.services.llm.configuration import ProviderMode, ProviderTask, resolve_provider_selection
from narrative_v3_live_stability import SCENARIOS, _post


def safe_provider_failure(error: ExplanationProviderError, *, task: str, model: str,
                          attempt: int, latency_seconds: float) -> dict[str, object]:
    """Never copy untrusted messages, headers, prompt, candidate data or raw body."""
    return {
        "provider_task": task, "model": model,
        "http_status": getattr(error, "status_code", None),
        "provider_error_code": getattr(error, "provider_error_code", None),
        "safe_category": error.category,
        "timeout_phase": getattr(error, "phase", None),
        "retry_after_seconds": getattr(error, "retry_after_seconds", None),
        "received_response": getattr(error, "received_response", False),
        "request_id": None,
        "attempt_number": attempt,
        "latency_seconds": round(latency_seconds, 3),
    }


class CountingProvider:
    """Observe the existing provider client; never create a second transport."""

    def __init__(self, provider):
        self.provider = provider
        self.attempts = 0
        self.last_http_status: int | None = None

    async def generate(self, request):
        self.attempts += 1
        response = await self.provider.generate(request)
        self.last_http_status = response.http_status_code
        return response


async def main() -> int:
    settings = Settings()
    extraction = resolve_provider_selection(settings, ProviderTask.EXTRACTION)
    explanation = resolve_provider_selection(settings, ProviderTask.EXPLANATION)
    if (extraction.mode is not ProviderMode.OPENAI_COMPATIBLE
            or explanation.mode is not ProviderMode.OPENAI_COMPATIBLE
            or extraction.model != "qwen3.7-flash-2026-07-15"
            or explanation.model != "qwen3.7-flash-2026-07-15"):
        raise RuntimeError("real_qwen_configuration_required")
    db_url = URL.create(
        "postgresql+asyncpg", username=settings.postgres_user or "peoplematch",
        password=settings.postgres_password or "peoplematch_local",
        host="127.0.0.1", port=settings.postgres_port or 5432,
        database=settings.postgres_db or "peoplematch",
    )
    engine = create_async_engine(db_url)
    repository = RecruiterNarrativeRepository(async_sessionmaker(engine, expire_on_commit=False))
    label, jd = SCENARIOS[0]
    stage = "runtime_setup"
    stage_started = time.monotonic()
    counted: CountingProvider | None = None
    try:
        async with AsyncExitStack() as stack:
            provider = build_recruiter_narrative_provider(settings)
            stack.push_async_callback(provider.aclose)
            counted = CountingProvider(provider)
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000/api/v1",
                                         trust_env=False, timeout=extraction.timeout_seconds) as api:
                stage = "extraction"
                stage_started = time.monotonic()
                print(json.dumps({"stage": "fresh_extraction", "scenario": label}), flush=True)
                job = await _post(api, "/jobs/parse", {"text": jd, "persist": True})
                stage = "match_run"
                stage_started = time.monotonic()
                print(json.dumps({"stage": "fresh_match_run"}), flush=True)
                run = await _post(api, "/match-runs", {
                    "job_id": job["record"]["job_id"], "ranking_variant": "ltr",
                    "top_k": 3, "candidate_pool_k": 20,
                })
                if run["status"] != "COMPLETED" or len(run["results"]) < 3:
                    raise RuntimeError("three_ranked_candidates_unavailable")
                before = ([(r["candidate_id"], r["ltr_score_raw"]) for r in run["results"]],
                          run["result_fingerprint"])
                stage = "explanation"
                stage_started = time.monotonic()
                print(json.dumps({"stage": "fresh_explanations", "run_id": run["run_id"]}), flush=True)
                explanation_run = await _post(
                    api, f"/match-runs/{run['run_id']}/explanations", {"top_k": 3})
                if (explanation_run["status"] != "COMPLETED"
                        or len(explanation_run["explanations"]) < 3
                        or explanation_run["provider_kind"] != "openai_compatible"):
                    raise RuntimeError("three_real_explanations_unavailable")
                results = []
                for entry in explanation_run["explanations"][:3]:
                    stage = "recruiter_narrative"
                    stage_started = time.monotonic()
                    counted.attempts = 0
                    counted.last_http_status = None
                    source = await repository.load_source(entry["match_explanation_id"])
                    if source is None:
                        raise RuntimeError("validated_explanation_source_missing")
                    projection = build_narrative_projection(bundle=source.bundle, source=source.output)
                    graph = build_recruiter_claim_graph_v4(build_atomic_fact_graph_v3(projection))
                    frame = build_hiring_decision_frame_v4_1(graph)
                    context = build_hiring_context_v5(graph, frame)
                    item = {"candidate_id": projection.candidate_id, "rank": projection.result_rank,
                            "extraction": "PASS", "explanation": "PASS", "grounding": "PASS"}
                    try:
                        generated = await generate_validated_narrative_v5(
                            counted, context=context, graph=graph, frame=frame,
                            role_title=projection.role_title)
                    except NarrativeV5GenerationError as error:
                        item.update(schema_claim_frame="FAIL", failure_category=error.reason,
                                    failure_sections=error.diagnostics,
                                    http_status=counted.last_http_status,
                                    attempt_number=counted.attempts,
                                    safe_category="narrative_validation")
                    else:
                        narrative = generated.narrative
                        item.update(schema_claim_frame="PASS", repair_count=generated.repair_count,
                                    latency_seconds=generated.latency_seconds,
                                    http_status=counted.last_http_status,
                                    attempt_number=counted.attempts,
                                    safe_category="ok", provider_error_code=None,
                                    decision_summary=narrative.decision_summary.text,
                                    why_consider=[x.text for x in narrative.why_consider],
                                    technical_signal=[x.text for x in narrative.technical_signal],
                                    uncertainty=[x.text for x in narrative.uncertainty],
                                    interview_focus=[x.text for x in narrative.interview_focus])
                    results.append(item)
                    print(json.dumps({"stage": "candidate_complete", **item}, ensure_ascii=True), flush=True)
                current_response = await api.get(f"/match-runs/{run['run_id']}", timeout=20)
                current_response.raise_for_status()
                current = current_response.json()["data"]
                after = ([(r["candidate_id"], r["ltr_score_raw"]) for r in current["results"]],
                         current["result_fingerprint"])
                print(json.dumps({"stage": "summary", "run_id": run["run_id"],
                                  "candidate_count": len(set(x["candidate_id"] for x in results)),
                                  "claim_pass_count": sum(x["schema_claim_frame"] == "PASS" for x in results),
                                  "ranking_invariance": before == after}), flush=True)
                return 0
    except ExplanationProviderError as error:
        print(json.dumps({"stage": "blocked", "at_stage": stage,
                          **safe_provider_failure(
                              error, task="recruiter_narrative", model=explanation.model,
                              attempt=counted.attempts if counted else 1,
                              latency_seconds=time.monotonic() - stage_started)},
                         ensure_ascii=True), flush=True)
        return 1
    except Exception as error:
        print(json.dumps({"stage": "blocked", "at_stage": stage,
                          "error_type": type(error).__name__,
                          "safe_error": str(error) if str(error).startswith("application_http_") else None}),
              flush=True)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
