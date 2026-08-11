# Service Boundaries

This directory reserves the application-service boundary for later phases. Phase 0 contains no matching business logic.

Planned ownership is intentionally separated by capability:

- `profile_parser`: structured candidate and job extraction.
- `retrieval`: hybrid candidate/job retrieval.
- `scoring`: evidence-aware feature computation.
- `ranking`: learned and deterministic ranking stages.
- `explanation`: evidence-grounded recommendation explanations.
- `feedback`: explicit feedback processing.
- `evaluation`: sandbox-only offline evaluation runs.

These names describe boundaries, not implemented features. Add a package only when a phase introduces executable behavior and tests for it.
