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

**Status:** Planned

- **Objective:** Convert permitted raw sandbox/public text into reviewable structured profiles.
- **Primary deliverables:** Provider boundary, candidate/job extraction services, prompt/schema versioning, deterministic fixtures, human-review flow.
- **Dependency:** Phase 2 persistence and Phase 1 contracts.
- **Quality gate:** Extraction tests cover missing/unsupported evidence and provider failure; outputs preserve source traceability; no ranking is performed.

## Phase 4 — Hybrid Retrieval

**Status:** Planned

- **Objective:** Produce auditable candidate/job recall sets using lexical and vector retrieval.
- **Primary deliverables:** Qdrant collection design, embedding-provider boundary, lexical retrieval, fusion strategy, retrieval run records.
- **Dependency:** Phase 3 structured profiles.
- **Quality gate:** Retrieval is evaluated on a documented sandbox set; collection/schema versions are traceable; no final-ranking claims are made.

## Phase 5 — Evidence-aware Feature Scoring

**Status:** Planned

- **Objective:** Compute typed, inspectable features for skills, evidence, direction, constraints, and context.
- **Primary deliverables:** Feature registry/versioning, deterministic feature computations, constraint handling, feature-level tests.
- **Dependency:** Phase 4 recall candidates and stable profiles.
- **Quality gate:** Each feature has a documented meaning/source; missing evidence is not treated as evidence; deterministic fixtures pass.

## Phase 6 — Learning-to-Rank

**Status:** Planned

- **Objective:** Train and compare a learned ranking stage without handing final ordering to an LLM.
- **Primary deliverables:** Training data contract, baseline ranker, LTR experiment pipeline, model/version metadata, offline comparison report.
- **Dependency:** Phase 5 features and documented labels.
- **Quality gate:** Fixed data split and baseline are documented; results are reproducible; no online-impact claims or cherry-picked metrics.

## Phase 7 — Cross-Encoder Reranking

**Status:** Planned

- **Objective:** Evaluate a bounded reranking stage over retrieved/ranked candidates.
- **Primary deliverables:** Cross-encoder provider boundary, top-k rerank flow, batching/configuration, offline comparison.
- **Dependency:** Phase 6 ranking outputs.
- **Quality gate:** Latency/cost are measured only in the local sandbox; comparison uses the same dataset and labels; fallback behavior is explicit.

## Phase 8 — Match-run Orchestration & Traceability

**Status:** Planned

- **Objective:** Orchestrate the pipeline as inspectable, versioned match runs.
- **Primary deliverables:** Run state model, stage execution contract, request/run correlation, retry/idempotency rules, run-detail API.
- **Dependency:** Phases 4–7 stage contracts.
- **Quality gate:** A run can be reproduced from captured versions/configuration; partial failure is visible; no fake fallback success.

## Phase 9 — Evidence-grounded Explanation

**Status:** Planned

- **Objective:** Explain an existing rank using cited evidence and explicit gaps.
- **Primary deliverables:** Explanation input contract, grounded prompt/service, evidence citations, uncertainty/gap handling, hallucination tests.
- **Dependency:** Phase 8 traceable runs and ranking evidence.
- **Quality gate:** Explanations cannot alter rank; every positive claim maps to source evidence; unsupported claims fail tests.

## Phase 10 — Feedback & Bad Case Review

**Status:** Planned

- **Objective:** Capture explicit feedback and attribute bad recommendations to pipeline/data categories.
- **Primary deliverables:** Feedback schema/API, immutable run links, bad-case taxonomy, review workflow, exportable review records.
- **Dependency:** Phase 9 explanations and Phase 8 match runs.
- **Quality gate:** Feedback never mutates historical runs; taxonomy is documented; privacy review passes for sandbox data.

## Phase 11 — Offline Evaluation

**Status:** Planned

- **Objective:** Compare retrieval/ranking configurations through reproducible local evaluation.
- **Primary deliverables:** Dataset/version manifest, label guidance, Recall/NDCG/MRR implementations, run comparison, bad-case slices.
- **Dependency:** Phase 10 review signals and earlier stage implementations.
- **Quality gate:** Metric implementations have reference tests; reports identify split/config/code version; results make no online or commercial claims.

## Phase 12 — Local Prototype Hardening & Demo

**Status:** Planned

- **Objective:** Consolidate a reliable local demonstration and developer handoff without claiming production readiness.
- **Primary deliverables:** End-to-end sandbox demo, operational runbook, failure-mode documentation, performance observations, final architecture reconciliation.
- **Dependency:** Phase 11 evaluation complete.
- **Quality gate:** Clean-machine local setup is reproducible; end-to-end checks pass; all capabilities/limitations are accurately documented; no production claim is introduced.
