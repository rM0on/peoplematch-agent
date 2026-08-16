# Phase 5 Feature Engineering Implementation Plan

> Status: Completed / Frozen after independent source review and closeout verification.

> Execute in this session with RED -> GREEN cycles. Do not commit, push, run the Phase 4 test evaluation, change Phase 4 retrieval behavior, or begin Phase 6.

**Goal:** Add a deterministic, auditable, versioned, label-free pair feature layer that enriches Phase 4 results without changing their order.

## Task 1: Feature contract and pure extraction

**Create:** `backend/app/schemas/features.py`, `backend/app/services/features/{contract,normalization,matching,extractor}.py`, `backend/tests/test_feature_contract.py`, `backend/tests/test_feature_extractor.py`, `data/eval/phase5/feature_contract_v1.json`.

1. Write failing contract tests for exact order/version/fingerprint, stable generation, and checked-in artifact equality.
2. Implement the registry and deterministic stable serialization.
3. Write failing normalization/extractor tests for bounds, missingness, monotonic skill/evidence coverage, penalty direction, forbidden-field invariance, label independence, construction-artifact invariance, raw retrieval scores, and determinism.
4. Implement minimal pure normalizer, matcher, extractor, and typed schemas; keep diagnostics outside model features.
5. Run feature unit tests to green.

## Task 2: Enrichment service and API

**Create:** `backend/app/services/features/service.py`, `backend/app/api/routes/features.py`, `backend/tests/test_feature_service.py`, `backend/tests/test_feature_api.py`. **Modify:** API dependencies/router.

1. Write failing service tests for both directions, batch profile reuse, exact retrieval-order preservation, pair consistency, filters, missing profiles, and unavailable retrieval errors.
2. Implement `FeatureEngineeringService` as a wrapper over the stable retrieval interface; do not copy or alter retrieval logic.
3. Write failing API tests for both routes, standard envelopes/request IDs, strict requests, errors, and inherited filters.
4. Wire dependencies/routes and run service/API tests to green.
5. Add an import-architecture regression preventing runtime feature modules from importing evaluation/label/pairwise/split/hard-negative artifacts.

## Task 3: Audit and documentation

**Create:** `backend/app/services/features/audit.py`, `scripts/generate_feature_contract.py`, `scripts/audit_features.py`, `backend/tests/test_feature_audit.py`, `data/eval/phase5/feature_audit_v1.json`, `docs/feature-engineering.md`. **Modify:** README, roadmap, architecture, API docs.

1. Write failing audit tests for train/dev-only scope, 912 pairs, determinism, no labels/ranking metrics, bounds, missing rates, distinct counts, and artifact equality.
2. Implement a deterministic profile-only audit and generate both checked-in derived artifacts.
3. Document definitions, formulas, allowlist/denylist, missingness, bidirectionality, fingerprint, limitations, and Phase 6 contract.
4. Mark Phase 5 Completed / Frozen and Phase 6 Planned only after the review gate passes.

## Task 4: Verification and review handoff

1. Run feature-specific tests and Phase 4 retrieval regressions.
2. Run full backend, PostgreSQL, and Qdrant tests; report environment-skipped gates exactly.
3. Run dataset freeze/validation and Alembic current/check.
4. Run frontend lint/typecheck/test/build without source changes.
5. Run Compose health and minimal bidirectional runtime feature smoke if infrastructure is available.
6. Review full diff for frozen data/artifacts, migration, generated/cache/secrets, Phase 6 scope, privacy, type/contract consistency, and `git diff --check`.
7. Request independent code review, address only verified Phase 5 findings, and rerun affected tests.
8. After independent review and all closeout gates pass, create the designated local closeout commit; do not push or begin Phase 6.
