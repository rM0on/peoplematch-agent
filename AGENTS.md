# AGENTS.md

This file defines repository-wide instructions for coding agents working on PeopleMatch Agent.

## Repository Rules

Before changing code:

1. Read `README.md`.
2. Read `docs/PRD.md` and `docs/architecture.md`.
3. Read `docs/development-roadmap.md` and identify the explicitly active phase.
4. Read the relevant API or phase document for the task.
5. Inspect `git status`, existing files, and recent commits. Preserve user work.

When an instruction conflicts with an observed implementation, stop and resolve the inconsistency before broad edits.

## Scope Discipline

- Implement only the active phase and the behavior explicitly requested by the user.
- Do not pre-build planned phases, speculative abstractions, fake endpoints, sample results, or placeholder production logic.
- Mark future capabilities as `Planned`; do not describe them in present tense as implemented.
- Keep Phase 0 limited to product definition, engineering bootstrap, liveness, and local infrastructure configuration.

## Engineering Rules

- Preserve existing architecture and public contracts unless the task explicitly changes them.
- Avoid unnecessary rewrites and unrelated dependency upgrades.
- Prefer typed interfaces and small, focused modules.
- Keep dependency direction clear: API → service → repository. Do not add a layer when no behavior needs it.
- Use explicit error handling; never swallow exceptions or return fake fallback success.
- Do not add dead code, unused dependencies, giant files, or speculative frameworks.
- Keep configuration in environment-backed settings. Never commit secrets or hard-code credentials/API keys.
- Use npm for the frontend while `package-lock.json` is present.
- Document executable Windows PowerShell commands, not only POSIX shell commands.

## Testing

- Add a test before implementing new behavior and observe the expected failure.
- New behavior must include deterministic tests appropriate to its layer.
- Run all relevant tests, lint, typecheck, and builds after changes.
- For a bug fix, first add a regression test that reproduces the bug.
- Do not claim a command passes unless it was run in the current task and exited successfully.
- Report skipped or unavailable verification as `NOT VERIFIED` with the exact reason.

## AI / Ranking Rules

- The LLM does not directly own final ranking.
- LLM responsibilities may include semantic extraction, structured profile generation, and evidence-grounded explanation.
- Ranking evidence and explanation are separate artifacts. Explanation must not mutate ranking.
- Final ranking must come from a deterministic and/or learned ranking pipeline with traceable features and stages.
- Claimed skills and supporting project evidence must remain distinct.

## Evaluation Integrity

- Never invent metrics, labels, benchmark results, user outcomes, latency, QPS, or business impact.
- Do not cherry-pick offline results without documenting the dataset, split, comparison, and limitations.
- Never claim online improvement from offline evaluation.
- Keep evaluation data synthetic, public, manually labeled, and locally reproducible.

## Privacy

- Do not add real candidate personal data, private resumes, employer data, or credentials.
- Use synthetic/sandbox records, public job-description examples, and manually created labels only.
- Remove or redact personal data discovered accidentally and notify the user before committing it.

## Git Safety

- Never use destructive reset, force push, or rewrite existing user commits.
- Do not delete unrelated work or discard a dirty working tree.
- Do not configure a remote or push unless the user explicitly asks.
- Do not commit generated secrets, `.env`, caches, build outputs, databases, or model artifacts.
- Prefer small, reviewable commits when the user requests commits.

## Final Verification

Before ending any task:

1. Inspect the full `git diff` and run `git diff --check`.
2. Run relevant backend tests.
3. Run relevant frontend test, lint, typecheck, and build commands.
4. Run Compose checks when infrastructure changed and Docker is available.
5. Check the final branch and `git status`.
6. Report commands and their real results, known limitations, and phase scope.
