# Phase 10B Feedback Loop and Bad Case Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task. Every production behavior follows RED → GREEN → REVIEW. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Historical-plan note:** The task map and unchecked items below preserve the original Phase 10A implementation plan. `Phase 10B Status` and the dated verification paragraphs at the end are the current implementation record and supersede early statements that frontend work or intermediate checkpoints were still forbidden.

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
- `backend/app/repositories/system_signal_repository.py` — read-only deterministic SystemSignal lookup.
- `backend/app/services/feedback/contracts.py` — feedback contract version and semantic mappings.
- `backend/app/services/feedback/errors.py` — bounded service/API error model.
- `backend/app/services/feedback/service.py` — target ownership validation and server-owned identity derivation.
- `backend/app/services/feedback/transaction.py` — standalone or caller-owned short transaction scope.
- `backend/app/services/bad_cases/taxonomy.py` — symptom/root-cause/action compatibility maps.
- `backend/app/services/bad_cases/compatibility.py` — Task 4 semantic compatibility policy.
- `backend/app/services/bad_cases/projections.py` — bounded API and Phase 11-safe export projections.
- `backend/app/services/bad_cases/service.py` — case creation and constrained lifecycle orchestration.
- `backend/app/schemas/phase10.py` — closed API detail, source-link command, and review-export contracts.
- `backend/app/api/routes/phase10.py` — thin feedback and BadCase command/query endpoints using `ApiResponse`.
- `backend/alembic/versions/20260826_0005_feedback_bad_case_management.py` — additive Phase 10 tables only.
- `data/contracts/feedback_record_v1.json`, `data/contracts/bad_case_v1.json`, and `data/contracts/phase10_review_export_v1.json` — checked-in strict schemas.

### Minimal existing-file changes

- `backend/app/api/dependencies.py` — construct Phase 10 services from the existing session factory.
- `backend/app/api/router.py` — register Phase 10 routes under `/api/v1`.
- `backend/alembic/env.py` — import new metadata only.

### New tests

- `backend/tests/test_feedback_contracts.py`
- `backend/tests/test_bad_case_contracts.py`
- `backend/tests/test_feedback_bad_case_persistence_contract.py`
- `backend/tests/test_feedback_bad_case_repository_contract.py`
- `backend/tests/test_feedback_bad_case_repository_postgres.py`
- `backend/tests/test_phase10_business_services.py`
- `backend/tests/test_phase10_api.py`
- `backend/tests/test_phase10_api_postgres.py`
- `backend/tests/test_phase10_export_contract.py`
- `backend/tests/test_phase10_services_postgres.py`

## Public Interfaces

