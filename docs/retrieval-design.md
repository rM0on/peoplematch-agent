# Phase 4 Hybrid Retrieval Design

## Goal

Phase 4 implements first-stage Candidate/Job recall. Given a Job profile, it retrieves a bounded Candidate set for later feature engineering and ranking. The same components support the reverse Candidate-to-Job direction. Retrieval is not a final match score and does not decide hiring suitability.

## Architecture

```mermaid
flowchart LR
    PG["PostgreSQL canonical profiles"] --> Docs["Retrieval documents\nretrieval_doc_v4"]
    Docs --> Embed["Local pretrained embeddings"]
    Embed --> Qdrant["Qdrant derived dense index"]
    Docs --> BM25["In-process BM25"]
    Qdrant --> RRF["Reciprocal Rank Fusion"]
    BM25 --> RRF
    RRF --> TopK["Deterministic Top-K recall set"]
```

PostgreSQL is the canonical profile source. Qdrant is derived retrieval state and can be rebuilt explicitly from PostgreSQL. Candidate/Job CRUD does not dual-write to Qdrant; every dense or hybrid request checks full-corpus freshness before searching. This full comparison is appropriate for the fixed 48-Candidate/24-Job local sandbox, not a production-scale synchronization design.

## Retrieval Documents

Both channels share the same normalized source `RetrievalDocument` contract. Sparse BM25 consumes the full text. MiniLM applies its 256-token model input limit to the dense channel, so dense consumes a tokenizer-truncated prefix rather than the complete effective content. Document identity, filters, and fingerprints are stored separately and do not become semantic tokens.

### Candidate included fields

- `target_roles`
- `skills.name`, `skills.category`
- `projects.summary`, `projects.role`
- `projects.technologies`, `projects.skills_demonstrated`
- `project_evidence.supports_skills`, `project_evidence.evidence_type`, `project_evidence.statement`
- `ai_tools`

Candidate text excludes Candidate name, project names, every root/nested ID, raw text, URLs/artifact references, archetype, provenance/version fields, missing fields, overclaim risk, location, seniority, and work style. Project names are excluded because the frozen sandbox uses synthetic family/variant suffixes that the dataset leakage guard prohibits as model signals. The builder derives each owned name's full value and dash-delimited base/variant fragments, then removes those signals case-insensitively from every candidate semantic section, including summaries and evidence statements. This is owner-derived normalization, not a fixture keyword list. Location and seniority remain separate filter payload; missing/overclaim/work-style signals remain future Phase 5 concerns.

### Job included fields

- `role_title`, `role_direction`
- must-have and nice-to-have requirement text, category, and evidence expectation
- `evaluation_focus`

Job text excludes job/company name identity, every root/nested ID, raw JD, archetype, provenance/version fields, location, seniority, product stage, and team tags. Product stage is intentionally excluded pending external review.

The active document version is `retrieval_doc_v4`. Review-tree v1–v3 experiments were invalidated while tightening the frozen dataset's project construction-signal guard; their reports remain only as audit history. V4 removes dynamically derived full/base/variant project-name signals across the complete Candidate semantic text. The document fingerprint is SHA-256 over the exact normalized semantic text and is used only for index freshness.

## Dense Retrieval

The runtime provider is `sentence_transformers` with the general-purpose local pretrained model `sentence-transformers/all-MiniLM-L6-v2`. It produces 384-dimensional normalized vectors on CPU and needs no API key. It is not trained or fine-tuned on recruitment data.

The audited model/tokenizer maximum sequence length is 256. For `retrieval_doc_v4`, Candidate documents span 317-452 tokens and all 48 of 48 exceed the limit; Job documents span 256-284 tokens and 23 of 24 exceed the limit. Sentence Transformers therefore truncates dense input to a prefix. Later Candidate sections, including evidence statements and AI tools, may be partially or fully absent from dense encoding. The reported Dense and Hybrid metrics represent this actual baseline. Sparse BM25 continues to consume the full retrieval document.

Qdrant collections are server-configured:

