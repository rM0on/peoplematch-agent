# Phase 4 Hybrid Retrieval Implementation Plan

> **Evaluation-history note:** This is the original prospective implementation plan, not the final experiment ledger. Actual artifacts record dev and test runs for `retrieval_doc_v1`, `retrieval_doc_v2`, `retrieval_doc_v3`, and `retrieval_doc_v4`. V1-v3 were invalidated during construction-artifact remediation after their test metrics were visible. The active v4 result is therefore a post-exposure fixed synthetic sandbox benchmark, not a pristine held-out estimate. See `docs/retrieval-evaluation.md` and the retained v1-v4 artifacts for the authoritative history.

> **For agentic workers:** Execute inline in this session. Every production behavior follows RED → GREEN → regression verification. Do not commit or push; leave a dirty Phase 4 review tree.

**Goal:** Build auditable, bidirectional first-stage retrieval with versioned semantic documents, local pretrained dense embeddings in Qdrant, in-process BM25, explicit metadata filters, RRF, strict index freshness, and isolated fixed-sandbox offline retrieval evaluation.

**Architecture:** PostgreSQL remains the canonical profile store. A versioned builder converts Candidate/Job records into label-free retrieval documents; Qdrant stores deterministic dense-index projections while BM25 is built from the same current eligible document text. A single retrieval service performs Job→Candidate and Candidate→Job dense/sparse/hybrid recall, and a separate evaluator is the only layer permitted to load labels or splits.

**Tech Stack:** Python 3.9+, FastAPI, Pydantic v2, async SQLAlchemy, sentence-transformers `sentence-transformers/all-MiniLM-L6-v2`, qdrant-client, Qdrant 1.15.4, pytest.

## Global Constraints

- Phase 4 is recall/retrieval only; no feature scores, weighted match score, LTR, Cross-Encoder, explanation, real LLM, feedback, or Phase 5+ behavior.
- Runtime retrieval must not import or read labels, pairwise preferences, hard-negative metadata, or train/dev/test splits.
- Retrieval text excludes IDs, names/company names, raw source, provenance/construction fields, location, seniority, and future feature fields exactly as required by the approved prompt.
- Metadata filters are explicit-only eligibility filters and never contribute score.
- PostgreSQL is canonical; Qdrant is derived state rebuilt explicitly and guarded by full-corpus sandbox freshness checks.
- No PostgreSQL migration, new service, secret, commit, push, or test-set tuning.
- Test evaluation runs only after config/document fields are sealed and fingerprinted from stable JSON.

---

### Task 1: Lock schemas, configuration, documents, BM25, and RRF