```python
class FeedbackService:
    async def create(self, request: FeedbackCreateRequest) -> FeedbackRecordV1: ...
    async def get(self, feedback_id: str) -> FeedbackRecordV1: ...

class BadCaseReviewService:
    async def create_detail(self, request: BadCaseCreateRequest) -> BadCaseApiDetailResponse: ...
    async def get_detail(self, bad_case_id: str, *, child_limit: int = 100) -> BadCaseApiDetailResponse: ...
    async def list_summaries(self, *, limit: int, offset: int): ...
    async def link_source_detail(self, bad_case_id: str, request: BadCaseLinkSourceRequest) -> BadCaseApiDetailResponse: ...
    async def review_detail(self, bad_case_id: str, request: BadCaseUpdateRequest) -> BadCaseApiDetailResponse: ...
    async def export_review(self, bad_case_id: str) -> Phase10ReviewExportV1: ...
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

Tasks 1–3 are frozen through checkpoint `2a6a05c70e920aeab02d43f976d0ae04169786c8`. Task 4 business services and the Task 5 backend API/export boundary are frozen through checkpoint `86a556d64146e269049675c2db4755f8ae68d594`. Feedback creation derives historical Job/Candidate/rank/explanation/evidence ownership from frozen Phase 8/9 records, preserves absent-result references as opaque human observations, and composes through caller-owned short transactions. BadCase review keeps symptom, root cause, action, and verification semantics separate; supported/confirmed analysis requires a compatible historical evidence link; lifecycle transitions use the Task 3 row-lock/revision primitive; and case-specific immutable verification remains distinct from Phase 11 aggregate effectiveness.

The Phase 10 API is a thin `API → Service → Repository` boundary. Implemented routes are `POST /api/v1/feedback`, `GET /api/v1/feedback/{id}`, `POST /api/v1/bad-cases`, paginated `GET /api/v1/bad-cases`, bounded `GET /api/v1/bad-cases/{id}`, append-only `POST /api/v1/bad-cases/{id}/sources`, and typed `POST /api/v1/bad-cases/{id}/review`. BadCase create/source requests discriminate on `source_type`; review requests discriminate on `command` (`transition`, `analysis`, or `resolution`) and then reuse the frozen service contract. The source command lets multiple compatible immutable FeedbackRecords or deterministic SystemSignals support one existing BadCase; it validates historical ownership and symptom compatibility in one short transaction and does not change root status/revision or infer a root cause, verification, or evaluation label. There is no generic mutable BadCase PATCH. BadCase detail responses include `child_limit` and `truncated_collections`; stale revisions map to a typed conflict; all responses reuse the existing request-ID envelope. `phase10_review_export_v1` is an internal, deterministic, versioned projection with closed symptom/root-cause/action fields and the immutable case-specific verification reference for `VERIFIED` cases; it has no free-form notes, raw profiles, provider data, metrics, evaluation splits, or current mutable state. It is not a Phase 11 evaluation implementation and has no public export endpoint.

Task 3 hardening verification used PostgreSQL 16.14 in the disposable `peoplematch_task3_review_a01425` database. The Task 3 PostgreSQL repository/concurrency module passed `15 passed, 0 failed, 0 skipped`, including caller-owned transaction rollback and explicit bounded-projection tests; the frozen PostgreSQL regression modules passed `31 passed, 0 failed, 0 skipped`; Task 1/2 plus Task 3 contract tests passed `51 passed`; and the separated-process full backend suite passed `740 passed, 0 failed, 47 skipped`. Alembic head/current were both `20260826_0005` and `alembic check` reported no drift. Task 4 subsequently implemented the deferred business compatibility for feedback supersession, case symptom/source selection, supported/confirmed root-cause evidence, action semantics, and lifecycle orchestration using these frozen repository primitives.

The Task 4+5 actual-code hardening gate used PostgreSQL 16.14 in the disposable `peoplematch_task45_review_20260828` database. It closed generic API command shapes, stale append-only review writes, obsolete supported analyses remaining current after a rejected revision, missing verification provenance in the export artifact, and concurrent duplicate source-link behavior. Fresh verification passed Task 4+5 PostgreSQL integration (`10 passed, 0 failed, 0 skipped`), Task 3 repository/concurrency (`15 passed, 0 failed, 0 skipped`), relevant frozen Phase 8/9 PostgreSQL modules (`19 passed, 0 failed, 0 skipped`), Phase 10 unit/contract targets (`76 passed`), and the separated-process full backend suite (`765 passed, 0 failed, 57 skipped`). The source-link PostgreSQL attack tests cover valid append-only linking, missing and cross-run Feedback, incompatible symptoms, duplicate conflicts, rollback, immutable Feedback/source history, unchanged BadCase status/revision, and two-session duplicate attachment with one typed loser. Alembic head/current were `20260826_0005` and `alembic check` reported no drift. The real API/service/repository scenario includes lifecycle review, stale revision conflict, duplicate/reopen audit, bounded detail, privacy-safe export, and compatible multi-source case attribution. Task 4+5 is frozen; canonical Phase 10 remains open for Task 6 product integration and its independent review/freeze gates.

The PostgreSQL suites and the standard full backend regression remain separate pytest processes. Running in-process Alembic PostgreSQL execution before the full suite changes process-global logger state and causes one frozen extraction log-capture assertion to miss otherwise emitted completion records. That frozen test passes independently and with its adjacent module; the standard backend regression and the PostgreSQL suites also pass independently. This is a test-runner composition limitation, not a Phase 10 persistence correctness failure, and the frozen extraction implementation is unchanged.

Task 6's pre-implementation API audit found one narrow product-contract gap: contextual MatchRun and Explanation reads did not expose the immutable persisted locators required by the already-frozen Feedback write commands. The additive bridge exposes `match_result_id` on each MatchRun result and `match_explanation_id` on a dedicated public explanation projection. Persisted `CandidateExplanationOutput`, fingerprints, ORM models, migrations, Feedback requests, repository ownership checks, and service semantics remain unchanged. PostgreSQL 16 verification in disposable database `peoplematch_task6_contract_20260828` passed the locator round-trip and cross-run spoof attacks plus relevant frozen MatchRun/Explanation/Phase 10 modules (`30 passed, 0 failed, 0 skipped`); the separated full backend suite passed `768 passed, 0 failed, 58 skipped`; Alembic remained `20260826_0005 / 20260826_0005 / no drift`. The database is removed after the repair checkpoint and before Task 6 frontend work continues.

Task 6 frontend implementation now integrates persisted Feedback and BadCase review into the frozen Phase 0.5B shell. Matching Results loads completed MatchRun/Explanation context, keeps opaque target locators internal, submits discriminated ranking/explanation/profile feedback, and keeps BadCase creation explicit. The Bad Case queue/detail views provide bounded sources/evidence/history, closed analysis and resolution commands, append-only action supersession, exact lifecycle progression, case-specific verification provenance, safe 409 refresh behavior, and localized 404/422/500/loading/empty states. A generic source-link picker remains intentionally deferred because there is no safe compatible-source discovery endpoint; the UI does not ask reviewers for UUIDs.

The Task 6 Playwright runner uses isolated frontend/backend ports and the exact disposable PostgreSQL database `peoplematch_task6_e2e_20260829`. It upgrades an empty database through `20260826_0005`, seeds frozen-compatible synthetic MatchRun/Explanation/evidence history without rerunning retrieval/ranking or calling a provider, and proves a real browser flow through Feedback → explicit BadCase → REVIEWED → confirmed analysis → ROOT_CAUSE_IDENTIFIED → append-only planned/completed action → ACTION_PLANNED → RESOLVED → immutable VERIFIED. A second real scenario proves stale revision 409 recovery without replay and a safe semantic 422. PostgreSQL 16.14, Alembic head/current `20260826_0005`, no drift, database cleanup, browser console/page/request gates, and desktop/narrow overflow checks are verified by the runner. Task 6 is frozen at its product-integration checkpoint; canonical Phase 10 still requires final integration/freeze review and Phase 11 remains unimplemented.

The late Task 6 self-review closed frontend-only integrity and accessibility gaps before handoff. The persisted-review entry is now explicitly separated from the illustrative Phase 0.5 canvas; Feedback reason/result choices are target-scoped; a rejected or suspected latest analysis cannot leave an older supported revision visually current; truncated analysis/action projections fail closed for dependent review commands; duplicate disposition uses a bounded compatible-case selector rather than handwritten UUIDs; and every modal enters focus, contains Tab/Shift+Tab navigation, closes with Escape, and restores either the invoking control or a stable case heading when a successful lifecycle command removes that trigger. Focus restoration also guards React Strict Mode effect replay so an open dialog cannot return focus to the background trigger. The Bad Case queue offers a local, race-safe retry after a transient read failure. Fresh verification after these repairs passed all frontend unit/integration tests (`35 passed, 0 failed`), typecheck, lint, production build, the real PostgreSQL Playwright scenarios (`2 passed, 0 failed, 0 skipped`), and the frozen backend targeted regression (`76 passed, 0 failed`). The final screenshots use exact `1440x1024` and `390x844` viewports. The E2E runner again confirmed PostgreSQL 16.14, Alembic `20260826_0005 / 20260826_0005 / no drift`, zero unexpected browser console/page/request failures, and removal of `peoplematch_task6_e2e_20260829`. These are implementation-readiness results, not a Phase 10 completion or production-readiness claim.

The independent Task 6 actual-code review then closed additional frontend-only findings: successful API envelopes now undergo endpoint-specific runtime shape and closed-enum validation instead of unchecked TypeScript casts; overlapping detail refreshes cannot let an older response replace a newer revision; bounded analysis/action histories continue to fail closed; independent resolution-action supersession chains remain actionable; persisted Feedback can offer only its compatible BadCase symptom and observations without one remain Feedback-only; keyboard tabs and pending review work expose complete interaction semantics; and reviewer-facing success copy no longer surfaces the internal Feedback identifier. The Final Freeze gate also closed one remaining envelope invariant: a successful response carrying a non-null `error` now fails closed instead of being cast to the successful response type. RED regressions cover malformed and contradictory envelopes, unknown-discriminator, unknown-enum/status, invalid nested Feedback responses, stale refresh ordering, multiple current action chains, BadCase symptom eligibility, keyboard navigation, pending accessibility, and opaque identifiers. Fresh final verification passed frontend unit/integration (`48 passed, 0 failed, 0 skipped`), typecheck, lint, production build, frozen backend targeted regression (`95 passed, 0 failed`), and the real PostgreSQL Playwright suite (`2 passed, 0 failed, 0 skipped`). The runner again confirmed PostgreSQL 16.14, Alembic `20260826_0005 / 20260826_0005 / no drift`, and deletion of `peoplematch_task6_e2e_20260829`. Task 6 is frozen at its product-integration checkpoint.

The Phase 10 final integration review verified the complete Task 1–6 chain without changing production code. Fresh closure gates passed frontend unit/integration (`48 passed, 0 failed, 0 skipped`), frontend typecheck and lint, and the Phase 10 contract/persistence/repository/service/API/export plus MatchRun/Explanation locator target (`95 passed, 0 failed`). The frozen Task 6 build, real PostgreSQL Playwright (`2 passed, 0 failed, 0 skipped`), PostgreSQL 16.14, Alembic `20260826_0005 / 20260826_0005 / no drift`, and disposable-database cleanup remain the immediately preceding end-to-end evidence. Phase 10 is completed and frozen as a local synthetic/sandbox feedback and Bad Case review loop. Phase 11 has not started; metrics, evaluation datasets, strategy comparison, and model-quality claims remain outside this phase.
