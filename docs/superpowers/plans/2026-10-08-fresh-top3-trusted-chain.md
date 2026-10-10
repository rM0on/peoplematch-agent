# Fresh Top-3 Trusted Chain Validation Plan

> **For agentic workers:** If this plan is approved for execution, use the repository's applicable implementation workflow and review each checkpoint before proceeding. This document authorizes **no execution now**.

**Goal:** Validate one fresh, synthetic JD-to-Top-3 run of the trusted matching, evidence and RecruiterProposition chain without making free-text Narrative an autonomous safety gate.

**Architecture:** Reuse the existing configured extraction and frozen retrieval/ranking/MatchRun/Phase 9 evidence services. Build canonical recruiter propositions only from the selected, validated per-candidate evidence projection. Keep optional Qwen prose as a separately labeled, human-review draft; do not use it to author facts, alter rank, or determine whether the trusted chain passed.

**Tech stack:** Existing FastAPI/Pydantic/PostgreSQL/Qdrant/OpenAI-compatible application path, frozen LightGBM LambdaMART strategy, local synthetic fixture, pytest and existing integrity checks. Do not create a parallel Provider client or new Narrative generation experiment.

## Global constraints and present status

- This is **Proposed / awaiting explicit approval**. No Fresh Top-3 is run by this handoff.
- Phase 2 Recruiter Narrative is **CLOSED / NOT PASS** for automatic free-text publication. No new Prompt, Intent, regex, validator, auditor, renderer, Provider comparison batch, or Narrative version.
- Preserve all existing dirty-worktree code, gold, manifests, JSONL and failed experiments. No reset, clean, restore, commit or push unless separately authorized.
- Synthetic/public inputs only. No private resumes, candidate PII or secrets in artifacts.
- Real and mock Provider evidence must be named separately. A mock run cannot pass a gate that explicitly requires real extraction.
- Use the frozen retrieval/feature/LambdaMART/optional Cross-Encoder strategy exactly as configured; do not tune ranking or evaluate a new algorithm.
- Current `RecruiterPropositionV1` code is not yet the primary product runtime. Any integration needed for this validation is a separate, explicitly reviewed implementation task, not assumed complete.

## File and artifact map to inspect before execution

- Existing inputs and contracts: `backend/app/services/explanation/presentation/contracts_proposition_v1.py`, `propositions_v1.py`, `adapter.py`; frozen MatchRun, Evidence Engine and ExplanationPlanV1 modules under `backend/app/services/` and `backend/app/schemas/`.
- Existing experiments to preserve, **not rerun**: `backend/tests/fixtures/recruiter_proposition_phase2_semantic_intent_recovered_20261007T0858Z.jsonl` and `backend/tests/fixtures/triage_phase2_final_20261008T0859Z.*`.
- New phase artifacts, only after approval: a unique Fresh Top-3 run manifest, immutable JSON/JSONL trace, structured-proposition export, provenance/candidate-isolation audit, ranking before/after comparison, and a written manual product review in a separately named validation directory under `backend/tests/fixtures/` or `docs/` according to existing artifact conventions. Never overwrite Phase 2 files.
- Expected future product evidence, **not this plan's deliverable**: JD-input and Top-3 screens, a structured recruiter briefing with drill-down to source evidence, and MatchRun trace; any optional draft view must show “Requires Human Review”. Screenshots require separate UI/screenshot approval after the trusted backend chain passes, and must not imply unimplemented behavior.

## Task 1 — Freeze scope and source input

1. Record branch/HEAD/dirty status and hashes of frozen ranking strategy, key contracts, fixture and test code; keep Phase 2 artifacts unchanged.
2. Prepare one genuinely fresh synthetic JD not reused from Phase 2 development/holdout experiments or historical MatchRuns. Identify the candidate pool and its versions; redact or exclude any real personal information.
3. Declare before execution the configured extraction Provider/model, whether it is `real` or `mock`, the frozen retrieval and ranking strategy including whether Cross-Encoder is enabled, Top-3 count, timeout/retry policy, and stop conditions. Record Provider status/health separately from configuration. Do not switch to mock after a real-provider failure.
4. Define a new run/experiment identifier and immutable manifest. Fail closed if the JD, candidate pool, strategy, request or implementation hash changes after freeze.

**Checkpoint:** A reviewer can identify the exact synthetic input, strategy and artifact IDs before any extraction or MatchRun runs.

## Task 2 — Execute the existing trusted matching chain once

1. Use the configured application's extraction service for the fresh JD; verify the extraction schema, requirement/evidence references, and actual Provider mode. If real extraction is required but quota/network prevents it, mark the real gate **BLOCKED**, not Mock PASS.
2. Use the existing Hybrid Retrieval over the fixed candidate pool. Record retrieval IDs, stage/config fingerprints and candidate-pool provenance, without altering retrieval implementation.
3. Run frozen feature engineering and LambdaMART. Apply Cross-Encoder only if the predeclared existing strategy says so, reporting its role separately; do not allow the LLM Narrative to rerank.
4. Create a **new** MatchRun through the existing orchestration path. Confirm terminal state, exactly three ordered results, raw LTR margins, ranking fingerprint and source snapshots; do not reuse a historical run, cached Narrative or approved copy.

