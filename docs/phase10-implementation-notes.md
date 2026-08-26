# Phase 10B Feedback Loop and Bad Case Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task. Every production behavior follows RED → GREEN → REVIEW. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auditable feedback and BadCase backend that attaches typed review records to immutable Phase 8/9 history without mutating ranking, evidence, or explanations.

**Architecture:** The implementation stays in the modular monolith and follows API → service → repository → PostgreSQL. Feedback is immutable; BadCase is a row-locked workflow aggregate; source links, analyses, resolution actions, and lifecycle transitions are append-only. Historical Job, Candidate, rank, and explanation ownership are resolved server-side from frozen MatchRun/Explanation records.

**Tech Stack:** Python 3.9+, FastAPI, Pydantic v2, async SQLAlchemy, PostgreSQL, Alembic, pytest.

## Global Constraints

- Baseline is `80e9637eb3126600e2fd3bc72b6ca1e38944c680` on `main`.
- Do not modify Phase 4–9.4 implementation, contracts, migrations, or tests.
- Do not modify the frontend; Phase 10A leaves Bad Case pages as future information architecture.
- Do not implement Phase 11 metrics, datasets, benchmarks, evaluation runs, or strategy comparison.
- Do not add authentication, users, queues, Redis/Celery/Kafka business usage, retraining, or model changes.
- Feedback and BadCase records never update MatchRun, MatchResult, Evidence Bundle, ExplanationRun, or ExplanationOutput.
- Caller-supplied historical identity is treated as a selector; Job/Candidate/rank ownership is derived from persisted history.
- Human notes are optional, bounded, untrusted review content and never provider input or model truth.
- One final commit only, using `feat: implement feedback loop and bad case management system`; no push.

---

## File Map

### New production files

- `backend/app/models/feedback.py` — immutable feedback and deterministic system-signal rows.
- `backend/app/models/bad_case.py` — BadCase aggregate, source links, analyses, actions, and transitions.
- `backend/app/schemas/feedback.py` — discriminated feedback requests and response records.
- `backend/app/schemas/bad_cases.py` — closed taxonomy, lifecycle, PATCH operations, list/detail responses.
- `backend/app/repositories/feedback_repository.py` — historical lookup plus immutable feedback persistence.
- `backend/app/repositories/bad_case_repository.py` — atomic create, detail/list, and row-locked update transactions.
- `backend/app/services/feedback/contracts.py` — feedback contract version and semantic mappings.
- `backend/app/services/feedback/service.py` — target ownership validation and server-owned identity derivation.
- `backend/app/services/bad_cases/taxonomy.py` — symptom/root-cause/action compatibility maps.
- `backend/app/services/bad_cases/service.py` — case creation and constrained lifecycle orchestration.
- `backend/app/api/routes/feedback.py` — create/detail endpoints using `ApiResponse`.
- `backend/app/api/routes/bad_cases.py` — create/list/detail/PATCH endpoints using `ApiResponse`.
- `backend/alembic/versions/20260826_0005_feedback_bad_case_management.py` — additive Phase 10 tables only.
- `data/contracts/feedback_record_v1.json` and `data/contracts/bad_case_v1.json` — checked-in strict schemas.

### Minimal existing-file changes

- `backend/app/api/dependencies.py` — construct Phase 10 services from the existing session factory.
- `backend/app/api/router.py` — register Phase 10 routes under `/api/v1`.
- `backend/app/exceptions.py` — typed feedback/BadCase errors.
- `backend/alembic/env.py` — import new metadata only.
- `README.md` and `docs/development-roadmap.md` — mark Phase 10B backend implementation accurately.

### New tests

- `backend/tests/test_feedback_contracts.py`
- `backend/tests/test_bad_case_contracts.py`
- `backend/tests/test_feedback_service.py`
- `backend/tests/test_bad_case_service.py`
- `backend/tests/test_feedback_bad_case_api.py`
- `backend/tests/test_feedback_bad_case_persistence_contract.py`
- `backend/tests/test_feedback_bad_case_postgres.py`

