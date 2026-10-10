"""Opt-in synthetic A/B quality probe; never logs unvalidated provider output."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.explanation.generation.provider import ExplanationProviderError
from app.services.explanation.presentation.contracts_v2_1 import RecruiterNarrativeV2_1
from app.services.explanation.presentation.contracts_v2_2 import RecruiterNarrativeV2_2
from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
from app.services.explanation.presentation.facts_v2_1 import build_atomic_facts_v2_1
from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
from app.services.explanation.presentation.prompt_v2_1 import build_narrative_v2_1_request
from app.services.explanation.presentation.prompt_v2_2 import (
    build_narrative_v2_2_repair_request, build_narrative_v2_2_request,
)
from app.services.explanation.presentation.validator_v2_1 import (
    invalid_narrative_v2_1_sections, validate_narrative_v2_1_projection,
)
from app.services.explanation.presentation.validator_v2_2 import (
    invalid_narrative_v2_2_sections, validate_narrative_v2_2_projection,
    validation_error_summary_v2_2,
)
from narrative_v2_comparison_fixture import build_comparison_group
from narrative_v2_live_comparison import _v1_baseline


def _prose(narrative) -> dict:
    return {
        "candidate_snapshot": narrative.candidate_snapshot.text,
        "why_consider": narrative.why_consider.text,
        "key_strengths": [{"title": item.title, "explanation": item.explanation}
                          for item in narrative.key_strengths],
        "trade_offs": [{"title": item.title, "explanation": item.explanation,
                        "validation_question": item.validation_question}
                       for item in narrative.trade_offs],
        "interview_focus": [{"topic": item.topic, "question": item.question,
                             "reason": item.reason} for item in narrative.interview_focus],
    }


async def _run_version(provider, *, version: str, projection) -> dict:
    start = time.monotonic()
    if version == "v2.1":
        request = build_narrative_v2_1_request(
            build_atomic_facts_v2_1(projection), candidate_id=projection.candidate_id,
            result_rank=projection.result_rank, role_title=projection.role_title,
            max_output_tokens=2048,
        )
        contract, validate, invalid = (
            RecruiterNarrativeV2_1, validate_narrative_v2_1_projection, invalid_narrative_v2_1_sections,
        )
    else:
        request = build_narrative_v2_2_request(
            build_evidence_package_v2_2(projection), projection=projection, max_output_tokens=2048,
        )
        contract, validate, invalid = (
            RecruiterNarrativeV2_2, validate_narrative_v2_2_projection, invalid_narrative_v2_2_sections,
        )
    result = {"prompt_version": request.output_contract_version, "schema": "NOT_RUN",
              "claim_validation": "NOT_RUN"}
    try:
        result["attempt_count"] = 1
        response = await provider.generate(request)
        try:
            narrative = contract.model_validate_json(response.content)
        except (ValueError, TypeError):
            result.update(schema="FAIL", error_category="schema_invalid")
        else:
            result["schema"] = "PASS"
            try:
                validate(narrative, projection=projection)
            except ValueError:
                result.update(claim_validation="FAIL", error_category="claim_validation_failed",
                              invalid_sections=list(invalid(narrative, projection=projection)))
                if (version == "v2.2" and narrative.candidate_id == projection.candidate_id
                        and narrative.result_rank == projection.result_rank):
                    summary = validation_error_summary_v2_2(narrative, projection=projection)
                    result["first_failure"] = summary
                    repair = build_narrative_v2_2_repair_request(request, narrative, summary)
                    result["attempt_count"] = 2
                    repaired_response = await provider.generate(repair)
                    try:
                        repaired = contract.model_validate_json(repaired_response.content)
                    except (ValueError, TypeError):
                        result.update(schema="FAIL", error_category="repair_schema_invalid")
                    else:
                        try:
                            validate(repaired, projection=projection)
                        except ValueError:
                            result.update(invalid_sections=list(invalid(repaired, projection=projection)),
                                          error_category="repair_claim_invalid")
                        else:
                            result.update(schema="PASS", claim_validation="PASS", error_category=None,
                                          invalid_sections=[], narrative=_prose(repaired))
            else:
                result.update(claim_validation="PASS", narrative=_prose(narrative))
    except ExplanationProviderError as error:
        result["error_category"] = error.category
        if hasattr(error, "status_code"):
            result["http_status"] = error.status_code
    except Exception as error:
        result["error_category"] = type(error).__name__
    result["latency_seconds"] = round(time.monotonic() - start, 2)
    return result


async def main(selection: str | None = None, version_filter: str | None = None) -> None:
    provider = build_recruiter_narrative_provider(Settings())
    try:
        for group in (1, 2, 3):
            case = build_comparison_group(group)
            for label, projection in zip(("A", "B"), case["projections"]):
                if selection is not None and selection != f"{group}:{label}":
                    continue
                package = build_evidence_package_v2_2(projection)
                result = {
                    "scenario": case["role"], "candidate": label,
                    "provider": provider.descriptor.kind,
                    "model": provider.descriptor.configured_model,
                    "candidate_evidence": [
                        {"kind": item.kind, "terms": item.terms}
                        for item in package.project_practice + package.technical_scope
                    ],
                    "v1": _v1_baseline(projection),
                }
                if version_filter in {None, "v2.1"}:
                    result["v2_1"] = await _run_version(provider, version="v2.1", projection=projection)
                if version_filter in {None, "v2.2"}:
                    result["v2_2"] = await _run_version(provider, version="v2.2", projection=projection)
                run, before = case["run"], case["ranking_before"]
                result["ranking_invariance"] = {
                    "candidate_order": [item.candidate_id for item in run.results] == before["order"],
                    "ltr_score": [item.ltr_score_raw for item in run.results] == before["ltr_scores"],
                    "fingerprint": run.result_fingerprint == before["fingerprint"],
                }
                print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)
    finally:
        await provider.aclose()


if __name__ == "__main__":
    if len(sys.argv) > 3 or (len(sys.argv) >= 2 and sys.argv[1] not in {
        "1:A", "1:B", "2:A", "2:B", "3:A", "3:B",
    }) or (len(sys.argv) == 3 and sys.argv[2] not in {"v2.1", "v2.2"}):
        raise SystemExit("usage: narrative_v2_2_live_comparison.py [1:A|1:B|2:A|2:B|3:A|3:B] [v2.1|v2.2]")
    asyncio.run(main(sys.argv[1] if len(sys.argv) >= 2 else None,
                     sys.argv[2] if len(sys.argv) == 3 else None))
