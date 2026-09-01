# Phase 12 Algorithm Story Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe the frozen local prototype as a Job-query-driven retrieval and ranking system in the real UI, README, and screenshots without changing algorithm or evaluation behavior.

**Architecture:** Keep the existing Next.js workbench and backend contracts. Add presentation-only stage and candidate-label helpers inside the matching-results feature, remove disabled navigation, and update the existing deterministic Phase 12 E2E to capture the final product. Documentation reads frozen artifacts; it does not regenerate or reinterpret them.

**Tech Stack:** Next.js 16, React 19, TypeScript, CSS Modules, Vitest, Playwright, FastAPI/Docker Compose, Markdown/Mermaid.

## Global Constraints

- Phase 11 Offline Evaluation and all selected artifacts remain unchanged.
- Do not change dataset labels, query splits, LTR feature order, CE experiment, retrieval/ranking logic, protocol, or results.
- Do not introduce a new framework or implement disabled placeholder pages.
- All behavior changes use RED → minimal GREEN.
- README and UI are Chinese-first while preserving necessary algorithm terminology.
- Screenshots come from the actual final application with synthetic data only.

---

### Task 1: Algorithm-first README landing page

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: frozen Phase 11 report values and existing architecture documents.
- Produces: Chinese-first GitHub landing page with a traceable recommendation-system narrative.

- [ ] Rewrite the first screen around `AI-powered Talent Matching & Recommendation System`.
- [ ] Add the Job-query → candidate pool → Top-K explanation.
- [ ] Add an Algorithm Pipeline and explicit Dense/Sparse/Hybrid responsibilities.
- [ ] List the exact ten frozen LTR feature names.
- [ ] Add Ranking Ownership, Evidence First, and Evaluation Driven Development sections.
- [ ] Keep Phase 11 metrics and claim limitations unchanged.

### Task 2: Recommendation-system semantics in the UI

**Files:**
- Modify: `frontend/src/features/matching-results/matching-results.test.tsx`
- Modify: `frontend/src/features/matching-results/matching-results-screen.tsx`
- Modify: `frontend/src/features/matching-results/app-sidebar.tsx`
- Modify: `frontend/src/features/matching-results/matching-results.module.css`

**Interfaces:**
- Consumes: existing `DemoRun`, `DemoStage`, MatchRun result order, and opaque Candidate IDs.
- Produces: presentation-only story/progress, Top-K explanation, friendly labels, and audit metadata.

- [ ] Add RED assertions for the Job-query/candidate-pool explanation, six stages, Chinese labels, LTR Score disclaimer, friendly candidate labels, visible technical IDs, and absence of disabled navigation.

```tsx
expect(screen.getByText(/岗位作为 Query/)).toBeTruthy();
expect(screen.getByText(/候选池 Top-K/)).toBeTruthy();
expect(screen.getByText(/不是概率、匹配百分比或录用概率/)).toBeTruthy();
expect(screen.queryByRole("button", { name: "Overview" })).toBeNull();
```

- [ ] Run `npm test -- matching-results.test.tsx` under Node 22 and observe meaningful failure.
- [ ] Implement the minimal JSX and CSS changes; do not change `runDemo` or backend ranking contracts.
- [ ] Run the focused test again and require GREEN.

### Task 3: Final E2E and screenshots

**Files:**
- Modify: `frontend/e2e/phase12.spec.ts`
- Create/update: `screenshots/phase12-product-home-1440x1024.png`
- Create/update: `screenshots/phase12-algorithm-workbench-1440x1024.png`
- Create/update: `screenshots/phase12-top-k-ranking-1440x1280.png`
- Create/update: `screenshots/phase12-evidence-explanation-1440x1024.png`
- Create/update: `screenshots/phase12-matchrun-trace-1440x1024.png`

**Interfaces:**
- Consumes: deterministic mock Provider, disposable PostgreSQL, isolated Qdrant, real Next.js/FastAPI pipeline.
- Produces: actual product evidence and stable GitHub-renderable images.

- [ ] Add E2E assertions for recommendation-system explanation, Top-K title, LTR disclaimer, Candidate ID metadata, and Chinese explanation/trace headings.
- [ ] Run the focused E2E and observe RED before UI implementation if the assertions are not already covered by Task 2 RED.
- [ ] Capture the four final screenshots from fixed viewports/locators after the E2E turns GREEN.
- [ ] Visually inspect every file for truncation, stale text, debug overlays, secrets, and personal data.

### Task 4: Documentation synchronization

**Files:**
- Modify: `README.md`
- Modify if needed: `docs/demo-guide.md`
- Modify if needed: `docs/portfolio-evidence.md`

**Interfaces:**
- Consumes: final UI copy, final screenshot names, frozen evaluation artifact.
- Produces: consistent recruiter demo and interview narrative.

- [ ] Reference the final screenshots using relative GitHub paths.
- [ ] Replace stale English UI instructions in the demo guide.
- [ ] Keep allowed/forbidden claims explicit and preserve the CE experiment-only decision.

### Task 5: Verification and protection audit

**Files:**
- Verify all changed files; do not add unrelated files.

- [ ] Run frontend unit tests, typecheck, lint, and production build under Node 22.
- [ ] Run Phase 12 browser E2E with disposable PostgreSQL/Qdrant and clean only exact disposable state.
- [ ] Run the Docker explanation-contract regression and actual Compose health/full demo smoke.
- [ ] Verify README links and screenshot paths.
- [ ] Run secret/privacy scans and `git diff --check`.
- [ ] Prove no Phase 11 artifact, evaluation code, label, split, model metadata, or ranking implementation changed.
- [ ] Report the dirty working tree truthfully; do not commit or push without explicit authorization.
