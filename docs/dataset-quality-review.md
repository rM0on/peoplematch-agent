# Phase 1 Dataset Quality Review — Semantic Repair v2

Review date: 2026-08-12
Dataset version: `1.0.0`
Schema version: `1.0`

## Review method

This repair combined full deterministic validation with a record-by-record semantic audit of all Grade 3 labels, all hard negatives, and all 48 pairwise preferences. The review traced job requirements to candidate claims, owned projects, available evidence, declared constraints, and label rationale. It did not use a retrieval or ranking model and does not constitute independent human labeling; annotation provenance remains `synthetic_curated`.

## External Review Findings

The external review identified five concrete quality risks:

1. The prior hard-negative sample listed `lbl_0019` even though its stored flag was `false`.
2. Grade 3 labels, including `job_001` with `cand_005` and `cand_007`, did not reference available evidence for every evidence-backed must-have.
3. Grade 2 rationales for `cand_041` and `cand_042` did not fully state their missing direct matching/ranking evidence and practical constraints.
4. Some hard negatives, especially `job_001` with `cand_011` and `cand_012`, relied on generic AI/Python proximity rather than a retrieval-confusing overlap.
5. Four candidates within an archetype shared project names, summaries, skills, evidence patterns, and a fixed quality order closely enough to create a synthetic shortcut.

## Repairs applied

### Grade 3 evidence coverage

Every Grade 3 label now links available evidence that covers each typed skill or project-evidence must-have. For `job_001`, both `cand_005` and `cand_007` link owned artifacts for Candidate retrieval, Feature engineering, and Offline evaluation. The Offline evaluation artifacts belong to existing candidate projects; no label-only evidence or future ranking score was added.

The validator now rejects a Grade 3 label when its own `supporting_evidence_ids` do not cover all evidence-backed must-haves with `verification_status = available`.

### Grade 2 gap completeness

`job_001` / `cand_041` remains Grade 2 because available Search relevance and Evaluation harness artifacts provide adjacent retrieval/evaluation evidence. Its rationale now states that Candidate retrieval, Feature engineering, and Offline evaluation lack direct evidence and records direction, project-depth, evidence, and seniority gaps.

`job_001` / `cand_042` moved from Grade 2 to Grade 1. Its relevant vocabulary is insufficient to overcome missing direct must-haves plus location, seniority, and zero-to-one work-style conflicts. All remaining Grade 2 labels link at least one available adjacent artifact and explicitly state why the pair remains plausible and why it is not strong.

### Hard-negative semantics

`job_001` / `cand_011` and `job_001` / `cand_012` are no longer hard negatives. Their ML infrastructure profiles are weak matches, but they do not contain enough matching/ranking/retrieval overlap to be likely semantic traps.

`job_001` / `cand_045` and `job_001` / `cand_046` are hard negatives: both explicitly claim ranking/recommendation/retrieval concepts, while direct matching artifacts are missing or only described. `lbl_0019` keeps the reviewed `job_002` / `cand_046` pair and now has `hard_negative = true`: the profile explicitly targets Recommendation Engineer and claims Learning to rank, but no available artifact covers Learning to rank, Feature engineering, or Offline evaluation.

All hard-negative rationales now use two explicit clauses: `Overlapping terms:` and `Actual mismatch:`. The validator recomputes meaningful overlap from candidate/job text and rejects evaluation-only or generic AI/Python overlap. The final dataset contains 46 semantically reviewed hard negatives; the count was not held to the earlier fixed distribution.

### Pairwise preferences

All 48 preferences were checked against job requirements, candidate evidence, constraints, and graded relevance. Every winner has a higher relevance grade than its loser. All rationales now name winner evidence coverage, loser overlap, and the decisive missing requirement.

`pref_004` changed from `cand_021 > cand_045` to `cand_006 > cand_046`. The previous NLP winner had a weak recommendation direction. The repaired pair prefers a recommendation-profile candidate with available Offline evaluation evidence over an explicit recommendation overclaim whose Learning-to-rank claim lacks an available artifact.

### Template diversification

All 12 candidate archetypes retain four profiles and stable candidate IDs, but now use at least two project concept families. Numeric project-name suffixes were removed. Within each archetype, raw narratives, project summaries, technology sets, evidence types, adjacent skills, and evidence-quality order vary. Archetype-specific variant permutations break the prior global `strong / medium / strong / overclaim` candidate-position pattern.

## Semantic review sample

The candidate sample is seven rather than six because the externally mandated IDs require seven distinct profiles.

- Candidates (7): `cand_005`, `cand_007`, `cand_011`, `cand_012`, `cand_041`, `cand_042`, `cand_045`
- Jobs (6): `job_001`, `job_002`, `job_003`, `job_004`, `job_014`, `job_024`
- Relevance labels (16): `lbl_0001` through `lbl_0012`, plus `lbl_0017`, `lbl_0018`, `lbl_0019`, and `lbl_0043`
- Pairwise preferences (8): `pref_001` through `pref_008`
- Hard negatives (10): `lbl_0005`, `lbl_0006`, `lbl_0007`, `lbl_0017`, `lbl_0018`, `lbl_0019`, `lbl_0030`, `lbl_0043`, `lbl_0161`, `lbl_0282`

Each listed hard-negative ID has `hard_negative = true`, relevance grade 1, at least one non-generic semantic overlap, and an explicit actual mismatch.

## Test-split challenge coverage

The five test queries (`job_020` through `job_024`) contain:

- direction-mismatch hard negatives;
- evidence-insufficient and overclaim hard negatives;
- location conflicts;
- seniority conflicts;
- evidence recovery, including adjacent Grade 2 candidates with multiple available supporting artifacts;
- evidence-backed pairwise challenges where the curated preferred candidate has stronger evidence than a lexically attractive hard negative.

This coverage is fixed by data semantics, not adjusted against future model output. Retrieval misses, ranking inversions produced by a model, and rerank regressions remain future pipeline-level observations.

## Remaining acceptable limitations

- Labels are synthetic curation, not independently adjudicated human judgments.
- Artifact availability is a sandbox fixture property, not proof of an external repository.
- The archetype-balanced catalog is intentionally not representative of a hiring market.
- Semantic overlap validation uses a documented domain signal vocabulary and cannot replace future reviewer adjudication.

## Result

The repaired dataset is internally consistent for Phase 1 review. Structural validation, semantic policy tests, and the documented spot-check agree; no retrieval, ranking, evaluation metric, or Phase 2 behavior was implemented.