**Checkpoint:** A durable new MatchRun yields a reproducible Top-3. Extraction/retrieval/ranking/persistence failure stops the trusted-chain validation and is reported by stage.

## Task 3 — Evidence and canonical RecruiterProposition for each Top-3 result

1. For each of the three persisted results, obtain the selected Phase 9 Evidence bundle and validated source explanation/projection through existing ownership/reference checks. The canonical entry point is `build_recruiter_propositions_from_evidence_v1` where its required `CandidateExplanationOutput` exists. Do not bypass that contract by inventing a direct MatchRun-to-Proposition shortcut.
2. If the current service cannot supply this validated source for a fresh MatchRun, record the exact missing integration and stop for approval before changing contracts or runtime. An absent source cannot be filled with a mock or generated fact.
3. Rebuild/validate each `RecruiterPropositionSetV1` against its original projection. Check `candidate_id`, `result_rank`, fact IDs, claim IDs, evidence refs, job-requirement refs, recommendation strength and unknown/review predicates. Verify no cross-candidate reference and no unsupported upgrade from material technology to personal experience/action.
4. Produce a recruiter-facing **structured** brief for each candidate: why review/conditional screen, a limited key technical signal, the most material unknown, and a source-backed first verification target. Presentation may use existing structured fields and source labels; it must not rely on Qwen prose for truth or become a schema/debug dump. If no safe item exists, represent the gap explicitly instead of inventing one.
5. Keep existing Evidence Grounding and Proposition validation separate. A structured Proposition failure is a trusted-chain failure; a free-text draft failure is not.

**Checkpoint:** 3/3 candidates have independently verifiable source-backed structured review signals, unknowns and next checks, or the phase reports the exact failed contract.

## Task 4 — Optional experimental draft boundary

1. Default to **no new Narrative generation** in the trusted-chain run. If separately authorized later, request at most one opt-in draft per candidate through the existing Provider/Schema/Handle protocol; no retry for semantic failure.
2. Label every draft “Requires Human Review / 需人工复核” in artifacts and any later UI. Keep an explicit `experimental_draft` status separate from `trusted_structured_evidence`; do not auto-approve or auto-publish on Schema/Handle/Blind Auditor/legacy Guard PASS.
3. Demonstrate that draft presence, failure or differing wording leaves MatchRun and the structured Proposition results unchanged. Manual review can reject the draft while the trusted Top-3 remains valid.

**Checkpoint:** Draft failures never mutate or block ranking/evidence/propositions. No unlabelled draft is presented as verified fact.

## Task 5 — Verify, report and hand off

1. Compare candidate order, raw LTR score vector and ranking fingerprint from the persisted MatchRun before and after evidence/proposition/presentation work. Equality must be exact for all three; distinguish a rerun from merely re-reading a frozen snapshot.
2. Inspect full traceability from each structured review item through proposition → source fact/claim → selected candidate/job Evidence → MatchRun and original synthetic input. Verify candidate isolation for 3/3; preserve all failures.
3. Run focused Proposition/provenance/candidate-isolation and integration tests, full backend mock regression with process-scoped mock Provider variables, `git diff --check`, compile/import checks and secret/privacy scan. Do not claim frontend/build/Compose verification unless actually run when a later implementation changes those layers.
4. Produce one validation report with Provider mode and status, three candidate records, stage latencies, explicit success/failure table, source links, ranking invariance, optional draft status, frozen-path diff, limitations and artifact hashes. Compare neither a mock result nor this one fresh case to Phase 11 offline metrics as an online gain.
5. Only after trusted backend success and separate approval should product/UI work or screenshots be considered. Preserve the Phase 2 decision record and all experimental assets.

**Checkpoint:** Reviewable, immutable artifact and an honest go/no-go for the trusted Fresh Top-3 chain.

## Acceptance and failure criteria

**PASS — trusted main chain:** new synthetic JD and MatchRun; configured extraction mode accurately recorded and valid; Hybrid Retrieval/feature/LambdaMART (plus only predeclared optional Cross-Encoder) complete; 3/3 persisted candidates have correct identities and grounded Evidence; 3/3 canonical Proposition sets pass source/rebuild/ownership checks; structured why-review, technical signal, unknown and first-check fields are source-backed and appropriately calibrated; exact order/raw scores/fingerprint unchanged by explanation/presentation; full relevant regression and privacy checks pass. If the approved validation explicitly requires **real** extraction, only a real Provider call can satisfy that sub-gate.

**FAIL / BLOCKED:** missing or invalid extraction; retrieval/ranking/MatchRun failure; missing Explanation/Evidence source required by the canonical Proposition builder; any unsupported structured claim, foreign-candidate reference or unsourced JD requirement; any ranking mutation; misleading real/mocked provenance; incomplete trace or artifact corruption. Report stage-specific failure and do not fabricate a Top-3 success.

**Non-gating experimental result:** absence, semantic failure or manual rejection of an optional Qwen Narrative Draft. It remains a human-review draft, never a fact source, automatic hiring decision or ranking input. This does not waive the trusted-chain checks above.

**Decision rule:** Phase 2 Recruiter Narrative remains closed regardless of this result. A PASS advances only the trusted Fresh Top-3 project path; a FAIL triggers diagnosis of that path, **not** another Recruiter Narrative VNext/Prompt/Intent loop.
