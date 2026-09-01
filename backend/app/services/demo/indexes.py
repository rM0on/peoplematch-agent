from __future__ import annotations

from app.schemas.demo import DemoIndexRebuildData
from app.services.retrieval.documents import (
    build_candidate_document,
    build_job_document,
)
from app.services.retrieval.indexing import build_dense_index


class DemoIndexService:
    """Explicitly rebuild derived demo indexes without changing retrieval semantics."""

    def __init__(self, retrieval_service) -> None:
        self.retrieval_service = retrieval_service

    async def rebuild(self) -> DemoIndexRebuildData:
        candidates = await self.retrieval_service.candidate_repository.list_all_records()
        jobs = await self.retrieval_service.job_repository.list_all_records()
        candidate_report = await build_dense_index(
            documents=[build_candidate_document(item) for item in candidates],
            provider=self.retrieval_service.embedding_provider,
            store=self.retrieval_service.vector_store,
            collection_name=self.retrieval_service.candidate_collection,
        )
        job_report = await build_dense_index(
            documents=[build_job_document(item) for item in jobs],
            provider=self.retrieval_service.embedding_provider,
            store=self.retrieval_service.vector_store,
            collection_name=self.retrieval_service.job_collection,
        )
        if candidate_report.document_version != job_report.document_version:
            raise RuntimeError("Candidate and Job retrieval document versions differ")
        return DemoIndexRebuildData(
            document_version=candidate_report.document_version,
            candidate_collection=candidate_report.collection_name,
            job_collection=job_report.collection_name,
            candidate_count=candidate_report.entity_count,
            job_count=job_report.entity_count,
        )


__all__ = ["DemoIndexService"]
