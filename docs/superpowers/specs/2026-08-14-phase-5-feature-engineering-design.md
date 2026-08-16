# Phase 5 Feature Engineering Design

> Status: Completed / Frozen after independent source review.

## Scope and boundary

Phase 5 adds an on-demand, versioned, label-free Candidate/Job pair feature layer after frozen Phase 4 retrieval. It emits a stable model-feature vector and separate diagnostics, preserves retrieval order, and does not score, rerank, train, or evaluate a ranking model. Phase 4 retrieval documents, algorithms, configuration, evaluation artifacts, and fixed test queries remain untouched.

## Architecture

```text
CandidateProfile + JobProfile + optional RetrievalResult
                         |
                         v
                  FeatureExtractor
                         |
             +-----------+-----------+
             |                       |
        FeatureVector          FeatureDiagnostics
   (registered model input)   (inspection only)
```

`FeatureEngineeringService` calls the existing `RetrievalService`, batch-loads the returned profiles, extracts one pair at a time, and emits results in the exact retrieval order. Runtime feature code depends on profile/retrieval contracts only; evaluation labels, splits, pairwise preferences, hard negatives, and benchmark reports are excluded from its dependency graph.

## Versioned contract

The initial contract is `feature_schema_v1`. `MODEL_FEATURE_ORDER` is:

1. `semantic_score`
2. `sparse_score`
3. `skill_fit_score`
4. `project_evidence_score`
5. `role_direction_score`
6. `ai_tool_score`
7. `location_score`
8. `seniority_score`
9. `missing_penalty`
10. `overclaim_penalty`

The fingerprint is SHA-256 over stable JSON containing the version, ordered feature definitions, formula identifiers, directions, bounds, missing policies, sources, source policy, and normalizer version. It excludes timestamps, paths, UUIDs, process state, and data values. Nullable values and explicit availability flags distinguish missing data from a real zero.

## Normalization and matching

Normalizer `text_nfkc_casefold_technical_tokens_v2` applies Unicode NFKC and casefold, preserves alphanumeric-attached `+`/`#` technical suffixes, removes internal dots only between alphabetic identifier characters, retains leading and numeric dots, converts other punctuation/symbols to separators, and collapses whitespace. This keeps symbol-bearing languages distinct, gives dotted/undotted identifiers one lexical identity, preserves `.NET` and numeric-version identity, and prevents `.NET` from matching `ASP.NET`. It is deterministic, local, and has no learned, product-specific, or benchmark-specific aliases.

Capability atoms come only from Candidate skill names, project technologies, and project demonstrated skills. Evidence atoms come only from `project_evidence.supports_skills` where `verification_status=available`. `described` and `missing` evidence records remain canonical information but create no positive Phase 5 evidence credit. A phrase is an explicit match only when its normalized token sequence occurs on requirement token boundaries. No category-only weak credit or synthetic ontology is invented. Project names/summaries, evidence statements, and artifact references are never matching inputs.

Requirement applicability is explicit per feature. Skill fit and its missing penalty consider only Job `skill` requirements. Project-evidence coverage considers Job `skill` and `project_evidence` requirements. Job `experience` requirements are out of scope for all three because the Candidate contract has no dedicated structured experience signal; vocabulary overlap cannot stand in for experience. Role, location, seniority, work style, and AI tooling are handled separately. Must-have weight is 2 and nice-to-have weight is 1. Explicit match is 1 and no match is 0; there is no 0.5 weak match or partial `described` evidence heuristic.

## Feature definitions

- `semantic_score`: unchanged Phase 4 dense score; unavailable when the dense channel did not run.
- `sparse_score`: unchanged Phase 4 BM25 score; unavailable when the sparse channel did not run.
- `skill_fit_score`: weighted Candidate capability coverage over Job `skill` must/nice requirements; unavailable if no Job `skill` requirement exists.
- `project_evidence_score`: weighted available-evidence coverage over Job `skill` and `project_evidence` requirements; unavailable if neither category exists.
- `role_direction_score`: maximum token-set Jaccard between Candidate target roles and Job role title/directions, with exact normalized equality equal to 1; unavailable if either side has no usable value.
- `ai_tool_score`: 1 when a declared Candidate AI-tool phrase appears explicitly in Job AI-tooling requirement text, otherwise 0; unavailable when the Job has no explicit AI-tooling requirement.
- `location_score`: exact normalized Candidate preferred-city/Job city overlap, 1 or 0; unavailable if either side is missing.
- `seniority_score`: exact canonical seniority membership, 1 or 0; unavailable if either side is missing.
- `missing_penalty`: mean `1 - match` for must-have Job `skill` requirements; unavailable if none exist; higher is worse.
- `overclaim_penalty`: existing ordered `OverclaimRisk.level` mapped by its explicit low/medium/high ordering to 0/0.5/1. Reasons are never model inputs.

## Input policy

Allowed Candidate inputs are structured skills, project technologies, project demonstrated skills, evidence supported skills/types/verification status, target roles, AI tools, preferred cities, seniority, and overclaim level. Allowed Job inputs are role title/direction, requirements and their categories/evidence expectations, evaluation focus, cities, and seniority requirements. Allowed retrieval inputs are only the existing dense/sparse scores and non-model ranks/fusion diagnostics. This source policy is an allowlist, not a claim that every field is consumed by every formula.

Forbidden signals include entity/name/company IDs as values, raw resume/JD text, URLs, project names/summaries, evidence statements, provenance, data origin, archetype, schema/dataset version, split, annotation source, synthetic naming/family phrases, labels, relevance grades, hard-negative or pairwise annotations, and benchmark membership/results.

## Diagnostics

Diagnostics may expose safe IDs and derived matches: matched/weak/missing skill-requirement IDs, available-evidence-supported requirement IDs, matched capability/available-evidence/tool names, location/seniority relation, overclaim level and reason count, feature availability, and original retrieval ranks/fusion score. Diagnostics are not part of `MODEL_FEATURE_ORDER` and do not include free-text evidence or raw source.

## API

- `POST /api/v1/features/jobs/{job_id}/candidates`
- `POST /api/v1/features/candidates/{candidate_id}/jobs`

Both reuse the strict Phase 4 retrieval request, return the standard success/data/error/request-id envelope, preserve all inherited filter semantics, and do not sort after feature extraction. Pair-derived profile features are identical across directions; retrieval-context values and diagnostics may differ.

## Derived artifacts and audit

`data/eval/phase5/feature_contract_v1.json` must equal deterministic code generation. A label-free audit over 48 Candidates x 19 train/dev Jobs (912 pairs) records only contract identity, bounds, missingness, distinct counts, and invariant outcomes. It does not read grades, calculate ranking metrics, run test queries, or tune formulas. Constant features are disclosed rather than changed.

## Known limitations and Phase 6 handoff

Lexical matching is not a semantic skill ontology. `described` evidence receives no partial score, and Job `experience` requirements remain unmodeled without a dedicated structured Candidate experience signal. Explicit AI-tool overlap is not overall AI competence. Location is exact-only and performs no geographic inference. Seniority is exact-only and performs no ordinal partial credit. The synthetic sandbox cannot establish hiring effectiveness. There are no learned weights, LTR, Cross-Encoder, LLM judging, final score, or reranking.

Phase 6 may consume only values in `MODEL_FEATURE_ORDER` under an exact feature version/fingerprint check. It must not consume diagnostics and must define its own missing-value/model-training policy.
