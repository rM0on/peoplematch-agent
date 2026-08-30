from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def _database_name() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "")
    parsed = urlparse(url.replace("postgresql+asyncpg://", "postgresql://", 1))
    name = parsed.path.lstrip("/")
    if not name.startswith("peoplematch_task6_"):
        raise RuntimeError("Task 6 E2E refuses to use a non-disposable database")
    if os.environ.get("DATABASE_URL") != os.environ.get("TEST_DATABASE_URL"):
        raise RuntimeError("DATABASE_URL and TEST_DATABASE_URL must target the same disposable database")
    return name


async def _seed() -> None:
    from app.repositories.explanation_run_repository import ExplanationRunRepository
    from tests.test_explanation_postgres import (
        _completion_values,
        _evidence,
        _explanation,
        _output,
        _running,
        _source_run,
    )
    from tests.test_feedback_bad_case_repository_postgres import _engine_and_factory, _truncate

    engine, factory = await _engine_and_factory()
    try:
        await _truncate(engine)
        run_id, job_id, candidates, results = await _source_run(
            factory, "910", candidate_count=2
        )
        explanation_run_id = "10000000-0000-0000-0000-000000000910"
        repository = ExplanationRunRepository(factory)
        await repository.create_running(_running(explanation_run_id, run_id, top_k=2))
        bundle, provider = _evidence(run_id, job_id, candidates)
        await repository.store_evidence(
            explanation_run_id,
            evidence_bundle=bundle,
            provider_evidence=provider,
        )
        explanation_rows = []
        for result in results:
            output = _output(result.candidate_id, result.result_rank)
            output.match_reasons[0].evidence_refs = [
                f"candidate:{result.result_rank}:skill:0123456789abcdef0123456789abcde{result.result_rank}"
            ]
            explanation_rows.append(_explanation(explanation_run_id, result, output))
        await repository.finalize_completed(
            explanation_run_id,
            explanation_rows,
            **_completion_values(),
        )
        explanation = await repository.get_by_explanation_run_id(
            explanation_run_id, include_explanations=True
        )
        print(json.dumps({
            "database": _database_name(),
            "match_run_id": run_id,
            "job_id": job_id,
            "candidate_ids": candidates,
            "match_result_ids": [item.id for item in results],
            "explanation_run_id": explanation_run_id,
            "match_explanation_ids": [item.id for item in explanation.explanations],
        }))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    _database_name()
    asyncio.run(_seed())
