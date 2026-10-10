"""Opt-in Qwen quality probe. Emits only validated synthetic narratives.

Run from backend: .venv/Scripts/python.exe tests/narrative_v2_live_comparison.py 1
No raw model response is written or printed. V1 is the deterministic catalog
baseline, not a claimed new V1 provider call.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.explanation.presentation.copy_catalog import approved_copy
from app.services.explanation.presentation.contracts_v2 import RecruiterNarrativeV2
from app.services.explanation.presentation.factory import build_recruiter_narrative_provider
from app.services.explanation.presentation.facts_v2 import build_atomic_facts
from app.services.explanation.presentation.prompt_v2 import (
    build_narrative_v2_repair_request, build_narrative_v2_request, load_narrative_v2_prompt,
)
from app.services.explanation.presentation.validator_v2 import (
    validation_error_summary_v2, validate_narrative_v2_projection,
)
from narrative_v2_comparison_fixture import build_comparison_group


def _v1_baseline(projection) -> dict:
    catalog = approved_copy(projection)
    return {
        "source": "deterministic_v1_approved_copy_baseline",
        "candidate_summary": catalog["candidate_summary"][0].text,
        "recommendation_summary": catalog["recommendation_summary"][0].text,
        "strengths": [item.text for item in catalog["strengths"][:2]],
        "risks": [item.text for item in catalog["risks"][:1]],
        "interview_focus": [item.text for item in catalog["interview_focus"][:1]],
    }


def _safe_failure_categories(narrative, projection) -> list[dict]:
    return validation_error_summary_v2(narrative, projection=projection)["invalid_sections"]


async def main(group: int, candidate_filter: str | None = None) -> None:
    case = build_comparison_group(group)
    before = case["ranking_before"]
    provider = build_recruiter_narrative_provider(Settings())
    try:
        for label, projection in zip(("A", "B"), case["projections"]):
            if candidate_filter is not None and label != candidate_filter:
                continue
            facts = build_atomic_facts(projection)
            start = time.monotonic()
            result = {
                "group": group, "candidate": label, "role": case["role"],
                "model": provider.descriptor.configured_model,
                "prompt_version": load_narrative_v2_prompt().version,
                "job_requirements": case["requirements"],
                "candidate_evidence": sorted({
                    (fact.kind, fact.term) for fact in facts
                    if fact.kind in {"candidate_skill", "project_practice"}
                }),
                "v1": _v1_baseline(projection),
            }
            try:
                request = build_narrative_v2_request(
                    facts, candidate_id=projection.candidate_id,
                    result_rank=projection.result_rank,
                    role_title=projection.role_title, max_output_tokens=2048,
                )
                result["attempt_count"] = 1
                response = await provider.generate(request)
                try:
                    narrative = RecruiterNarrativeV2.model_validate_json(response.content)
                except (ValueError, TypeError):
                    result.update(schema="FAIL", claim_validation="NOT_RUN", failure="schema_invalid")
                else:
                    result["schema"] = "PASS"
                    try:
                        validate_narrative_v2_projection(narrative, projection=projection)
                    except ValueError:
                        result["initial_claim_validation"] = "FAIL"
                        result["initial_failed_sections"] = _safe_failure_categories(narrative, projection)
                        if narrative.candidate_id != projection.candidate_id or narrative.result_rank != projection.result_rank:
                            result.update(claim_validation="FAIL", failure="provenance_invalid")
                        else:
                            repair = build_narrative_v2_repair_request(
                                request, narrative,
                                validation_error_summary_v2(narrative, projection=projection),
                            )
                            result["attempt_count"] = 2
                            response = await provider.generate(repair)
                            try:
                                narrative = RecruiterNarrativeV2.model_validate_json(response.content)
                            except (ValueError, TypeError):
                                result.update(schema="FAIL", claim_validation="NOT_RUN", failure="repair_schema_invalid")
                            else:
                                try:
                                    validate_narrative_v2_projection(narrative, projection=projection)
                                except ValueError:
                                    result.update(claim_validation="FAIL", failure="repair_claim_invalid",
                                                  failed_sections=_safe_failure_categories(narrative, projection))
                                else:
                                    result.update(schema="PASS", claim_validation="PASS",
                                                  observed_model=response.observed_model,
                                                  v2=narrative.model_dump(mode="json"))
                    else:
                        result.update(
                            claim_validation="PASS", observed_model=response.observed_model,
                            v2=narrative.model_dump(mode="json"),
                        )
            except Exception as error:
                result.update(latency_seconds=round(time.monotonic() - start, 2),
                              schema="NOT_RUN", claim_validation="NOT_RUN",
                              failure=type(error).__name__)
            result["latency_seconds"] = round(time.monotonic() - start, 2)
            run = case["run"]
            result["ranking_invariant"] = (
                run.result_fingerprint == before["fingerprint"]
                and [item.candidate_id for item in run.results] == before["order"]
                and [item.ltr_score_raw for item in run.results] == before["ltr_scores"]
            )
            print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)
    finally:
        await provider.aclose()


if __name__ == "__main__":
    if len(sys.argv) not in {2, 3} or sys.argv[1] not in {"1", "2", "3"} or (len(sys.argv) == 3 and sys.argv[2] not in {"A", "B"}):
        raise SystemExit("usage: narrative_v2_live_comparison.py {1|2|3} [A|B]")
    asyncio.run(main(int(sys.argv[1]), sys.argv[2] if len(sys.argv) == 3 else None))
