# EDR-01 · Choose a real V5 product task (2026-10-13)

This is the preserved V5 architecture decision record. It describes the decision at the time, not a claim that every later release check had already been completed.

| Option | Product gap / value | Cross-module difficulty | Existing overlap / frozen risk | Decision |
|---|---|---|---|---|
| A · Core Requirement Verification Workbench | Recruiter View surfaces selected unknowns, not every canonical must-have/nice-to-have with its source and next check. | Persisted explanation source → canonical diagnostic/proposition contract → read-only API → typed frontend and source drill-down. | Reuse existing builders, proposition service and repository; no ranking or proposition semantic edits. | Select, subject to source integrity tests. |
| B · Trusted Run Inspection & Replay | Useful for audit, less immediate recruiter value. | Backend/API/UI possible. | Existing trusted readback covers much of this; a second integrity engine would add risk. | Reject for V5 center. |
| C · Evidence-Grounded Review Workflow | Could record human resolution over time. | Would need new state, migration, UI and fact-promotion policy. | Existing Feedback/Bad Case owns human review; migration risks frozen trust boundary. | Defer pending specification. |

## Chosen architecture

`match_explanation_id → existing persisted-source integrity check → canonical recruiter brief + requirement diagnostics → read-only requirement projection → typed API → frontend inspection`.

The response is a view of historical data, not a new fact source. For each canonical JD requirement it exposes priority, verbatim text, diagnostic relationship, evidence status and only propositions linked by exact job requirement references. It never converts `missing` into “candidate lacks skill”. Historical evidence uses its canonical source ID, never a mutable current candidate-profile project name. Multi-requirement propositions remain aggregate suggestions, not per-row proof.

## Ownership / frozen boundaries

Allowed: additive response schema, read-only service and API route, typed frontend helper and workbench, a small Recruiter View link, deterministic tests and documentation.

Frozen: Retrieval, Features, Ranking, MatchRun core, Evidence Bundle builder, Grounding, Proposition semantics/builders, model artifacts, Phase 11 data, historical JSONL and earlier published portfolios. No writes, Provider call or MatchRun recomputation.

## Risks and acceptance

1. Source mismatch or cross-candidate proposition contamination must fail closed.
2. Requirement IDs must be unique and covered exactly once; no fuzzy text matching.
3. Diagnostic `missing` is absence of a source-backed relationship in this snapshot, not a negative skill verdict.
4. Frontend must distinguish `available`, `claim_only`, `absent` and `not_assessed` and provide source drill-down.
5. API/browser synthetic integration, negative tests, regression, diff review and frozen-path check are required. Database readback is separately reported; no mock is relabeled as DB integration.

Original local record: `output/peoplematch-directors-cut/signature-v5/engineering/architecture-decision.md` (not included in the public repository). This publication copy preserves the decision and removes only workstation-specific status wording.
