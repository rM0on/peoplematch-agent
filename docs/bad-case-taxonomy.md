# Bad Case Taxonomy

This taxonomy separates **data-level mismatches that Phase 1 can annotate** from **pipeline failures that require future retrieval/ranking/explanation runs**. A data mismatch is not evidence that a pipeline failed.

## Data-level mismatch — CURRENT in Phase 1

| Code | Meaning | Required evidence |
|---|---|---|
| `DIRECTION_MISMATCH` | Overlapping skills support a different daily work direction | Candidate target/project direction compared with job role direction |
| `EVIDENCE_INSUFFICIENT` | A relevant claim lacks an available or adequate artifact | Claim, evidence status, and job expectation |
| `KEYWORD_FALSE_POSITIVE` | Vocabulary creates apparent relevance without corresponding depth | Raw text/claim compared with project role and artifacts |
| `MUST_HAVE_MISSING` | A critical job requirement has no support | Specific affected requirement ID |
| `LOCATION_MISMATCH` | City, remote policy, or relocation constraints conflict | Structured candidate and job location fields |
| `SENIORITY_MISMATCH` | Demonstrated scope does not meet the requested level | Candidate seniority and job seniority requirement |
| `WORK_STYLE_MISMATCH` | Preferred operating stage conflicts with the job context | Candidate work-style preference and job product stage |
| `OVERCLAIM_RISK` | Claimed breadth/level exceeds artifact depth | Structured overclaim reasons and evidence status |
| `AI_TOOLING_GAP` | A typed AI-tooling requirement is missing | Affected AI-tooling requirement |
| `PROJECT_DEPTH_GAP` | Relevant work exists but is too shallow for a stronger judgment | Project scope, outcomes, and evidence |

These codes describe a candidate-job pair inside a synthetic sandbox. They are not judgments about personal worth, trustworthiness, or employability.

## Pipeline-level failure — PLANNED / FUTURE

| Future category | Meaning | Earliest dependent phase |
|---|---|---|
| Retrieval miss | A relevant labeled candidate is absent from the retrieved set | Phase 4 |
| Retrieval false positive | Retrieval over-selects semantically similar but weak pairs | Phase 4 |
| Feature attribution error | A deterministic feature contradicts its documented input | Phase 5 |
| Ranking inversion | A weaker labeled candidate is ordered above a stronger one | Phase 6 |
| Rerank regression | Cross-encoder ordering degrades a previously correct pair | Phase 7 |
| Trace loss | A run cannot identify the stage/configuration behind an output | Phase 8 |
| Explanation overclaim | Explanation states support absent from ranking evidence | Phase 9 |
| Feedback attribution error | Review feedback is linked to the wrong immutable run/pair | Phase 10 |
| Evaluation data leakage | Query or label information crosses the declared split | Phase 11 |

No Phase 1 record claims that any of these pipeline failures has occurred. They become assignable only after the relevant pipeline stage exists and a traceable run provides evidence.

## Review rule

When a future bad case is opened, first distinguish the ground-truth pair property from the system behavior. For example, `DIRECTION_MISMATCH` may explain why a retrieved pair is weak; the pipeline failure would be a ranking inversion only if that weak pair is ordered above a stronger labeled candidate.
