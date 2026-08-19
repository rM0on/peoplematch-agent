# Match-run Orchestration and Traceability

## Status

Phase 8 is **Completed / Frozen**. It adds deterministic, server-controlled orchestration and durable historical execution records around the default frozen Phase 6 LambdaMART service and the explicit optional Phase 7 Cross-Encoder experiment. It does not add explanations, LLM behavior, feedback, replay, or ranking changes.

## Domain

The canonical backend concept is `MatchRun`. Product UI may label the view Agent Run or Workflow, but there is no autonomous agent, planner, tool-selection loop, or duplicate `AgentRun` table.

`MatchRun` uses a durable UUID `run_id` distinct from the HTTP `request_id`. Every POST creates a new run. The only lifecycle states are `RUNNING`, `COMPLETED`, and `FAILED`; completed and failed runs are terminal and immutable through the application/repository contract. There is no normal terminal-run mutation path, and a rerun creates a new `run_id`; this is not database-level tamper-proof storage.

## Variants and Actual Steps

The default variant is `ltr`:

1. `resolve_inputs`
2. `phase6_ltr_rank`
3. `persist_results`

The explicit `cross_encoder_experiment` variant is:

1. `resolve_inputs`
2. `phase6_ltr_rank`
3. `phase7_cross_encoder_rerank`
4. `persist_results`

These are observable execution boundaries. There are no fictional parse, reason, explain, or replay steps. Phase 8 wraps the existing services and does not copy retrieval, feature, LambdaMART, or Cross-Encoder logic. The CE runtime is lazy and is never resolved for the default LTR variant.

The tracked workflow contract is `data/contracts/match_run_workflow_v1.json`. Its stable fingerprint is recorded on every run.

## Persistence

Alembic revision `20260818_0002` adds:

- `match_runs`: durable identity, lifecycle, request parameters, frozen stage provenance, historical Job snapshot, fingerprints, result count, and safe failure fields.
- `match_results`: one returned Candidate per row, historical rank, Phase 4 ranks/raw scores, the exact ten Phase 5 features, selected diagnostics, Phase 6 raw margin, optional Phase 7 raw logit, and a privacy-bounded Candidate snapshot.
- `run_steps`: ordered durable step status, UTC timestamps, monotonic duration, compact references, and safe failure data.

Per-run Candidate and rank uniqueness is enforced. Job/Candidate references use `ON DELETE RESTRICT`; unreferenced user profiles retain normal deletion behavior, while referenced profiles return `profile_history_conflict` rather than losing history.

## Transactions and Failure Semantics

The request-scoped database session is not used as one giant run transaction. A dedicated aggregate repository opens independent transactions for lifecycle writes:

- create and commit `RUNNING` before resolving the Job;
- durably start and finish each actual step;
- write the complete result set, complete `persist_results`, and mark the run `COMPLETED` in one atomic transaction;
- if that transaction fails, roll it back and use a new transaction to mark the real step and run `FAILED`.

A missing Job, ranking failure, explicit CE failure, or persistence failure never becomes an empty successful result. A process crash may leave a `RUNNING` row; recovery workers are outside Phase 8.

## Historical Inputs and Privacy

MatchRun execution uses one PostgreSQL `REPEATABLE READ` session for input
resolution, the frozen Phase 4/5/6 graph, optional Phase 7 canonical reads, and
returned Candidate snapshots. Lifecycle writes use independent sessions so a
ranking failure cannot erase the durable trace. PostgreSQL repeatable read does
not transactionally freeze Qdrant; stored retrieval freshness and index
provenance make that derived-state boundary explicit.

The snapshot contract is `ranking_input_snapshot_v1`, with a separate `candidate_input_snapshot_v1` for each returned Candidate and `selected_feature_diagnostics_v1` for selected diagnostics. The allowlist is tracked in `data/contracts/ranking_input_snapshot_v1.json`.

Snapshots retain structured roles, requirements, skills, technologies, evidence IDs/status/supports-skills, location, seniority, team-stage preference, and bounded overclaim state. They exclude raw resume/JD text, names, company names, URLs, artifact references, project prose, evidence statements, labels, splits, pairwise preferences, hard-negative metadata, and explanation output.

Canonical SHA-256 fingerprints normalize dictionaries, enums, and finite float64 values. Result fingerprints exclude run IDs and timestamps and are stable after PostgreSQL roundtrip.

## Provenance and Score Semantics

Expected frozen provenance is used only for validation. A successful run stores
the observed values returned by the runtime, and mismatches fail closed. Each
run records the Phase 4 document/configuration contract plus actual retrieval freshness/provider/index diagnostics, Phase 5 version/fingerprint, Phase 6 ranker version/model SHA-256, request parameters, and workflow version/fingerprint. CE provenance is non-null only when the explicit experimental variant actually completes and records its model ID, immutable revision, snapshot/text fingerprints, pair order, raw-logit semantics, and `calibration=false`.

Dense/BM25/fusion values are retrieval-stage values. `ltr_score_raw` is a raw LightGBM margin. `cross_encoder_score_raw` is a raw relevance logit. None is a probability, percentage, confidence, or final match score.

## API

- `POST /api/v1/match-runs`: synchronously creates and executes a new run. LTR defaults are `candidate_pool_k=20`, `top_k=10`. CE defaults are retrieval pool 20, CE pool 10, top 5.
- `GET /api/v1/match-runs/{run_id}`: reads persisted historical metadata, results, and steps. It never calls ranking or retrieval services.
- `GET /api/v1/match-runs`: lists newest runs with limit/offset and optional Job, status, and variant filters.

There is no update, delete, retry, replay, explanation, or result-detail endpoint in Phase 8.

The LIST endpoint reads summary columns only; historical result and step children
are loaded by GET detail, not by the summary query.

## Phase 9 Boundary

Phase 9 can start from `run_id` and read the exact historical top result, rank, structured Job/Candidate inputs, retrieval values, ten features, selected diagnostics, Phase 6 margin, optional Phase 7 logit, and frozen execution provenance without reranking. Phase 8 contains no explanation table, provider, prompt, validator, prose output, or rank mutation.