**Files:**
- Create: `backend/tests/test_retrieval_documents.py`
- Create: `backend/tests/test_retrieval_sparse.py`
- Create: `backend/tests/test_retrieval_fusion.py`
- Create: `backend/app/schemas/retrieval.py`
- Create: `backend/app/services/retrieval/__init__.py`
- Create: `backend/app/services/retrieval/documents.py`
- Create: `backend/app/services/retrieval/sparse.py`
- Create: `backend/app/services/retrieval/fusion.py`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`

**Interfaces:**
- Produce `RETRIEVAL_DOCUMENT_VERSION = "retrieval_doc_v1"`, `CandidateRetrievalDocument`, `JobRetrievalDocument`, strict request/result/diagnostic models, `build_candidate_document(record)`, `build_job_document(record)`, `tokenize(text)`, `BM25Retriever.search(query, limit)`, and `reciprocal_rank_fusion(...)`.
- Fingerprint exact normalized semantic text as SHA-256; IDs remain identity fields outside text.

- [ ] Write document tests asserting every approved include and exclude field plus stable fingerprints.
- [ ] Run `python -m pytest backend/tests/test_retrieval_documents.py -q` and observe import/behavior failures.
- [ ] Implement minimal strict retrieval schemas and centralized document builders.
- [ ] Re-run document tests to green.
- [ ] Write tokenizer/BM25 tests for Unicode-safe lowercase alphanumeric tokens, lexical winner, empty query, stable ties, and corpus-order independence.
- [ ] Run sparse tests and observe missing behavior.
- [ ] Implement BM25 with fixed `k1=1.5`, `b=0.75`, deterministic entity-ID tie-break, and no frozen-label knowledge.
- [ ] Re-run sparse tests to green.
- [ ] Write exact mathematical RRF tests for dense `A B C`, sparse `B D A`, missing contributions, equal weights, `rrf_k=60`, and stable ties.
- [ ] Run fusion tests and observe missing behavior.
- [ ] Implement minimal RRF and re-run tests to green.
- [ ] Add typed settings for providers, model, collections, RRF, BM25, pool minimum/multiplier, and Qdrant URL; expose safe defaults in Compose and `.env.example`.

### Task 2: Add deterministic and real embedding providers

**Files:**
- Create: `backend/tests/test_retrieval_embedding.py`
- Create: `backend/app/services/retrieval/embedding.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`

**Interfaces:**
- Produce immutable `EmbeddingProviderDescriptor`, async `EmbeddingProvider.embed_documents(texts)` / `embed_query(text)`, `DeterministicTestEmbeddingProvider` marked test-only, and lazy `SentenceTransformerEmbeddingProvider` fixed to `sentence-transformers/all-MiniLM-L6-v2`.
- Provider descriptor owns name/model/dimension/kind; every output is dimension-validated with no padding/truncation/fallback.

- [ ] Write failing unit tests for deterministic dimension, repeatability, input distinction, batch order, and dimension mismatch.
- [ ] Run embedding unit tests and observe expected import/behavior failures.
- [ ] Implement provider boundary and deterministic provider; re-run unit tests to green without loading a real model.
- [ ] Add pinned compatible `sentence-transformers` dependency and lazy real provider with typed unavailable errors.
- [ ] Install dependencies in the existing backend environment; if network sandbox blocks, request approved download access rather than switching model.
- [ ] Run a real provider smoke that loads the reviewed model and emits a correctly dimensioned vector; record actual dimension/provider metadata.

### Task 3: Add Qdrant derived index and freshness lifecycle

**Files:**
- Create: `backend/tests/test_retrieval_vector_store.py`
- Create: `backend/tests/test_qdrant_integration.py`
- Create: `backend/app/services/retrieval/vector_store.py`
- Create: `backend/app/services/retrieval/indexing.py`
- Modify: `backend/app/exceptions.py`
- Create: `scripts/build_retrieval_index.py`

**Interfaces:**
- Produce `DenseVectorStore` abstraction, `QdrantDenseVectorStore`, deterministic UUID5 point IDs, cosine collections sized from provider descriptors, exact search, payload `{entity_id, document_version, document_fingerprint, cities, seniority|seniorities}`, explicit payload filters, `build_index`, and `validate_freshness`.
- Missing, stale, embedding unavailable, and vector-store unavailable failures map to typed domain errors without raw Qdrant details.

- [ ] Write failing fake-store tests for collection creation, descriptor/output dimension validation, deterministic mapping, payload allowlist, missing/stale ID/fingerprint/version cases, and exact-search request policy.
- [ ] Run unit tests and observe expected failures.
- [ ] Implement the abstraction, Qdrant adapter, payload builder, indexer, and typed errors; re-run unit tests to green.
- [ ] Write real-Qdrant integration tests gated by required `QDRANT_TEST_URL` and unique UUID collection names, covering create/upsert/search/filter/fingerprint/fresh/stale/missing/cleanup.
- [ ] Start/confirm local Qdrant, run `test_qdrant_integration.py`, and require zero skipped.
- [ ] Implement `scripts/build_retrieval_index.py --entity candidates|jobs|all` using PostgreSQL records, real provider, and no evaluator imports.

### Task 4: Add bidirectional runtime retrieval service and APIs

**Files:**
- Create: `backend/tests/test_retrieval_service.py`
- Create: `backend/tests/test_retrieval_api.py`
- Create: `backend/app/services/retrieval/service.py`
- Create: `backend/app/api/routes/retrieval.py`
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/repositories/candidate_repository.py`
- Modify: `backend/app/repositories/job_repository.py`

**Interfaces:**
- Produce one `RetrievalService` for Job→Candidate and Candidate→Job, strategies `dense|sparse|hybrid`, default hybrid/top-k 10, channel pool `min(eligible_count, max(20, top_k*3))`, explicit city/seniority eligibility, channel diagnostics, equal-weight RRF, and tie-break `(score desc, best channel rank asc, entity_id asc)`.
- Routes: `POST /api/v1/retrieval/jobs/{job_id}/candidates` and `POST /api/v1/retrieval/candidates/{candidate_id}/jobs`.

