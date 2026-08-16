# Phase 5 Feature Engineering

## Scope

Phase 5 is a completed and frozen feature-extraction baseline after completed Phase 4 retrieval. It converts a canonical Candidate/Job pair plus optional Phase 4 channel signals into a stable `FeatureVector` and separate `FeatureDiagnostics`. The implementation passed independent source review. It does not learn weights, compute a final match score, rerank retrieval results, run a Cross-Encoder/LLM, or evaluate ranking quality.

```text
CandidateProfile + JobProfile + optional RetrievalResult
                         |
                         v
                  FeatureExtractor
                         |
             +-----------+-----------+
             |                       |
        FeatureVector          FeatureDiagnostics
    stable model contract       inspection only
```

The two inspection APIs wrap the existing `RetrievalService`, batch-load canonical profiles, and retain the exact Phase 4 result order. PostgreSQL remains canonical; feature output is derived on demand and creates no migration or persistence table.

## Feature contract

- version: `feature_schema_v1`
- normalizer: `text_nfkc_casefold_technical_tokens_v2`
- fingerprint: `dc85c7237c6c67785199d221c919ae48c31c9a6323857070e6399d3eae365e42`
- artifact: `data/eval/phase5/feature_contract_v1.json`

The fingerprint is SHA-256 over stable JSON containing the version, ordered registry, formula versions, directions, ranges, missing policies, source policy, and normalizer version. It excludes time, paths, random IDs, machine/process state, data values, and evaluation results. The checked-in artifact must equal code generation.

`MODEL_FEATURE_ORDER` is the only Phase 6 model-input allowlist:

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

IDs, ranks, matched names, diagnostics, labels, and splits never enter this ordered vector.

## Normalization and matching primitive

Text normalization applies Unicode NFKC and casefold, preserves alphanumeric-attached `+`/`#` technical suffixes, removes an internal dot only when both adjacent identifier characters are alphabetic, replaces other punctuation/symbols with spaces, and collapses whitespace. Leading dots and dots adjacent to digits remain part of the token. This keeps `C`, `C++`, `C#`, `F`, and `F#` distinct; gives dotted/undotted spellings such as `Node.js`/`NodeJS` and `Next.js`/`NextJS` one lexical identity; keeps `.NET` distinct from both `NET` and `ASP.NET`; preserves numeric versions such as `4.1`; and treats slash-separated forms such as `C/C++` as separate tokens. The policy is deterministic and local. There is no online ontology, embedding lookup, LLM, hidden NLP model, product-specific alias table, or label-derived synonym table.

Candidate capability atoms come only from `skills.name`, `projects.technologies`, and `projects.skills_demonstrated`. Evidence atoms come only from `project_evidence.supports_skills` on records whose canonical `verification_status` is `available`. A full match requires the complete normalized atom phrase to occur on requirement-text token boundaries.

Requirement-category applicability is feature-specific. `skill_fit_score` and `missing_penalty` consider only Job `skill` requirements. `project_evidence_score` considers Job `skill` and `project_evidence` requirements because available structured evidence can support either. Job `experience` requirements are excluded from all three formulas: the Candidate contract has no dedicated structured work-experience signal, so a shared capability word must not satisfy an experience requirement. Role direction, location, seniority, work style, and AI tooling are handled separately.

Candidate skill categories and Job requirement categories are not isomorphic, so v1 does not invent category aliases or award category-only partial credit. The diagnostics field for weak matches remains structurally available for a future contract version if a canonical cross-schema taxonomy is approved; it is empty in v1. Must-have weight is fixed at 2 and nice-to-have weight at 1. These rules are static, label-free business rules and were not fitted to evaluation grades.

## Evidence verification policy

- `available`: `supports_skills` may create positive `project_evidence_score` atoms and positive evidence diagnostics.
- `described`: the canonical evidence record is retained for later inspection or caveated explanation, but contributes no positive Phase 5 model-feature evidence credit.
- `missing`: contributes no positive evidence credit or positive evidence diagnostics.

There is no `described = 0.5` heuristic, learned evidence weighting, free-text evidence matching, or semantic evidence ontology. Evidence statement, artifact reference, project name, and project summary are not scoring inputs.

## Feature registry

| Feature | Formula | Range | Missing policy | Direction |
|---|---|---:|---|---|
| `semantic_score` | unchanged Phase 4 `dense_score` | `[-1, 1]` | `null` when dense channel absent | higher is better |
| `sparse_score` | unchanged Phase 4 `sparse_score` | `[0, +inf)` | `null` when sparse channel absent | higher is better |
| `skill_fit_score` | weighted matched Job `skill` requirements / weighted Job `skill` requirements | `[0, 1]` | `null` when no Job `skill` requirements | higher is better |
| `project_evidence_score` | weighted Job `skill`/`project_evidence` requirements supported by `available` evidence / weighted applicable requirements | `[0, 1]` | `null` when neither applicable category exists | higher is better |
| `role_direction_score` | max target-role vs Job title/direction token-set Jaccard; exact phrase = 1 | `[0, 1]` | `null` when either side absent | higher is better |
| `ai_tool_score` | 1 for at least one explicit declared-tool phrase overlap in an AI-tooling requirement, otherwise 0 | `[0, 1]` | `null` when Job has no explicit AI-tooling requirement | higher is better |
| `location_score` | normalized exact city overlap | `{0, 1}` | `null` when either side absent | higher is better |
| `seniority_score` | Candidate canonical seniority is an exact Job accepted value | `{0, 1}` | `null` when either side absent | higher is better |
| `missing_penalty` | mean `1 - capability_match` across must-have Job `skill` requirements | `[0, 1]` | `null` when no must-have Job `skill` requirements | higher is worse |
| `overclaim_penalty` | canonical risk enum `low=0`, `medium=0.5`, `high=1` | `{0, 0.5, 1}` | `null` only for unavailable/invalid state | higher is worse |

