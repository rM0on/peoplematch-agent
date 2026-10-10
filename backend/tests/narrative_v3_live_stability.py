"""Opt-in five-case real-provider probe; never prints secrets or invalid prose.

Requires the existing local Compose application and synthetic candidate pool.
This is a diagnostic, not a pytest test or an API/production fallback.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import time

import httpx
from sqlalchemy import URL, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.repositories.recruiter_narrative_repository import RecruiterNarrativeRepository
from app.models.explanation_run import ExplanationRunModel, MatchExplanationModel
from app.services.explanation.generation.openai_compatible import OpenAICompatibleChatProvider
from app.services.explanation.generation.provider import ExplanationProviderDescriptor, ExplanationProviderError
from app.services.explanation.presentation.adapter import build_narrative_projection
from app.services.explanation.presentation.contracts_v3 import RecruiterNarrativeV3
from app.services.explanation.presentation.facts_v3 import build_atomic_fact_graph_v3
from app.services.explanation.presentation.prompt_v3 import build_narrative_v3_request
from app.services.explanation.presentation.validator_v3 import (
    diagnose_narrative_v3_sections, invalid_narrative_v3_sections,
)
from app.services.explanation.presentation.validator_v2 import (
    _CAUTIOUS, _GENERIC_ENGLISH, _INTERNAL, _NUMBER, _TECH_TOKEN, _UNSUPPORTED,
    _invalid_action, _invalid_responsibility, _invalid_scale,
)
from app.services.explanation.presentation.validator_v2_1 import (
    _unsupported_personal_work, _unsupported_production_claim,
)
from app.services.explanation.presentation.validator_v2_2 import _OTHER_CANDIDATE, _UNSUPPORTED_PERSONAL
from app.services.explanation.presentation.validator_v2_3 import _ABSTRACT
from app.services.llm.configuration import ProviderMode, ProviderTask, resolve_provider_selection
from narrative_v2_3_live_comparison import _run_v2_3
from narrative_v2_live_comparison import _v1_baseline


SCENARIOS = (
    ("AI Agent Engineer", "Synthetic AI Agent Engineer role. Build Python and FastAPI services for LLM applications, RAG with Qdrant, agent workflows, retrieval evaluation and backend APIs. Review implementation trade-offs and system boundaries."),
    ("Recommendation Engineer", "Synthetic Recommendation Engineer role. Develop retrieval and learning-to-rank systems with LambdaMART, feature engineering and offline evaluation. Use Python and measurable ranking diagnostics for candidate search."),
    ("AI Backend Engineer", "Synthetic AI Backend Engineer role. Design FastAPI and Python APIs, PostgreSQL data models, Redis integration and Docker-based service delivery. Integrate LLM application backends and review API reliability."),
    ("LLM Application Engineer", "Synthetic LLM Application Engineer role. Build RAG pipelines, structured outputs, prompt engineering workflows and Python backend services. Evaluate retrieval quality and integrate vector databases for AI applications."),
    ("Search Ranking Engineer", "Synthetic Search Ranking Engineer role. Work on embeddings, lexical and vector retrieval, reranking, search relevance and offline evaluation. Use Python and explain ranking trade-offs with measurable diagnostics."),
)


async def _post(client: httpx.AsyncClient, path: str, payload: dict) -> dict:
    response = await client.post(path, json=payload, timeout=180)
    if response.status_code >= 400:
        raise RuntimeError(f"application_http_{response.status_code}")
    envelope = response.json()
    if envelope.get("success") is not True:
        raise RuntimeError("application_response_failed")
    return envelope["data"]


async def _run_v3(provider, projection) -> dict:
    started = time.monotonic()
    graph = build_atomic_fact_graph_v3(projection)
    result = {"schema": "NOT_RUN", "claim": "NOT_RUN", "repair_count": 0,
              "graph_facts": len(graph.facts), "graph_relations": len(graph.edges)}
    try:
        request = build_narrative_v3_request(graph, projection=projection, max_output_tokens=4096)
        response = await provider.generate(request)
        try:
            narrative = RecruiterNarrativeV3.model_validate_json(response.content)
        except (ValueError, TypeError):
            result.update(schema="FAIL", error="schema_invalid")
        else:
            result["schema"] = "PASS"
            sections = invalid_narrative_v3_sections(narrative, projection=projection)
            result["claim"] = "FAIL" if sections else "PASS"
            if sections:
                result["invalid_sections"] = list(sections)
                result["failure_categories"] = diagnose_narrative_v3_sections(narrative, projection=projection)
                lookup = {fact.fact_id: fact for fact in graph.facts}
                claims = {"decision_summary": narrative.decision_summary,
                          **{f"strengths[{i}]": item for i, item in enumerate(narrative.strengths)},
                          **{f"risks[{i}]": item for i, item in enumerate(narrative.risks)},
                          **{f"interview_focus[{i}]": item
                             for i, item in enumerate(narrative.interview_focus)}}
                result["failure_refs"] = {
                    section: {"claim_type": claims[section].claim_type,
                              "fact_ids": claims[section].fact_ids,
                              "fact_kinds": [lookup[ident].kind if ident in lookup else "unknown"
                                             for ident in claims[section].fact_ids]}
                    for section in sections if section in claims
                }
                surface = {}
                for section, category in result["failure_categories"].items():
                    if section not in claims or category not in {
                        "surface_or_caution_violation", "unsafe_or_abstract_assertion",
                    }:
                        continue
                    item = claims[section]
                    facts = [lookup[ident] for ident in item.fact_ids if ident in lookup]
                    cautious = item.claim_type in {"interview_validation", "uncertainty_statement"}
                    allowed_tokens = {token.casefold() for fact in facts
                                      for token in _TECH_TOKEN.findall(fact.term)} | _GENERIC_ENGLISH
                    if projection.role_title.casefold() in item.text.casefold():
                        allowed_tokens |= {token.casefold() for token in _TECH_TOKEN.findall(projection.role_title)}
                    surface[section] = {
                        "unsupported_latin_tokens": sorted({token.casefold() for token in _TECH_TOKEN.findall(item.text)}
                                                           - allowed_tokens),
                        "unsupported_numbers": sorted({number for number in _NUMBER.findall(item.text)}
                                                      - {number for fact in facts for number in _NUMBER.findall(fact.term)}),
                        "abstract": bool(_ABSTRACT.search(item.text)),
                        "cross_candidate": bool(_OTHER_CANDIDATE.search(item.text)),
                        "personal_assertion": bool(_UNSUPPORTED_PERSONAL.search(item.text)
                                                   or _unsupported_personal_work(item.text)),
                        "production_assertion": bool(_unsupported_production_claim(item.text)),
                        "unsafe": bool(_UNSUPPORTED.search(item.text)),
                        "internal": bool(_INTERNAL.search(item.text)),
                        "scale": _invalid_scale(item.text, cautious=cautious, allow_unknown_scale=True),
                        "action": _invalid_action(item.text),
                        "responsibility": _invalid_responsibility(item.text, cautious=cautious),
                        "missing_caution": cautious and not bool(_CAUTIOUS.search(item.text)),
                    }
                result["surface_diagnostics"] = surface
            else:
                result.update(decision=narrative.decision,
                              decision_summary=narrative.decision_summary.text,
                              strengths=[item.text for item in narrative.strengths],
                              risks=[item.text for item in narrative.risks],
                              interview_focus=[item.text for item in narrative.interview_focus])
    except ExplanationProviderError as error:
        result["error"] = error.category
        if hasattr(error, "status_code"):
            result["http_status"] = error.status_code
    except Exception as error:
        result["error"] = type(error).__name__
    result["latency_seconds"] = round(time.monotonic() - started, 2)
    return result


async def main(selected: int | None = None, existing_run_id: str | None = None,
               existing_run_ids: tuple[str, ...] = (),
               graph_only: bool = False) -> None:
    settings = Settings()
    selection = resolve_provider_selection(settings, ProviderTask.EXPLANATION)
    if selection.mode is not ProviderMode.OPENAI_COMPATIBLE:
        raise RuntimeError("real provider required")
    transport = httpx.AsyncClient(trust_env=False, timeout=selection.timeout_seconds)
    provider = OpenAICompatibleChatProvider(
        descriptor=ExplanationProviderDescriptor(
            kind="openai_compatible", name=selection.provider_name,
            configured_model=selection.model,
            configuration_fingerprint=selection.configuration_fingerprint,
        ),
        base_url=selection.base_url, api_key=selection.api_key,
        timeout_seconds=selection.timeout_seconds, client=transport,
    )
    db_url = URL.create(
        "postgresql+asyncpg", username=settings.postgres_user or "peoplematch",
        password=settings.postgres_password or "peoplematch_local",
        host="127.0.0.1", port=settings.postgres_port or 5432,
        database=settings.postgres_db or "peoplematch",
    )
    engine = create_async_engine(db_url)
    repository = RecruiterNarrativeRepository(async_sessionmaker(engine, expire_on_commit=False))
    api = httpx.AsyncClient(base_url="http://127.0.0.1:8000/api/v1", trust_env=False)
    try:
        if existing_run_id is not None or existing_run_ids:
            for run_id in (existing_run_id,) if existing_run_id else existing_run_ids:
                async with async_sessionmaker(engine)() as session:
                    explanation_id = (await session.execute(
                        select(MatchExplanationModel.id)
                        .join(ExplanationRunModel,
                              MatchExplanationModel.explanation_run_id == ExplanationRunModel.explanation_run_id)
                        .where(ExplanationRunModel.match_run_id == run_id)
                        .order_by(MatchExplanationModel.result_rank)
                        .limit(1)
                    )).scalar_one_or_none()
                if explanation_id is None:
                    raise RuntimeError("existing_explanation_missing")
                source = await repository.load_source(explanation_id)
                if source is None:
                    raise RuntimeError("validated_source_missing")
                projection = build_narrative_projection(bundle=source.bundle, source=source.output)
                if graph_only:
                    graph = build_atomic_fact_graph_v3(projection)
                    print(json.dumps({
                        "diagnostic_run_id": run_id,
                        "facts": [{"fact_id": fact.fact_id, "kind": fact.kind,
                                   "concepts": fact.concepts,
                                   "evidence_ref_types": [ref.split(":", 1)[0] for ref in fact.evidence_refs]}
                                  for fact in graph.facts],
                        "edges": [edge.__dict__ for edge in graph.edges],
                    }, ensure_ascii=True, sort_keys=True), flush=True)
                    continue
                result = await _run_v3(provider, projection)
                print(json.dumps({"diagnostic_run_id": run_id, "v3": result},
                                 ensure_ascii=True, sort_keys=True), flush=True)
            return
        for number, (label, jd) in enumerate(SCENARIOS, start=1):
            if selected is not None and selected != number:
                continue
            record = {"case": number, "scenario": label, "provider": selection.provider_name,
                      "model": selection.model, "extraction": "NOT_RUN", "retrieval_ranking": "NOT_RUN",
                      "explanation": "NOT_RUN", "grounding": "NOT_RUN", "v2_3": {"status": "NOT_RUN"},
                      "v3": {"status": "NOT_RUN"}}
            try:
                print(json.dumps({"case": number, "stage": "extraction"}), flush=True)
                started = time.monotonic()
                job = await _post(api, "/jobs/parse", {"text": jd, "persist": True})
                record["extraction"] = "PASS"
                record["extraction_latency_seconds"] = round(time.monotonic() - started, 2)
                job_id = job["record"]["job_id"]
                print(json.dumps({"case": number, "stage": "ranking"}), flush=True)
                run = await _post(api, "/match-runs", {"job_id": job_id,
                                                        "ranking_variant": "ltr", "top_k": 3,
                                                        "candidate_pool_k": 20})
                record["run_id"] = run["run_id"]
                if run["status"] != "COMPLETED" or not run["results"]:
                    raise RuntimeError("ranking_not_completed")
                record["retrieval_ranking"] = "PASS"
                before = ([(r["candidate_id"], r["ltr_score_raw"]) for r in run["results"]],
                          run["result_fingerprint"])
                print(json.dumps({"case": number, "stage": "explanation"}), flush=True)
                started = time.monotonic()
                explanation = await _post(api, f"/match-runs/{run['run_id']}/explanations", {"top_k": 1})
                record["explanation_latency_seconds"] = round(time.monotonic() - started, 2)
                if (explanation["status"] != "COMPLETED" or not explanation["explanations"]
                        or explanation["provider_kind"] != "openai_compatible"):
                    raise RuntimeError("real_explanation_not_completed")
                record["explanation"] = "PASS"
                source = await repository.load_source(explanation["explanations"][0]["match_explanation_id"])
                if source is None:
                    raise RuntimeError("validated_source_missing")
                projection = build_narrative_projection(bundle=source.bundle, source=source.output)
                record["grounding"] = "PASS"
                record["candidate_signature"] = source.output.candidate_id[:8]
                record["v1"] = _v1_baseline(projection)
                print(json.dumps({"case": number, "stage": "v2_3"}), flush=True)
                record["v2_3"] = await _run_v2_3(provider, projection)
                print(json.dumps({"case": number, "stage": "v3"}), flush=True)
                record["v3"] = await _run_v3(provider, projection)
                current_response = await api.get(f"/match-runs/{run['run_id']}", timeout=20)
                current_response.raise_for_status()
                current = current_response.json()["data"]
                after = ([(r["candidate_id"], r["ltr_score_raw"]) for r in current["results"]],
                         current["result_fingerprint"])
                record["ranking_invariance"] = before == after
            except Exception as error:
                record["error"] = str(error) if str(error).startswith("application_http_") else type(error).__name__
            print(json.dumps(record, ensure_ascii=True, sort_keys=True), flush=True)
    finally:
        await api.aclose()
        await transport.aclose()
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--existing-runs":
        asyncio.run(main(existing_run_ids=tuple(sys.argv[2:])))
    elif len(sys.argv) == 4 and sys.argv[1] == "--existing-run" and sys.argv[3] == "--graph-only":
        asyncio.run(main(existing_run_id=sys.argv[2], graph_only=True))
    elif len(sys.argv) == 3 and sys.argv[1] == "--existing-run":
        asyncio.run(main(existing_run_id=sys.argv[2]))
    elif len(sys.argv) <= 2 and (len(sys.argv) == 1 or sys.argv[1] in {"1", "2", "3", "4", "5"}):
        asyncio.run(main(int(sys.argv[1]) if len(sys.argv) == 2 else None))
    else:
        raise SystemExit("usage: narrative_v3_live_stability.py [1|2|3|4|5|--existing-run RUN_ID]")