## Public Interfaces

```python
class FeedbackService:
    async def create(self, request: FeedbackCreateRequest) -> FeedbackResponse: ...
    async def get(self, feedback_id: str) -> FeedbackResponse: ...

class BadCaseService:
    async def create(self, request: BadCaseCreateRequest) -> BadCaseDetailResponse: ...
    async def get(self, bad_case_id: str) -> BadCaseDetailResponse: ...
    async def list(self, *, limit: int, offset: int, status=None, severity=None, category=None): ...
    async def update(self, bad_case_id: str, request: BadCaseUpdateRequest) -> BadCaseDetailResponse: ...
```

Feedback create requests are discriminated by `feedback_type` (`ranking`, `explanation`, `profile_data`). BadCase update accepts only `expected_status`, `expected_revision`, a valid next `status`, optional append-only `analysis`, optional append-only `resolution`, and transition/verification data. Extra and immutable fields fail Pydantic validation.

## Task 1 — Closed Contracts and Taxonomy

- [ ] Add RED tests proving invalid feedback types, target/value mismatches, unbounded notes, arbitrary metadata, invalid categories/statuses, bool/float revisions, and invalid lifecycle operations fail.
- [ ] Add RED artifact parity tests for `feedback_record_v1` and `bad_case_v1` with `additionalProperties=false`.
- [ ] Run the two contract test modules and confirm failure is caused by missing Phase 10 schemas.
- [x] Implement the minimum strict Pydantic contracts and closed compatibility maps.
- [x] Generate artifacts from the executable schemas and rerun focused tests.
- [x] Review that no arbitrary name/value, metadata, raw-document, label, split, or evaluation field is reachable.

## Task 2 — Additive Persistence Contract and Migration

- [ ] Add RED tests for exact tables/columns, named restrictive FKs, unique/check constraints, append-only child tables, and `0005` parent `0004`.
- [ ] Confirm failures are due to missing models/migration.
- [x] Implement ORM models and additive migration `20260826_0005`.
- [x] Import only the new model metadata from Alembic `env.py`.
- [x] Run persistence contract tests and model/schema parity checks.
- [x] Review that no Phase 8/9 table or column is altered and no raw provider/snapshot/evaluation payload column exists.

## Task 3 — Repository and Transaction Foundation

- [x] Add RED tests for create/get, invalid result ownership, cross-run pairwise targets, non-top1 target, explanation ownership, unknown/cross-owner evidence reference, historical profile resolution, and immutable supersession rules.
- [x] Confirm RED failures reach missing Phase 10 repository behavior.
- [x] Implement repository historical reads and immutable insert/get transactions.
- [x] Implement bounded supersession ancestry, fixed-query BadCase detail loading, append-only child persistence, and row-locked atomic root/transition updates.
- [x] Verify stale revision rejection and deterministic two-session PostgreSQL lock contention without timing sleeps.
- [ ] Implement service validation that derives Job/Candidate/rank from persisted Phase 8/9 owners.
- [x] Rerun focused tests and review that no current Candidate/Job repository or provider is called.

## Task 4 — BadCase Aggregate and Lifecycle

- [ ] Add RED tests for atomic case/source creation, category/feedback compatibility, lifecycle happy path, invalid skip, stale revision/status, analysis/root-cause mismatch, resolution/action mismatch, and immutable-field rejection.
- [ ] Confirm RED failures are caused by missing BadCase behavior.
- [ ] Implement create/get/list and row-locked update transactions.
- [ ] Append analysis, action, and transition records; never overwrite previous child records.
- [ ] Enforce `CREATED → REVIEWED → ROOT_CAUSE_IDENTIFIED → ACTION_PLANNED → RESOLVED → VERIFIED`, plus documented dismissal/duplicate/reopen dispositions only when their required references are present.
- [ ] Rerun focused tests and review atomicity/concurrency semantics.

## Task 5 — API Integration

