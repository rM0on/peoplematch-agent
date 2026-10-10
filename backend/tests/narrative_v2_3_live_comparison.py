"""Opt-in real-provider quality probe over six synthetic A/B cases.

Only validated narratives are printed. Raw failed provider output is never
printed or written. A provider HTTP 403 stops further calls but emits explicit
NOT_RUN records for every remaining case to prevent success-only reporting.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.explanation.generation.provider import ExplanationProviderError
from app.services.explanation.presentation.contracts_v2_3 import RecruiterNarrativeV2_3
from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
from app.services.explanation.presentation.facts_v2_2 import build_evidence_package_v2_2
from app.services.explanation.presentation.prompt_v2_3 import (
    build_narrative_v2_3_repair_request, build_narrative_v2_3_request,
)
from app.services.explanation.presentation.validator_v2_3 import (
    invalid_narrative_v2_3_sections, validate_narrative_v2_3_projection,
)
from narrative_v2_2_live_comparison import _run_version
from narrative_v2_comparison_fixture import build_comparison_group
from narrative_v2_live_comparison import _v1_baseline


async def _run_v2_3(provider, projection) -> dict:
    start = time.monotonic()
    result = {"schema": "NOT_RUN", "claim_validation": "NOT_RUN", "attempt_count": 0}
    try:
        request = build_narrative_v2_3_request(
            build_evidence_package_v2_2(projection), projection=projection,
            max_output_tokens=2048,
        )
        result["attempt_count"] = 1
        response = await provider.generate(request)
        try:
            narrative = RecruiterNarrativeV2_3.model_validate_json(response.content)
        except (ValueError, TypeError):
            result.update(schema="FAIL", error_category="schema_invalid")
        else:
            result["schema"] = "PASS"
            try:
                validate_narrative_v2_3_projection(narrative, projection=projection)
            except ValueError:
                sections = list(invalid_narrative_v2_3_sections(narrative, projection=projection))
                result.update(claim_validation="FAIL", error_category="claim_validation_failed",
                              first_invalid_sections=sections)
                if narrative.candidate_id == projection.candidate_id and narrative.result_rank == projection.result_rank:
                    repair = build_narrative_v2_3_repair_request(
                        request, narrative,
                        {"category": "claim_validation_failed", "invalid_sections": sections},
                    )
                    result["attempt_count"] = 2
                    response = await provider.generate(repair)
                    try:
                        narrative = RecruiterNarrativeV2_3.model_validate_json(response.content)
                    except (ValueError, TypeError):
                        result.update(schema="FAIL", error_category="repair_schema_invalid")
                    else:
                        try:
                            validate_narrative_v2_3_projection(narrative, projection=projection)
                        except ValueError:
                            result.update(error_category="repair_claim_invalid",
                                          final_invalid_sections=list(invalid_narrative_v2_3_sections(
                                              narrative, projection=projection)))
                        else:
                            result.update(claim_validation="PASS", error_category=None,
                                          decision=narrative.decision_summary.decision,
                                          rationale=[{"statement": item.statement,
                                                      "verification_focus": item.verification_focus}
                                                     for item in narrative.decision_summary.rationale])
            else:
                result.update(claim_validation="PASS", decision=narrative.decision_summary.decision,
                              rationale=[{"statement": item.statement,
                                          "verification_focus": item.verification_focus}
                                         for item in narrative.decision_summary.rationale])
    except ExplanationProviderError as error:
        result["error_category"] = error.category
        if hasattr(error, "status_code"):
            result["http_status"] = error.status_code
    except Exception as error:
        result["error_category"] = type(error).__name__
    result["latency_seconds"] = round(time.monotonic() - start, 2)
    return result


async def main() -> None:
    provider = build_recruiter_narrative_provider(Settings())
    blocked = False
    try:
        for group in (1, 2, 3):
            case = build_comparison_group(group)
            before, run = case["ranking_before"], case["run"]
            for label, projection in zip(("A", "B"), case["projections"]):
                result = {
                    "scenario": case["role"], "candidate": label,
                    "provider": provider.descriptor.kind,
                    "configured_model": provider.descriptor.configured_model,
                    "v1": _v1_baseline(projection),
                    "v2_2": {"status": "NOT_RUN"} if blocked else None,
                    "v2_3": {"status": "NOT_RUN", "reason": "previous_http_403"} if blocked else None,
                    "ranking_invariance": {
                        "candidate_order": [item.candidate_id for item in run.results] == before["order"],
                        "ltr_score": [item.ltr_score_raw for item in run.results] == before["ltr_scores"],
                        "fingerprint": run.result_fingerprint == before["fingerprint"],
                    },
                }
                if not blocked:
                    result["v2_3"] = await _run_v2_3(provider, projection)
                    if (result["v2_3"].get("error_category") == "http_status"
                            and result["v2_3"].get("http_status") == 403):
                        blocked = True
                        result["v2_2"] = {"status": "NOT_RUN", "reason": "provider_http_403"}
                    else:
                        result["v2_2"] = await _run_version(provider, version="v2.2", projection=projection)
                        if (result["v2_2"].get("error_category") == "http_status"
                                and result["v2_2"].get("http_status") == 403):
                            blocked = True
                print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
