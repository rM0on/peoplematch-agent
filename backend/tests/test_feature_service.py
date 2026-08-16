from __future__ import annotations

import asyncio

import pytest

from test_retrieval_service import _service


def _feature_service():
    from app.services.features.service import FeatureEngineeringService

    retrieval, candidates, jobs = _service()
    return (
        FeatureEngineeringService(
            retrieval_service=retrieval,
            candidate_repository=retrieval.candidate_repository,
            job_repository=retrieval.job_repository,
        ),
        retrieval,
        candidates,
        jobs,
    )


def test_job_candidate_features_preserve_retrieval_order_and_raw_context() -> None:
    from app.schemas.retrieval import RetrievalRequest

    feature_service, retrieval, _, jobs = _feature_service()
    request = RetrievalRequest(strategy="hybrid", top_k=4)
    original = asyncio.run(retrieval.retrieve_candidates(jobs[0].job_id, request))
    enriched = asyncio.run(
        feature_service.features_for_job_candidates(jobs[0].job_id, request)
    )

    assert [item.entity_id for item in enriched.results] == [
        item.entity_id for item in original.results
    ]
    assert [item.retrieval for item in enriched.results] == original.results
    assert enriched.retrieval_diagnostics.query_id == jobs[0].job_id
    assert enriched.feature_version == "feature_schema_v1"
    assert len(enriched.feature_fingerprint) == 64


def test_candidate_job_features_preserve_reverse_order() -> None:
    from app.schemas.retrieval import RetrievalRequest

    feature_service, retrieval, candidates, _ = _feature_service()
    request = RetrievalRequest(strategy="sparse", top_k=3)
    original = asyncio.run(retrieval.retrieve_jobs(candidates[0].candidate_id, request))
    enriched = asyncio.run(
        feature_service.features_for_candidate_jobs(candidates[0].candidate_id, request)
    )

    assert [item.entity_id for item in enriched.results] == [
        item.entity_id for item in original.results
    ]
    assert [item.retrieval for item in enriched.results] == original.results


def test_profile_features_are_bidirectionally_consistent() -> None:
    from app.schemas.retrieval import RetrievalRequest

    feature_service, _, candidates, jobs = _feature_service()
    forward = asyncio.run(
        feature_service.features_for_job_candidates(
            jobs[0].job_id, RetrievalRequest(strategy="sparse", top_k=4)
        )
    )
    reverse = asyncio.run(
        feature_service.features_for_candidate_jobs(
            candidates[0].candidate_id, RetrievalRequest(strategy="sparse", top_k=3)
        )
    )
    forward_item = next(
        item for item in forward.results if item.entity_id == candidates[0].candidate_id
    )
    reverse_item = next(item for item in reverse.results if item.entity_id == jobs[0].job_id)
    forward_profile = forward_item.feature_vector.model_dump(
        exclude={"semantic_score", "sparse_score"}
    )
    reverse_profile = reverse_item.feature_vector.model_dump(
        exclude={"semantic_score", "sparse_score"}
    )

    assert forward_profile == reverse_profile


def test_feature_service_uses_batch_profile_reads_not_per_result_lookups() -> None:
    from app.schemas.retrieval import RetrievalRequest

    feature_service, retrieval, _, jobs = _feature_service()
    candidate_repo = retrieval.candidate_repository
    original_list = candidate_repo.list_all_records
    calls = 0

    async def counted_list():
        nonlocal calls
        calls += 1
        return await original_list()

    candidate_repo.list_all_records = counted_list
    asyncio.run(
        feature_service.features_for_job_candidates(
            jobs[0].job_id, RetrievalRequest(strategy="sparse", top_k=4)
        )
    )

    # One corpus read belongs to frozen retrieval; one batch read belongs to enrichment.
    assert calls == 2


def test_runtime_feature_modules_have_no_evaluation_or_label_dependency() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app/services/features"
    runtime_files = [
        "contract.py",
        "normalization.py",
        "matching.py",
        "extractor.py",
        "service.py",
    ]
    source = "\n".join((root / name).read_text(encoding="utf-8") for name in runtime_files)
    forbidden_imports = (
        "retrieval.evaluation",
        "relevance_grade",
        "pairwise_preferences",
        "hard_negative",
        "query_splits",
        "phase4_retrieval_report",
    )
    assert all(value not in source for value in forbidden_imports)


def test_invalid_profile_on_enrichment_batch_is_typed() -> None:
    from app.exceptions import InvalidProfileStateError
    from app.schemas.candidate import CandidateProfile
    from app.schemas.retrieval import RetrievalRequest

    feature_service, retrieval, _, jobs = _feature_service()
    candidate_repo = retrieval.candidate_repository
    original_list = candidate_repo.list_all_records
    calls = 0

    async def invalid_second_read():
        nonlocal calls
        calls += 1
        if calls == 1:
            return await original_list()
        CandidateProfile.model_validate({})

    candidate_repo.list_all_records = invalid_second_read

    with pytest.raises(InvalidProfileStateError):
        asyncio.run(
            feature_service.features_for_job_candidates(
                jobs[0].job_id, RetrievalRequest(strategy="sparse", top_k=2)
            )
        )


def test_invalid_job_on_reverse_enrichment_batch_is_typed() -> None:
    from app.exceptions import InvalidProfileStateError
    from app.schemas.job import JobProfile
    from app.schemas.retrieval import RetrievalRequest

    feature_service, retrieval, candidates, _ = _feature_service()
    job_repo = retrieval.job_repository
    original_list = job_repo.list_all_records
    calls = 0

    async def invalid_second_read():
        nonlocal calls
        calls += 1
        if calls == 1:
            return await original_list()
        JobProfile.model_validate({})

    job_repo.list_all_records = invalid_second_read

    with pytest.raises(InvalidProfileStateError):
        asyncio.run(
            feature_service.features_for_candidate_jobs(
                candidates[0].candidate_id,
                RetrievalRequest(strategy="sparse", top_k=2),
            )
        )


def test_runtime_feature_dependency_graph_excludes_evaluation_data_modules() -> None:
    import ast
    from pathlib import Path

    app_root = Path(__file__).resolve().parents[1] / "app"
    queue = ["app.services.features.service"]
    visited = set()
    imports = set()
    while queue:
        module = queue.pop()
        if module in visited:
            continue
        visited.add(module)
        path = app_root.parent / (module.replace(".", "/") + ".py")
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
                if node.module.startswith("app."):
                    queue.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
                    if alias.name.startswith("app."):
                        queue.append(alias.name)

    forbidden = ("evaluation", "label", "pairwise", "hard_negative", "query_splits")
    assert all(not any(term in module for term in forbidden) for module in imports)