- [ ] Write failing service tests for both directions and all strategies, default no-filter corpus, explicit filter reduction, top-k, diagnostics, stable ties, no labels/feature scores, freshness-before-dense, and failure mapping.
- [ ] Run service tests and observe expected failures.
- [ ] Add repository full-corpus retrieval reads and implement minimal service; re-run service tests to green.
- [ ] Write failing FastAPI tests for success envelopes/request IDs/default hybrid, reverse route, strict invalid top-k/strategy/filter, not found, missing/stale index, and unavailable vector store.
- [ ] Run API tests and observe expected failures.
- [ ] Wire dependencies/routes/error behavior and re-run API tests to green.
- [ ] Add architecture regression test proving runtime retrieval modules do not import/read label, pairwise, split, or evaluator data and responses expose no grades/vectors.

### Task 5: Add isolated offline evaluation and seal the config

**Files:**
- Create: `backend/tests/test_retrieval_evaluation.py`
- Create: `backend/app/services/retrieval/evaluation.py`
- Create: `scripts/evaluate_retrieval.py`
- Create: `docs/retrieval-design.md`
- Create: `docs/retrieval-evaluation.md`
- Create after sealed runs: `data/eval/phase4_retrieval_report.json`
- Modify: `README.md`
- Modify: `docs/development-roadmap.md`
- Modify: `docs/architecture.md`
- Modify: `docs/api-design.md`

**Interfaces:**
- Evaluator alone loads frozen labels/splits; it verifies exact frozen candidate corpus and query IDs, fixes relevance as grades `>=2`, computes Recall@5/10/20, HitRate@5/10, optional MRR, and reports judged coverage without treating unlabeled pairs as negatives.
- Stable config fingerprint includes document version/fields, real model/provider, BM25 params, RRF/pool policy, relevance threshold, and K values.

- [ ] Confirm label coverage from current files before fixing metric semantics; document why grades 2/3 are retrieval-relevant from the existing labeling guide.
- [ ] Write failing evaluator tests for metrics, incomplete-judgment handling, exact corpus integrity, runtime-output isolation, label mutation not affecting retrieval output, and deterministic config fingerprint.
- [ ] Run evaluator tests and observe expected failures.
- [ ] Implement evaluator and CLI; re-run tests to green.
- [ ] Write retrieval design/evaluation docs and update project docs to Phase 4 `In Progress`, Qdrant-derived-state semantics, first-stage API semantics, and synthetic metric honesty.
- [ ] Build real indexes and run train/dev evaluation only.
- [ ] Fix correctness bugs only; lock the approved constants/document fields and write/print config fingerprint before any test query evaluation.
- [ ] Run the final test evaluation once and write one deterministic report containing train/dev/test strategy metrics and no volatile timing/path data.
- [ ] Do not change retrieval algorithm/config/documents after inspecting test metrics.

### Task 6: Full verification and review handoff

**Files:**
- Inspect all created/modified files; do not commit.

- [ ] Load and follow `verification-before-completion` before making any success claim.
- [ ] Run retrieval-specific tests and record passed/failed/skipped/warnings.
- [ ] Run full backend tests with explicit `TEST_DATABASE_URL` and `QDRANT_TEST_URL`; require zero failed and zero skipped.
- [ ] Run explicit PostgreSQL and Qdrant integration test files separately; require zero skipped.
- [ ] Run `scripts/freeze_dataset.py --check` and `scripts/validate_dataset.py`; verify all five hashes unchanged.
- [ ] Run Alembic `current` and `check`; require only `20260813_0001 (head)` and no new operations.
- [ ] Run seed and seeded-database verification; require 48 candidates and 24 jobs unchanged after any temporary data cleanup.
- [ ] Build backend Docker image, start all five existing services, and verify all are healthy.
- [ ] Build both real-model indexes and verify counts 48/24, dimensions, payload allowlist, fingerprints, and freshness.
- [ ] Execute dev Job→Candidate dense/sparse/hybrid, Candidate→Job dense/sparse/hybrid, and explicit/no-filter API smokes with request IDs.
- [ ] Run frontend test/lint/typecheck/build because shared Compose/project docs changed.
- [ ] Run `git diff --check`, inspect full `git diff`, `git diff --stat`, `git diff --name-only`, branch, HEAD, and status.
- [ ] Produce the exact 23-section user report and end only with `READY FOR PHASE 4 REVIEW` if every mandatory gate is evidenced; otherwise end `NOT READY FOR PHASE 4 REVIEW`.