- `peoplematch_candidates_retrieval_v1`
- `peoplematch_jobs_retrieval_v1`

They use cosine similarity. Queries set Qdrant `exact=true` because the fixed sandbox corpus is small and benchmark reproducibility matters more than approximate-search throughput. The client never exposes vectors through the API.

Tests use a separate deterministic hash-projection embedding provider marked `test` and unique Qdrant collection names. Test embeddings are never used for committed retrieval metrics.

## Sparse Retrieval

Sparse retrieval uses an in-process BM25 implementation over retrieval-document text. Tokenization is deterministic Unicode-aware lowercase alphanumeric extraction with no stemming, external tokenizer, LLM tokenizer, or synthetic keyword rules.

- `k1 = 1.5`
- `b = 0.75`

The index is rebuilt in memory per request from the current eligible sandbox corpus. This is intentionally simple for 48/24 entities and is not a production search-index architecture.

## Metadata Eligibility

Filters are optional and explicit-only:

- Job to Candidates: `cities` checks Candidate preferred cities; `seniorities` checks Candidate seniority.
- Candidate to Jobs: `cities` checks Job cities; `seniorities` checks Job accepted seniorities.

No filter is inferred from the query profile. Filters only reduce the eligible corpus. They never add a location score, seniority score, bonus, penalty, or other feature.

## Hybrid Fusion

Hybrid retrieval uses equal-weight Reciprocal Rank Fusion:

```text
fusion_score(entity) = 1 / (60 + dense_rank) + 1 / (60 + sparse_rank)
```

Missing-channel contribution is zero. Each channel contributes up to `min(eligible corpus, max(20, top_k * 3))`. Dense exact search first returns every eligible hit so application-level score/ID ordering is stable before pool truncation. Results sort by fusion score descending, best channel rank ascending, then entity ID ascending. Dense-only and sparse-only ties use score descending and entity ID ascending. No channel weight is learned.

## Qdrant Payload and Freshness

Point IDs are deterministic UUID5 values derived from entity type and canonical root ID. Payload is allowlisted to:

- `entity_id`
- `document_version`
- `document_fingerprint`
- `cities`
- `seniorities`

It excludes semantic text, labels, split, provenance, archetype, frozen status, hard-negative metadata, and construction fields. Before dense/hybrid search, the service verifies collection existence, cosine distance, vector dimension, exact entity-ID set, and the exact allowlisted payload including document version/fingerprint and filter metadata. Missing collections return `retrieval_index_missing`; mismatches return `retrieval_index_stale`; Qdrant failures return `vector_store_unavailable`.

Index construction is explicit:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://peoplematch:peoplematch_local@localhost:5432/peoplematch"
$env:QDRANT_URL = "http://localhost:6333"
& .\backend\.venv\Scripts\python.exe scripts\build_retrieval_index.py --entity all
```

## Integrity and Privacy

Runtime retrieval modules do not read labels, pairwise preferences, hard-negative bookkeeping, or query splits. IDs are used only for lookup, payload identity, result identity, and deterministic tie-breaking. Logs and API responses must not expose raw profile source, full documents, vectors, tensors, or private infrastructure exceptions.

## Limitations

- This is local sandbox first-stage retrieval, not final ranking.
- The embedding model is general-purpose and not recruitment-tuned.
- Exact Qdrant search, full freshness comparison, and request-time BM25 suit the current 48/24 corpus only.
- Equal-weight RRF is a fixed baseline, not a learned claim of optimal fusion.
- Dense input truncation is accepted and disclosed for this baseline. Section-aware encoding, chunked or multi-vector embeddings, pooling across sections/chunks, or a reviewed longer-context model would require a new retrieval experiment/version and must not be tuned against the already exposed Phase 4 test queries.
- The backend image contains the Python package but does not bake MiniLM weights or mount a persistent Hugging Face cache. A fresh container may require a first-use download and is not a fully offline image.
- Phase 5 feature engineering, constraint scoring, LTR, Cross-Encoder reranking, explanations, and feedback remain unimplemented.
