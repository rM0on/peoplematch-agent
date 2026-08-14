from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_engine, get_session_factory  # noqa: E402
from app.repositories.candidate_repository import CandidateRepository  # noqa: E402
from app.repositories.job_repository import JobRepository  # noqa: E402
from app.services.retrieval.documents import (  # noqa: E402
    build_candidate_document,
    build_job_document,
)
from app.services.retrieval.embedding import (  # noqa: E402
    SentenceTransformerEmbeddingProvider,
)
from app.services.retrieval.indexing import (  # noqa: E402
    build_dense_index,
    validate_index_freshness,
)
from app.services.retrieval.vector_store import QdrantDenseVectorStore  # noqa: E402


async def run(entity: str) -> int:
    settings = get_settings()
    if settings.retrieval_embedding_provider != "sentence_transformers":
        raise RuntimeError("Only sentence_transformers is implemented for runtime indexing")
    provider = SentenceTransformerEmbeddingProvider(
        model_name=settings.retrieval_embedding_model,
        dimension=settings.retrieval_embedding_dimension,
    )
    store = QdrantDenseVectorStore(url=settings.qdrant_url)
    reports = []
    try:
        async with get_session_factory()() as session:
            if entity in {"candidates", "all"}:
                records = await CandidateRepository(session).list_all_records()
                documents = [build_candidate_document(record) for record in records]
                report = await build_dense_index(
                    documents=documents,
                    provider=provider,
                    store=store,
                    collection_name=settings.retrieval_candidate_collection,
                )
                await validate_index_freshness(
                    documents=documents,
                    store=store,
                    collection_name=settings.retrieval_candidate_collection,
                    expected_dimension=provider.descriptor.dimension,
                )
                reports.append(report)
            if entity in {"jobs", "all"}:
                records = await JobRepository(session).list_all_records()
                documents = [build_job_document(record) for record in records]
                report = await build_dense_index(
                    documents=documents,
                    provider=provider,
                    store=store,
                    collection_name=settings.retrieval_job_collection,
                )
                await validate_index_freshness(
                    documents=documents,
                    store=store,
                    collection_name=settings.retrieval_job_collection,
                    expected_dimension=provider.descriptor.dimension,
                )
                reports.append(report)
        for report in reports:
            print(
                "Index PASS: "
                f"collection={report.collection_name}; entities={report.entity_count}; "
                f"dimension={report.dimension}; document_version={report.document_version}; "
                "freshness=fresh."
            )
        return 0
    finally:
        await store.client.close()
        await get_engine().dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build derived Phase 4 Qdrant indexes.")
    parser.add_argument(
        "--entity",
        choices=("candidates", "jobs", "all"),
        default="all",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.entity))


if __name__ == "__main__":
    raise SystemExit(main())
