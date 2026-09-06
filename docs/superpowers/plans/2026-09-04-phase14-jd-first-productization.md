# Phase 14 JD-first Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Resume+JD demo entry with a JD-only recommendation flow and move Resume ingestion into a dedicated Candidate Pool workflow without changing frozen ranking or evaluation behavior.

**Architecture:** Reuse the existing typed frontend clients and Phase 2/3/8/9 APIs. New frontend pages orchestrate already-frozen backend capabilities; no ranking, retrieval, feature, model, dataset, or evaluation implementation changes are permitted.

**Tech Stack:** Next.js 16, React 19, TypeScript, CSS Modules, FastAPI, Pydantic, PostgreSQL, Qdrant, Vitest, Playwright.

## Global Constraints

- Preserve the frozen 48 Candidate records and all Phase 11 artifacts.
- Do not change Retrieval, Feature Engineering, LambdaMART, Cross-Encoder, Evidence contracts, labels, splits, or evaluation results.
- Use RED-first tests for every behavior change.
- Keep deterministic mock mode and Chinese synthetic fixtures.
- Create one final Phase 14 checkpoint; do not push.

---

### Task 1: JD-only Recommendation Contract

**Files:**
- Modify: `frontend/src/lib/demo-api.ts`
- Modify: `frontend/src/types/demo.ts`
- Test: `frontend/src/lib/demo-api.test.ts`

- [ ] Write a failing test proving recommendation parses only the Job and never calls Candidate parse.
- [ ] Run the focused test and verify the failure is caused by the old Resume-first orchestration.
- [ ] Change the typed client to Job → index → MatchRun → Explanation.
- [ ] Run focused tests to GREEN.

### Task 2: JD-first Recommendation UI

**Files:**
- Modify: `frontend/src/features/matching-results/matching-results-screen.tsx`
- Modify: `frontend/src/features/matching-results/matching-results.module.css`
- Modify: `frontend/src/features/matching-results/matching-results.test.tsx`

- [ ] Write failing UI tests for a single JD field, JD-only sample loading, `开始推荐`, rank-based display tier, and separated explanation sections.
- [ ] Run focused tests and record meaningful RED.
- [ ] Implement the smallest UI change using existing design tokens and metadata.
- [ ] Run focused tests to GREEN.

### Task 3: Candidate Pool Management

**Files:**
- Create: `frontend/src/features/candidate-pool/candidate-pool-screen.tsx`
- Create: `frontend/src/features/candidate-pool/candidate-pool.module.css`
- Create: `frontend/src/features/candidate-pool/candidate-pool.test.tsx`
- Create: `frontend/src/app/candidates/page.tsx`
- Modify: `frontend/src/lib/demo-api.ts`
- Modify: `frontend/src/types/demo.ts`

- [ ] Write failing tests for list, Resume sample load, preview without persistence, confirmation, index refresh, and safe errors.
- [ ] Implement typed Candidate list/preview/ingestion clients and runtime validators.
- [ ] Implement the Candidate Pool page with Structured Profile preview and explicit confirmation.
- [ ] Run focused tests to GREEN.

### Task 4: Navigation And Recommendation History

**Files:**
- Modify: `frontend/src/features/matching-results/app-sidebar.tsx`
- Create: `frontend/src/features/recommendation-history/recommendation-history-screen.tsx`
- Create: `frontend/src/app/runs/page.tsx`
- Test: `frontend/src/features/matching-results/matching-results.test.tsx`

- [ ] Write failing navigation tests for four working destinations.
- [ ] Add Candidate Pool and recommendation-history routes using existing UI components.
- [ ] Run focused tests to GREEN.

### Task 5: Documentation And Browser Contract

**Files:**
- Modify: `README.md`
- Modify: `docs/demo-guide.md`
- Modify: `docs/development-roadmap.md`
- Modify: `frontend/e2e/phase12.spec.ts`

- [ ] Update E2E assertions first for Candidate ingestion followed by JD-only recommendation.
- [ ] Update Chinese-first product documentation and honest Provider boundary.
- [ ] Run frontend and backend focused suites.

### Task 6: Final Verification And Evidence

**Files:**
- Create: `screenshots/phase14-*.png`

- [ ] Run full backend pytest.
- [ ] Run frontend tests, typecheck, lint, and production build on Node 22.
- [ ] Run disposable PostgreSQL/Qdrant Browser E2E and inspect all accepted screenshots.
- [ ] Audit README links, secrets, privacy, and `git diff --check`.
- [ ] Prove protected Phase 11/algorithm paths have zero diff from `fd453f0`.
- [ ] Create one checkpoint commit: `feat: productize jd-first talent recommendation workflow`.