`ai_tool_score=0` means no explicit overlap in an explicit tool requirement, not low overall AI competence. A missing value means the feature cannot be computed; it is never silently imputed to zero. Availability flags accompany every vector.

## Input allowlist

Candidate inputs:

- skill name/category;
- project technologies and demonstrated skills;
- evidence supported skills, verification status, and evidence type;
- target roles and declared AI tools;
- preferred cities and seniority;
- canonical overclaim risk level.

Job inputs:

- role title/directions;
- must/nice requirement text, category, and evidence expectation;
- evaluation focus;
- location cities and seniority requirements.

Retrieval inputs are the existing nullable dense/sparse scores. Phase 5 does not calculate another embedding or BM25 score and does not change channel semantics. The contract `source_policy` is the Phase 5 runtime input allowlist; it does not mean every listed field is consumed by every feature formula.

## Forbidden and construction-artifact inputs

Runtime formulas never use Candidate/Job IDs as values, Candidate name, company name, raw resume/JD, GitHub/artifact URLs, project name, project summary, evidence statement, provenance, data origin, archetype, schema/dataset version, split, annotation source, synthetic family/suffix text, relevance grade, hard-negative flags, pairwise preferences, or benchmark artifacts. IDs are routing/diagnostic identity only.

This preserves the Phase 4 construction-artifact repair: changing a synthetic project name/suffix, project summary, or evidence statement cannot change a model feature. Claimed capability and structured supporting evidence remain separate features.

## Diagnostics and bidirectional behavior

Non-model diagnostics include matched/weak/missing skill-requirement IDs, evidence-supported requirement IDs, matched structured capabilities/evidence skills/AI tools, location/seniority relation, overclaim level/reason count, per-feature availability, retrieval rank/channel ranks, and fusion score. Evidence-supported IDs and matched evidence skills originate only from `available` evidence. They omit raw source and evidence statement text.

For the same Candidate/Job pair, all profile-derived features are direction invariant. `semantic_score`, `sparse_score`, channel ranks, fusion score, and retrieval rank belong to the specific Job-to-Candidate or Candidate-to-Job retrieval context and may differ. Feature enrichment never sorts; entity order is identical to the wrapped Phase 4 response.

## APIs and errors

- `POST /api/v1/features/jobs/{job_id}/candidates`
- `POST /api/v1/features/candidates/{candidate_id}/jobs`

The body is the strict Phase 4 retrieval request (`strategy`, `top_k`, optional explicit city/seniority filters). The standard `success`/`data`/`error`/`request_id` envelope is retained. Each result contains the original retrieval result, `feature_vector`, and `feature_diagnostics`; top-level data includes version/fingerprint and original retrieval diagnostics.

Missing queries remain `profile_not_found`. Retrieval/model/index failures retain Phase 4 typed errors. Invalid canonical profile state is `invalid_profile_state`; a generated value outside the registry contract is `feature_contract_violation`. There is no empty-result or zero-filled fallback.

## Label independence and audit

Runtime feature modules do not import evaluation code, labels, query splits, pairwise preferences, hard negatives, or benchmark reports. Mutating external relevance/pairwise/hard-negative data cannot affect a vector because such data is not accepted by the extractor.

`data/eval/phase5/feature_audit_v1.json` is a deterministic profile-only audit over 48 Candidates x 19 train/dev Jobs = 912 pairs. It reads split IDs only to select the offline scope, never reads grades, and excludes all five test Jobs. It reports bounds, missingness, distinct counts, determinism, finite serialization, and source-contract checks. It contains no Recall/NDCG/MRR or test ranking metric.

Dense/sparse are 100% unavailable in the profile-only audit because there is intentionally no retrieval execution. The current `ai_tool_score` is constant 0 across the 912 pairs: all Jobs contain an AI-tooling requirement, but no declared Candidate tool phrase explicitly occurs in those requirement texts. This is retained honestly and did not trigger formula/alias tuning.

## Known limitations and Phase 6 handoff

- deterministic lexical matching is not a complete semantic skill ontology;
- Job `experience` requirements are not modeled by skill/evidence coverage because no dedicated structured Candidate experience signal exists;
- explicit tool overlap is not an overall AI-competence judgment;
- exact location does not infer distance or nearby cities;
- exact seniority provides no ordinal partial credit;
- the synthetic sandbox does not demonstrate real hiring effectiveness;
- the historical Phase 4 Dense truncation limitation and post-exposure fixed synthetic sandbox benchmark remain unchanged;
- `ai_tool_score` is constant zero in the current Train/Dev audit, while `semantic_score` and `sparse_score` are unavailable in the profile-only audit;
- there are no learned weights, LTR, Cross-Encoder, LLM ranking, final match score, or feature-based reranking.

Phase 6 may consume only `MODEL_FEATURE_ORDER` after verifying the exact version/fingerprint. Diagnostics are not model input. Phase 6 must define its own training, missing-value, and model-version policies and is not started by this phase.
