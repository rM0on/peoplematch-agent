# Development Roadmap

Only the phase explicitly requested by the user may be implemented. Status values are `In Progress`, `Completed`, or `Planned`; planned deliverables are not current capabilities.

## Phase 0 — Product Definition & Engineering Bootstrap

**Status:** Completed

- **Objective:** Establish an honest product definition and runnable monorepo foundation.
- **Primary deliverables:** README, PRD, architecture/API/roadmap docs, FastAPI liveness and request tracing, minimal Next.js shell, tests, Docker Compose, PostgreSQL/Redis/Qdrant configuration, empty Alembic foundation.
- **Dependency:** None.
- **Quality gate:** Backend tests pass; frontend test/lint/typecheck/build pass; Compose configuration is valid; Docker runtime and health are verified when Docker is available; docs distinguish current and planned behavior.

## Phase 0.5 — Product Design / UI System

**Status:** Completed

- **Objective:** Define the visual language and interaction patterns before full product flows.
- **Primary deliverables:** Phase 0.5A defined information architecture, UX flows, design-system direction, state patterns, screenshot strategy, and three visual directions. Phase 0.5B implemented the explicitly selected Evidence-first fusion for the Matching Results design mock.
- **Dependency:** Phase 0 complete.
- **Quality gate:** The selected direction preserves evidence-first hierarchy, compact rank comparison, and a lightweight trace; the frontend passes tests, lint, typecheck, build, keyboard/responsive review, and reference-image QA. All illustrative values stay labeled as design mock data, and no future business workflow is implemented.

## Phase 1 — Dataset & Schema

**Status:** Completed

- **Objective:** Define versioned candidate/job contracts and a deterministic evidence-aware sandbox dataset for later retrieval, ranking, and evaluation work.
- **Primary deliverables:** Pydantic v2 contracts, 48 synthetic candidates, 24 fictional jobs, graded and pairwise `synthetic_curated` labels, job-query splits, hard negatives, JSON Schema exports, descriptive statistics, seed manifest, dataset freeze manifest, and dataset documentation.
- **Dependency:** Phase 0.5 complete.
- **Quality gate:** Data contracts and dataset integrity tests pass; 48/24/288/48 scale and 14/5/5 query split are validated; skill claims and evidence are structurally distinct; dataset `1.0.0` and its test queries are hash-pinned after external review; no database, parser, retrieval, ranking, or metric implementation is introduced.

## Phase 2 — Persistence & Backend Domain Layer

**Status:** Completed

- **Objective:** Persist versioned candidate/job profiles and their evidence safely in PostgreSQL.
- **Primary deliverables:** Async SQLAlchemy models, normalized nested profile data, repositories, domain services, the first real Alembic revision, typed CRUD APIs, frozen-dataset import, and transaction/error/integration tests.
- **Dependency:** Phase 1 contracts stable.
- **Quality gate:** Upgrade/downgrade migrations pass on PostgreSQL; frozen seed hashes and idempotency are verified; repository/service/API integration tests and canonical roundtrips pass; no fake ranking data is stored.

## Phase 3 — Structured Profile Extraction

**Status:** Completed

- **Objective:** Convert permitted raw sandbox/public text into reviewable structured profiles.
- **Primary deliverables:** Provider-agnostic structured-output boundary, deterministic mock provider, candidate/job prompt builders and draft schemas, strict JSON/Pydantic validation, bounded repair, preview/persistence APIs, and synthetic fixtures.
- **Dependency:** Phase 2 persistence and Phase 1 contracts.
- **Quality gate:** Extraction tests cover missing/unsupported evidence, malformed output, bounded repair, provider failures, provenance, PostgreSQL persistence, and source traceability; no real LLM, retrieval, or ranking is implemented.

## Phase 4 — Hybrid Retrieval

**Status:** Completed

- **Objective:** Produce auditable candidate/job recall sets using lexical and vector retrieval.
- **Primary deliverables:** Versioned retrieval documents, local pretrained embedding-provider boundary, derived Qdrant indexes, BM25 lexical retrieval, explicit metadata filters, RRF fusion, response diagnostics, and fixed-sandbox offline retrieval evaluation.
- **Dependency:** Phase 3 structured profiles.
- **Quality gate:** Retrieval documents and indexes exclude construction metadata and labels; real local dense retrieval and Qdrant integration run successfully; Dense/Sparse/Hybrid are evaluated with a v4-internal dev-sealed config on the documented post-exposure fixed synthetic sandbox benchmark; collection/document versions are traceable; no final-ranking claims are made. External review passed before status became Completed.

## Phase 5 — Feature Engineering

**Status:** Completed / Frozen

- **Objective:** Compute typed, inspectable, label-free Candidate/Job pair features after retrieval without scoring or changing retrieval order.
- **Primary deliverables:** Versioned feature registry/fingerprint, stable ordered model contract, separate diagnostics, deterministic normalization/matching, bidirectional inspection APIs, train/dev-only descriptive feature audit, and feature/API/leakage tests.
- **Dependency:** Phase 4 recall candidates and stable profiles.
- **Quality gate:** Each feature has a documented meaning/source/direction/range/missing policy; claimed skills and supporting evidence remain distinct; labels/construction metadata do not affect runtime values; both directions preserve Phase 4 order; no LTR, final score, reranking, Test tuning, or migration is introduced. Independent source review passed and the Phase 5 implementation is frozen for the Phase 6 handoff.

## Phase 6 — Learning-to-Rank

**Status:** Completed / Frozen

