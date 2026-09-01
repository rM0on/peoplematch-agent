from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from test_retrieval_service import _service


ROOT = Path(__file__).resolve().parents[2]


def test_demo_samples_are_exact_registered_synthetic_inputs(app) -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/demo/samples", headers={"X-Request-ID": "phase12-samples"}
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "phase12-samples"
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["data_origin"] == "synthetic_sandbox"
    assert payload["data"]["candidate_text"] == (
        ROOT / "data/samples/extraction/candidate_matching_resume.txt"
    ).read_text(encoding="utf-8")
    assert payload["data"]["job_text"] == (
        ROOT / "data/samples/extraction/job_matching_engineer.txt"
    ).read_text(encoding="utf-8")
    assert "api_key" not in response.text.lower()


def test_demo_index_service_reuses_frozen_documents_and_index_builder() -> None:
    from app.services.demo.indexes import DemoIndexService

    retrieval_service, candidates, jobs = _service()
    class RebuildStore:
        def __init__(self) -> None:
            self.collections = {}

        async def rebuild(self, collection_name, dimension, points) -> None:
            self.collections[collection_name] = list(points)

    retrieval_service.vector_store = RebuildStore()
    result = asyncio.run(DemoIndexService(retrieval_service).rebuild())

    assert result.document_version == "retrieval_doc_v4"
    assert result.candidate_count == len(candidates)
    assert result.job_count == len(jobs)
    assert result.candidate_collection == retrieval_service.candidate_collection
    assert result.job_collection == retrieval_service.job_collection
    assert len(retrieval_service.vector_store.collections[result.candidate_collection]) == len(candidates)
    assert len(retrieval_service.vector_store.collections[result.job_collection]) == len(jobs)


def test_demo_index_route_returns_typed_auditable_counts(app) -> None:
    from app.api.dependencies import get_demo_index_service
    from app.schemas.demo import DemoIndexRebuildData

    class FakeService:
        async def rebuild(self):
            return DemoIndexRebuildData(
                document_version="retrieval_doc_v4",
                candidate_collection="phase12_candidates",
                job_collection="phase12_jobs",
                candidate_count=49,
                job_count=25,
            )

    app.dependency_overrides[get_demo_index_service] = lambda: FakeService()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/demo/rebuild-retrieval-index",
            json={"confirm": True},
            headers={"X-Request-ID": "phase12-index"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "phase12-index"
    assert response.json()["data"] == {
        "document_version": "retrieval_doc_v4",
        "candidate_collection": "phase12_candidates",
        "job_collection": "phase12_jobs",
        "candidate_count": 49,
        "job_count": 25,
    }


def test_demo_index_route_requires_explicit_confirmation(app) -> None:
    from app.api.dependencies import get_demo_index_service

    class MustNotRun:
        async def rebuild(self):
            raise AssertionError("rebuild must not run without explicit confirmation")

    app.dependency_overrides[get_demo_index_service] = lambda: MustNotRun()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/demo/rebuild-retrieval-index", json={"confirm": False}
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
