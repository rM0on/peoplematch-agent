# Phase 13 Recommendation Product Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the frozen 48-person system read as a Chinese-first Job-query-driven recommendation product without changing ranking or evaluation semantics.

**Architecture:** Add Chinese Demo fixtures to the existing deterministic extraction registry and a typed frontend-only Candidate display catalog. Existing API/service/retrieval/LTR contracts remain unchanged; the UI consumes current result IDs/order/scores and enriches only their presentation. Documentation and screenshots are regenerated from the real final application.

**Tech Stack:** FastAPI, Pydantic, deterministic structured-output Provider, Next.js 16, React 19, TypeScript, CSS Modules, Vitest, Playwright, Docker Compose.

## Global Constraints

- Dataset `1.0.0`, all 48 frozen Candidate Profiles, labels, query splits, retrieval, feature order, LTR/CE models, Phase 11 protocol/artifacts/results remain unchanged.
- Chinese display metadata is frontend-only and cannot enter ranking, Evidence, or evaluation fingerprints.
- Chinese deterministic fixtures are additive Demo inputs only and cannot enter Offline Evaluation.
- Preserve Phase 0.5 visual language and existing routes; no new framework or large refactor.
- Every behavior change follows RED → minimal GREEN.
- Generate screenshots only from the actual final application with synthetic data.
- Create one final commit and do not push.

---

### Task 1: Chinese deterministic Demo fixtures

**Files:**
- Create: `data/samples/extraction/candidate_phase13_zh_resume.txt`
- Create: `data/samples/extraction/candidate_phase13_zh_output.json`
- Create: `data/samples/extraction/job_phase13_zh.txt`
- Create: `data/samples/extraction/job_phase13_zh_output.json`
- Modify: `backend/app/services/profile_extraction/mock_provider.py`
- Modify: `backend/app/api/routes/demo.py`
- Modify: `backend/tests/test_phase12_demo_api.py`
- Modify: `backend/tests/test_extraction_parser.py`

**Interfaces:**
- Consumes: `MockStructuredOutputProvider.from_fixture_directory(Path)` and `/api/v1/demo/samples`.
- Produces: two additional registered fingerprints and Chinese `DemoSamplesData` text.

- [ ] Add tests asserting `/demo/samples` returns Chinese/English mixed synthetic text and both texts parse through the deterministic Provider.
- [ ] Run the focused backend tests and observe failure because the fixtures are absent/unregistered.
- [ ] Add schema-valid fixtures and register them alongside existing pairs; point only the Demo samples endpoint at the new pair.
- [ ] Run the focused backend tests and require GREEN.

### Task 2: Frozen Candidate display catalog

**Files:**
- Create: `frontend/src/features/matching-results/candidate-display-metadata.ts`
- Create: `frontend/src/features/matching-results/candidate-display-metadata.test.ts`
- Modify: `frontend/src/features/matching-results/matching-results-screen.tsx`
- Modify: `frontend/src/features/matching-results/matching-results.test.tsx`

**Interfaces:**
- Produces: `getCandidatePresentation(candidateId, inputDraft?)` returning display label, direction, and strengths.
- Consumes: frozen Candidate IDs and optional runtime `CandidateDraft`; never mutates or sends data to the backend.

- [ ] Add RED tests for complete `cand_001`–`cand_048` coverage, unique stable labels, Chinese directions, strengths, and unknown-ID fallback.
- [ ] Run focused Vitest and observe meaningful failure because the catalog does not exist.
- [ ] Implement the typed catalog and integrate it into Top-K/detail cards without changing result order or score values.
- [ ] Run focused tests and require GREEN.

### Task 3: Recommendation Story Mode and ranking presentation

**Files:**
- Modify: `frontend/src/features/matching-results/matching-results.test.tsx`
- Modify: `frontend/src/features/matching-results/matching-results-screen.tsx`
- Modify: `frontend/src/features/matching-results/matching-results.module.css`

**Interfaces:**
- Consumes: existing `DemoStage`, `DemoRun`, MatchRun results, and presentation catalog.
- Produces: seven-step Story Mode and Chinese-first Top-K cards.