- **Objective:** Train and compare one deterministic learned ranking stage without handing final ordering to an LLM.
- **Primary deliverables:** Versioned LambdaMART contract, explicit Train/Dev judged-pair dataset, native model and provenance metadata, judged-set Dev comparison report, Job-to-Candidates Hybrid-pool ranking API, and leakage/integrity tests.
- **Dependency:** Phase 5 features and documented labels.
- **Quality gate:** Fixed data split and baseline are documented; Train/Dev rows are explicit judgments only; no Test rows or Test metrics are used; exact Phase 5 fingerprint/order is validated; deterministic native model reproduction, artifact hashes, runtime contract checks, full regressions, and honest synthetic limitations are documented. No online-impact claims or cherry-picked metrics.

## Phase 7 — Cross-Encoder Reranking

**Status:** Completed / Frozen

- **Objective:** Evaluate a bounded reranking stage over retrieved/ranked candidates.
- **Primary deliverables:** Frozen pretrained Cross-Encoder provider boundary, immutable model/text manifests, Job-to-Candidates top-k rerank flow, batching/configuration, Dev judged-set comparison, and local CPU latency diagnostics. No fine-tuning or Test evaluation.
- **Dependency:** Phase 6 ranking outputs.
- **Quality gate:** Immutable revision and snapshot hashes are verified; latency is measured only in the local sandbox; comparison uses the same explicitly judged Dev candidates and labels; fallback behavior is explicit; Phase 4/5/6 contracts remain frozen. The frozen result is an optional experimental comparison: Phase 6 LambdaMART remains the stronger current synthetic Dev baseline, with no fine-tuning or production claim.

## Phase 8 — Match-run Orchestration & Traceability

**Status:** Completed / Frozen

- **Objective:** Orchestrate the pipeline as inspectable, versioned match runs.
- **Primary deliverables:** Durable MatchRun/MatchResult/RunStep state, actual-stage workflow contract, request/run correlation, historical snapshots and observed runtime provenance protected by the application/repository contract, failure retention, create/detail/list APIs, and explicit rerun/no-idempotency v1 rules.
- **Dependency:** Phases 4–7 stage contracts.
- **Quality gate:** Historical results and versions/configuration are inspectable without reranking; partial failure remains durable; result persistence is atomic; completed/failed runs are terminal and immutable through the application/repository contract; no fake fallback success, Test evaluation, explanation, or ranking change.

## Phase 9 — Evidence-grounded Explanation

**Status:** Completed / Frozen

- **Objective:** Build historical-only evidence facts and a provider-neutral backend that can produce bounded, cited explanations without allowing an LLM to author facts or alter ranking.
- **Primary deliverables:** Frozen explanation persistence/contracts and deterministic Evidence Engine; opaque provider-reference projection; versioned structured-plan prompt; deterministic mock and OpenAI-compatible DeepSeek transport; closed reference resolution, semantic grounding, fixed-template rendering, bounded repair/audit persistence, and explanation create/detail/list APIs.
- **Dependency:** Phase 8 traceable runs and ranking evidence.
- **Quality gate:** Explanations cannot alter rank; providers cannot author factual prose; every rendered claim maps to deterministic source evidence; unsupported references or operations fail closed; no provider call holds a database transaction.

## Phase 10 — Feedback & Bad Case Review

**Status:** Completed / Frozen

- **Objective:** Capture explicit feedback and attribute bad recommendations to pipeline/data categories.
- **Primary deliverables:** Frozen Feedback/BadCase contracts, persistence, repositories, business/API boundary, privacy-safe Phase 11 export projection, and Evidence-first product integration.
- **Dependency:** Phase 9 explanations and Phase 8 match runs.
- **Quality gate:** Feedback never mutates historical runs; review writes remain append-only and concurrency-safe; the UI consumes server-derived historical context, handles stale revisions explicitly, and passes privacy, accessibility, responsive, and real PostgreSQL E2E review before Phase 10 freeze.

## Phase 11 — Offline Evaluation

**Status:** In Progress — implementation and Dev evidence frozen; formal Test sealed / not run

- **Objective:** Compare retrieval/ranking configurations through reproducible, leakage-aware local evaluation without treating unjudged pairs or Phase 10 review state as ground truth.
- **Primary deliverables:** Frozen `phase11_eval_protocol_v1`, dataset/split and Test-seal policy, stage-aware comparable strategy cohorts, exact Recall/NDCG/MRR/pairwise semantics, explanation/review/latency diagnostics, immutable evaluation manifests, RED-first runner, and reproducible Dev report. Formal Test remains the closure gate.
- **Dependency:** Phase 10 review signals and earlier stage implementations.
- **Quality gate:** The architecture in `docs/offline-evaluation.md` was frozen before implementation; metric implementations have independent reference and adversarial unjudged tests; candidate-pool comparability, vector-state provenance, immutability, and the explicit Test guard are enforced; two identical Dev runs reproduce the quality fingerprint; formal Test remains sealed and must run only after this implementation freeze; reports identify split/config/code/artifact versions and preserve the Phase 4 post-exposure caveat; no online, commercial, hiring-accuracy, or production claim is made.

## Phase 12 — Local Prototype Hardening & Demo

**Status:** Planned

- **Objective:** Consolidate a reliable local demonstration and developer handoff without claiming production readiness.
- **Primary deliverables:** End-to-end sandbox demo, operational runbook, failure-mode documentation, performance observations, final architecture reconciliation.
- **Dependency:** Phase 11 evaluation complete.
- **Quality gate:** Clean-machine local setup is reproducible; end-to-end checks pass; all capabilities/limitations are accurately documented; no production claim is introduced.
