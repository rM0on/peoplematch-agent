# Phase 1 Labeling Guidelines

## Provenance

All current labels use `annotation_source = "synthetic_curated"` and have no independent annotator review. A future review must be recorded separately with reviewer protocol, adjudication notes, and a new dataset version.

Labels answer one query: **for this specific job, how suitable is this candidate based on the canonical profile, project evidence, and declared constraints?** They do not score a candidate in general.

## Graded relevance

### Grade 3 — Strong Match

Use when the candidate's role direction matches the job, core requirements have available project evidence, and location, seniority, and work style do not create a material conflict. A shared skill list without artifacts is insufficient.

### Grade 2 — Plausible Match

Use when the pair is credible but has an explicit, reviewable gap: project depth, one missing requirement, adjacent direction, or a constraint requiring discussion. At least one available artifact must substantiate the direct or adjacent capability that keeps the pair plausible. The rationale must explain both the recovery evidence and the remaining gap, and `affected_requirement_ids` must point to the relevant job requirement.

### Grade 1 — Weak / Misleading Match

Use when keywords or semantic content could make the pair look relevant, but evidence, direction, or a hard requirement materially undermines the fit. These records are particularly useful for later ranking diagnostics.

### Grade 0 — Non-match

Use when the candidate's core direction is unrelated or critical requirements have no support. Do not use grade 0 merely because a candidate is imperfect; grade 2 exists for credible gaps.

## Hard negatives

Set `hard_negative = true` only for grade 0 or 1 pairs that could plausibly be retrieved by lexical or semantic similarity. The rationale must explicitly name the misleading overlap and the actual mismatch. Generic AI/Python proximity and evaluation-only overlap are insufficient; the candidate and job must share at least one direction-bearing signal such as ranking, retrieval, agent workflow, model serving, model reliability, language-model work, product workflow, security, backend/data systems, or frontend work. Do not mark every weak candidate as a hard negative, and do not use the flag for difficult positive grade-2 records.

## Mismatch codes

- `DIRECTION_MISMATCH`: the daily work and career direction differ despite overlapping technology.
- `EVIDENCE_INSUFFICIENT`: a claim lacks available or sufficiently described supporting artifacts.
- `KEYWORD_FALSE_POSITIVE`: repeated vocabulary exaggerates practical relevance.
- `MUST_HAVE_MISSING`: a critical typed job requirement is unsupported.
- `LOCATION_MISMATCH`: declared cities/remote policy/relocation choices conflict.
- `SENIORITY_MISMATCH`: demonstrated scope does not satisfy the requested level.
- `WORK_STYLE_MISMATCH`: preferred operating environment conflicts with team stage or ambiguity.
- `OVERCLAIM_RISK`: breadth or level of claims is inconsistent with provided artifacts.
- `AI_TOOLING_GAP`: a specific AI-tooling expectation is absent.
- `PROJECT_DEPTH_GAP`: work is relevant but not deep enough for a stronger grade.

Codes are evidence-backed descriptions, not moral judgments. Multiple codes may apply; avoid adding codes that the canonical fields do not support.

## Evidence references

`supporting_evidence_ids` may include only evidence owned by the labeled candidate. Use available artifacts for grade 3. A described artifact may support a grade 2 rationale with an explicit caveat. Missing artifacts must never be presented as positive evidence.

`affected_requirement_ids` may include only requirements owned by the labeled job. Constraint mismatch codes must reference requirements of the corresponding category.

## Pairwise preferences

A pairwise record compares two candidates already labeled for the same job. The winner should have a higher graded relevance value in Phase 1. The rationale must explain why evidence or constraints outweigh superficial similarity; it must not rely on a future model score.

## Annotation examples

1. **Evidence-supported matching role — grade 3:** For `job_001`, `cand_005` demonstrates Candidate retrieval, Feature engineering, and Offline evaluation through three available sandbox artifacts. Direction and declared constraints align, so the pair is grade 3.
2. **Strong adjacent project, limited role depth — grade 2:** For `job_001`, `cand_041` has available Search relevance and Evaluation harness artifacts but no direct Candidate-retrieval or Feature-engineering artifact and remains early career. Adjacent evidence makes the pair plausible; direction, must-have, project-depth, evidence, and seniority gaps prevent grade 3.
3. **Ranking overclaim — grade 1 hard negative:** For `job_001`, `cand_045` explicitly claims Learning to rank, targets Recommendation Engineer, and uses retrieval/evaluation vocabulary, but no available artifact covers Candidate retrieval, Feature engineering, or Offline evaluation. Use `KEYWORD_FALSE_POSITIVE`, `OVERCLAIM_RISK`, `EVIDENCE_INSUFFICIENT`, and the applicable direction/must-have codes.
4. **Agent overclaim — grade 1 hard negative:** For `job_003`, an overclaim profile mentions agents and evaluation while its artifacts are described or missing. Use `EVIDENCE_INSUFFICIENT`, `OVERCLAIM_RISK`, and `KEYWORD_FALSE_POSITIVE` when supported.
5. **Senior platform role — grade 2:** For `job_008`, a mid-level infrastructure specialist with relevant serving work remains plausible but receives `SENIORITY_MISMATCH`; the affected requirement must be the seniority requirement.
6. **Location conflict:** A Beijing onsite-only candidate who declines relocation is not constraint-compatible with a Shanghai onsite/hybrid role. Add `LOCATION_MISMATCH` and reference the location requirement; choose grade based on the rest of the pair.
7. **Work-style conflict:** A profile limited to mature platform maintenance is weaker for a zero-to-one product role. Add `WORK_STYLE_MISMATCH`; do not infer personality or motivation beyond the declared preference.
8. **NLP vs agent product — grade 1 or 0:** Transformer training and LLM vocabulary do not establish tool-calling or user-workflow evidence. Use direction and must-have codes instead of treating all LLM experience as equivalent.
9. **Search evidence recovery — grade 2 or 3:** A candidate whose title is not “recommendation engineer” may still fit a retrieval relevance job when query analysis, judgments, and reranking artifacts directly support requirements.
10. **Pairwise evidence wins:** For `pref_001`, `cand_005` wins over `cand_045` because available artifacts cover all three evidence-backed must-haves; the loser contains ranking/retrieval/evaluation overlap without the required available evidence.

## Quality checks before accepting a label

1. Read the full candidate and job, not only skill names.
2. Trace every positive statement to evidence or a structured profile field.
3. Check location, seniority, and work style explicitly.
4. Ensure the rationale agrees with the numeric grade and hard-negative flag.
5. Verify all evidence and requirement IDs belong to the pair.
6. Confirm the label contains no model score, expected rank, or performance claim.