- [ ] Add RED assertions for the Job Query/Candidate Pool explanation, seven stages, `岗位候选池 Top-K 推荐`, indexed/final counts, `排序模型分值（LTR Score）`, non-probability warning, direction, strengths, and secondary technical ID.
- [ ] Run focused Vitest and observe copy/layout contract failures.
- [ ] Apply minimal JSX/CSS changes using existing tokens and responsive patterns.
- [ ] Run focused Vitest and require GREEN.

### Task 4: Historical review and Bad Case localization

**Files:**
- Modify: `frontend/src/features/phase10/phase10-ui.test.tsx`
- Modify as required: `frontend/src/features/phase10/historical-feedback-entry.tsx`
- Modify as required: `frontend/src/features/phase10/feedback-panel.tsx`
- Modify as required: `frontend/src/features/phase10/bad-case-list-screen.tsx`
- Modify as required: `frontend/src/features/phase10/bad-case-detail-screen.tsx`
- Modify: `frontend/src/features/matching-results/matching-results-screen.tsx`

**Interfaces:**
- Consumes: unchanged Phase 10 API enums and immutable history.
- Produces: Chinese user-visible labels while preserving payload values and workflow state semantics.

- [ ] Add RED assertions for Chinese dialog, tabs, fields, buttons, empty/error/pagination copy, and absence of identified recruiter-visible English phrases.
- [ ] Run Phase 10 focused tests and observe meaningful copy failures.
- [ ] Add presentation label maps and replace only visible text; do not alter API payloads.
- [ ] Run Phase 10 focused tests and require GREEN.

### Task 5: README and Demo documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/demo-guide.md`
- Modify: `docs/portfolio-evidence.md`
- Modify: `docs/development-roadmap.md`

**Interfaces:**
- Consumes: frozen Phase 11 metrics and final UI terminology.
- Produces: Chinese-first Phase 13 product narrative and honest status.

- [ ] Record Phase 13 as the active/completed product-experience enhancement without changing earlier phase claims.
- [ ] Explain the 48-person frozen pool and presentation-only metadata boundary.
- [ ] Keep the pipeline, LLM/ranking ownership, evaluation metrics, and limitations unchanged.
- [ ] Update Demo instructions to the Chinese sample and final visible controls.

### Task 6: Browser E2E and screenshots

**Files:**
- Modify: `frontend/e2e/phase12.spec.ts`
- Update: `screenshots/phase12-product-home-1440x1024.png`
- Update: `screenshots/phase12-algorithm-workbench-1440x1024.png`
- Update: `screenshots/phase12-top-k-ranking-1440x1280.png`
- Update: `screenshots/phase12-evidence-explanation-1440x1024.png`
- Update: `screenshots/phase12-matchrun-trace-1440x1024.png`

**Interfaces:**
- Consumes: deterministic mock mode, disposable PostgreSQL/Qdrant, real Next.js/FastAPI flow.
- Produces: final application screenshots and ranking-invariance evidence.

- [ ] Add E2E assertions for Chinese inputs, seven-step story, Candidate Pool count, display metadata, Top-K, raw LTR disclaimer, Evidence, MatchRun, history review, and no console/page errors.
- [ ] Run the E2E against pre-change UI where possible and observe contract failure.
- [ ] Run the completed E2E with fixed viewports, write the final screenshots, and verify historical result fingerprints/order remain unchanged through explanation.
- [ ] Inspect each screenshot visually for cropping, stale text, personal data, secrets, and debug UI.

### Task 7: Full verification, protection audit, and checkpoint

**Files:**
- Verify all changed files; do not add runtime artifacts.

**Interfaces:**
- Produces: fresh evidence for the final Phase 13 checkpoint.

- [ ] Run focused and full backend tests from repository root; report exact passed/failed/skipped counts.
- [ ] Under Node 22 run frontend test, typecheck, lint, and production build.
- [ ] Run the full browser E2E with explicit disposable database/Qdrant state and exact cleanup.
- [ ] Validate README links/images, GitHub-visible Markdown, secrets, privacy, and `git diff --check`.
- [ ] Compare frozen Phase 11 paths, dataset files, labels, splits, model metadata, retrieval/features/ranking, and selected artifacts against `ced396c5` and require no changes.
- [ ] Review actual code, product screenshots, and README; close all blockers/majors/integrity minors.
- [ ] Create one final Phase 13 checkpoint commit and verify clean Git state; do not push.
