# V5 publication candidate · independent review closure (2026-10-20)

This records a read-only independent code review followed by changes in the isolated `release/v5-requirement-workbench` candidate. It is **not** a recovered historical Codex chat, a remote fresh clone, or a new PostgreSQL/Provider run. The public source and tests in this candidate are the artifacts to inspect.

## Finding 1 · undeclared job source

The original `frontend/src/lib/requirement-review.ts` accepted an HTTP-200 review whose proposition `evidence_refs` contained `job_requirement:req-foreign` while `job_requirement_refs` still named only its own row. The UI could display the foreign reference. The canonical proposition builder ordinarily derives job references from evidence, but the V5 service independently accepted a malformed injected brief.

- **RED:** added backend rejection cases for an extra job ref, unknown namespace and duplicate evidence ref. Before the fix, `python -m pytest backend/tests/test_requirement_review_workbench.py::test_foreign_or_unknown_requirement_proposition_fails_closed -q` exited 1 with `Failed: DID NOT RAISE` at the extra-job-ref assertion. A no-child-process runtime probe of the preserved old source also returned `true` for the malformed client payload.
- **Fix:** the V5 service now requires the job references appearing in evidence to equal the declared job-reference tuple, allows only candidate/job namespaces and rejects duplicates. The client shape validator enforces the same closure before an HTTP-200 response is accepted.
- **GREEN:** the same backend test passed 1/1; subsequent full related backend regression passed 117/117 after the additional descriptor-grammar test. Frontend focused Vitest passed 6/6, full Vitest 104/104. A desktop 1440px and mobile 390px production-page synthetic HTTP fixture sent an invalid review with HTTP 200; the page displayed its safe error state and no requirement matrix.

## Finding 2 · older ExplanationRun URL

The V5 URL contains a saved explanation ID, but the old client loaded only the latest completed ExplanationRun for its MatchRun. Saving a later run therefore made an older valid link fail ownership checking, despite its persisted explanation still being available.

- **RED evidence:** the no-child-process runtime probe against the preserved old source selected `ex-new` for a request to `ex-old` and rejected the older link. A new workbench test asserting selection of the review's `explanation_run_id` was written before the change, but an initial Vitest launch failed at `spawn EPERM`, so **no pre-fix Vitest RED result is claimed**.
- **Fix:** the V5 workbench first loads the requested review, then requests the precise ExplanationRun ID returned by that validated review. The shared trusted-run loader retains its no-ID latest-run behavior for existing Recruiter View callers; the explicit-ID path does not fall back from an empty identity. Existing run, candidate, rank, fingerprint and explanation ownership checks still execute.
- **GREEN:** a new real-function Vitest test loads the older run despite a newer one being listed, asserts the history-list shortcut is not used, and rejects a cross-MatchRun run. Frontend full suite passed 104/104. Desktop/mobile Playwright against the candidate production build and a synthetic HTTP fixture containing old and new completed runs fetched the old run for the saved URL; candidate switch, source drill-down, page errors and horizontal overflow also passed.

## Follow-up finding · incomplete historical source ID

The post-fix independent review found that `candidate:1:project:` with an empty project ID and a matching descriptor was still accepted from an HTTP-200 response. The V5 response Schema had a prefix-only pattern. Normal backend generation gets IDs from the historical Evidence Builder, but an external response validator should reject malformed IDs itself.

- **RED:** new backend Schema regression exited 1 (`Failed: DID NOT RAISE`), and the frontend Vitest case failed `expected true to be false` for that exact source. A runtime probe of the preserved old source confirmed acceptance.
- **Fix:** response Schema now uses full-match validation against the Evidence Builder's bounded historical ID grammar. Frontend candidate evidence and descriptors use the same rank, 64-character skill digest or bounded project/project-record ID grammar. No Evidence Builder, Ranking or Grounding code changed.
- **GREEN:** backend V5 10/10 and related backend 117/117; frontend focused 3/3 and full 104/104. Existing canonical projection fixtures still pass.

A final independent pass then compared this new guard with the existing Phase 9 `EvidenceId` contract. It found that the first guard rejected a legitimate 32-character skill digest and accepted a project suffix containing `:`. New backend and frontend tests both failed before the correction. The backend descriptor now reuses the canonical Phase 9 patterns; the client mirrors their 32–64 lowercase-hex skill digest and colon-free project ID grammar. The same focused tests then passed, followed by 117/117 backend, 104/104 frontend, TypeScript, ESLint and the default Turbopack production build. This alignment changes only the V5 read/projection contract, not the historical Evidence Builder.

## Verification scope

| Check | Current candidate result | Boundary |
|---|---|---|
| Backend focused tests | 117 passed, 0 failed/skipped; JUnit in local release audit | No current PostgreSQL service used |
| Frontend Vitest | 104 passed, 0 failed/skipped; JUnit in local release audit | Includes the new historical-run regression |
| TypeScript / ESLint | Exit 0 each | Isolated worktree with `npm ci` dependencies |
| Default production build | Next.js 16.3.0 Turbopack exit 0; `/requirement-review` generated | The earlier junction snapshot failure is a different environment |
| Synthetic production-page browser | 1440px and 390px history and malformed-source paths passed | HTTP fixture, not independent PostgreSQL |
| Independent PostgreSQL | **NOT RERUN in this candidate** | Separate 2026-10-18 tmpfs audit tested 31 persistence cases + one seed, on source files before these two later fixes; Docker Engine unavailable in the current candidate environment |
| Remote fresh clone / live deep links | **NOT VERIFIED** | No Push; remote proxy failed on a later retry |
| Qwen / Ranking / historical Fresh Top-3 | **NOT RERUN** | Frozen evidence only |

No frozen Ranking, Grounding, MatchRun or historical database content was modified by these corrections. A local release-candidate commit does not itself publish any V5 file; remote publication requires explicit user approval.