- [ ] Add RED API tests for feedback create/get and BadCase create/list/get/PATCH success.
- [ ] Add adversarial 404/400/409/422 tests, including caller attempts to mutate historical identity or select arbitrary taxonomy strings.
- [ ] Register dependencies/routes and map service results into the existing `ApiResponse`/`PaginatedData` envelope.
- [ ] Rerun API tests and verify request IDs and safe typed errors.

## Task 6 — PostgreSQL Integrity

- [ ] Add PostgreSQL tests for migration from `0004` to `0005`, FK restrictions, immutable feedback, atomic source-link creation, append-only analysis/action/transition rows, stale/invalid transitions, rollback behavior, and two-session transition contention.
- [ ] Run against real PostgreSQL with no timing sleeps.
- [ ] Run `alembic upgrade head`, migration-from-`0004`, and `alembic check`.
- [ ] Review final persisted state and ensure source MatchRun/Explanation rows remain unchanged.

## Task 7 — Documentation and Full Verification

- [ ] Update README and roadmap only for truthful Phase 10B backend status; keep frontend and Phase 11 planned.
- [ ] Run Phase 10 focused tests.
- [ ] Run full backend tests from repository root.
- [ ] Run Phase 8 and Phase 9 PostgreSQL regressions plus Phase 10 PostgreSQL tests.
- [ ] Run `git diff --check`, inspect the complete diff, scan for secrets/local artifacts, and verify frozen paths.
- [ ] Create the single requested commit only after every required verification passes; do not push.

## Current Verification Baseline

From the repository root on the frozen baseline:

```text
python -m pytest backend/tests -q
689 passed, 32 skipped
```

The same suite run from `backend/` produced 13 import failures because repository-root `scripts` was outside `sys.path`; that invocation issue is not a source regression. All final full-suite runs must execute from the repository root.

## Phase 10B Status

Tasks 1 and 2 are frozen at checkpoint `d10fe9d695b78693061156170a9b796fa92dd87c`. The Task 3 repository and transaction foundation is implemented in the uncommitted working tree; business services and APIs have not started. Feedback persistence is append-only, supersession ancestry is bounded, historical Job/Candidate/rank/explanation/evidence owners are resolved only from Phase 8/9 records, and BadCase root status/revision plus transition history update atomically under a row lock. Repository methods own a short transaction when called independently and accept an already-active caller transaction without committing it, so Task 4 can compose historical resolution, append-only writes, and a lifecycle transition into one atomic unit. Caller rollback was verified to remove every Phase 10 write while preserving frozen source history. Bounded BadCase details explicitly identify any truncated child collections rather than presenting a partial history as complete. A deterministic PostgreSQL two-session race proves that one conflicting transition wins, the losing backend is blocked specifically by the winner backend, and the stale writer receives a typed concurrency error.

Task 3 hardening verification used PostgreSQL 16.14 in the disposable `peoplematch_task3_review_a01425` database. The Task 3 PostgreSQL repository/concurrency module passed `15 passed, 0 failed, 0 skipped`, including caller-owned transaction rollback and explicit bounded-projection tests; the frozen PostgreSQL regression modules passed `31 passed, 0 failed, 0 skipped`; Task 1/2 plus Task 3 contract tests passed `51 passed`; and the separated-process full backend suite passed `740 passed, 0 failed, 47 skipped`. Alembic head/current were both `20260826_0005` and `alembic check` reported no drift. Task 4 must still enforce business compatibility for feedback supersession, case symptom/source selection, supported/confirmed root-cause evidence, action semantics, and complete lifecycle orchestration using these repository primitives.

The PostgreSQL suites and the standard full backend regression remain separate pytest processes. Running in-process Alembic PostgreSQL execution before the full suite changes process-global logger state and causes one frozen extraction log-capture assertion to miss otherwise emitted completion records. That frozen test passes independently and with its adjacent module; the standard backend regression and the PostgreSQL suites also pass independently. This is a test-runner composition limitation, not a Phase 10 persistence correctness failure, and the frozen extraction implementation is unchanged.
