# Phase 13 Recommendation Product Experience Design

## Decision

Implement a freeze-safe presentation enhancement around the existing 48-candidate recommendation system. The frozen Candidate Profiles remain the only ranking corpus. Phase 13 adds an independent Chinese display catalog, additive Chinese deterministic Demo fixtures, Chinese-first product copy, and updated screenshots without changing any retrieval, feature, ranking, model, evaluation, or historical artifact semantics.

## Canonical boundary

Phase 13 is a product-experience enhancement after the completed Phase 12 local prototype. It may change presentation, deterministic Demo inputs, tests, documentation, and screenshots. It may not change Dataset `1.0.0`, the 48 frozen Candidate Profiles, labels, query splits, retrieval configuration, `MODEL_FEATURE_ORDER`, LambdaMART or Cross-Encoder artifacts, ranking logic, Phase 11 protocol, or Phase 11 results.

The current frozen dataset already contains 48 Candidates, so the requested 30–50-person scale is satisfied. Adding or rewriting Candidate rows is rejected because it would invalidate frozen hashes and evaluation evidence.

## Product model

The workbench presents one clear recommendation-system flow:

1. The user loads or pastes a Resume as an optional Candidate Profile input.
2. The user loads or pastes a JD as the recommendation Query.
3. The parsed Candidate joins the local runtime corpus; the frozen 48-person pool is not rewritten.
4. Hybrid Retrieval produces a candidate pool.
5. Explicit features feed the frozen LambdaMART model.
6. The system returns a Top-K recommendation list.
7. Evidence-grounded Explanation and historical Feedback/Bad Case review remain separate from ranking.

The first screen must make this model understandable without requiring users to inspect logs or JSON.

## Candidate presentation metadata

Create one frontend-only, typed metadata catalog keyed by the frozen `cand_001`–`cand_048` IDs. Each entry contains:

- a stable display label such as `候选人 001`;
- a Chinese technical direction derived from the existing frozen archetype;
- two or three concise strengths suitable for a recommendation card.

The catalog is presentation-only. It is never sent to the backend and must not participate in retrieval documents, feature calculation, LTR input, Evidence Facts, evaluation, or fingerprints. Unknown/runtime Candidate IDs use a deterministic fallback based on the parsed Candidate draft; they are never inserted into the frozen catalog.

## Chinese deterministic Demo fixtures

Add one Chinese/English mixed Resume fixture and one Chinese JD fixture, with schema-valid deterministic outputs. Register them alongside the existing Phase 3 fixtures instead of replacing those fixtures. `/api/v1/demo/samples` returns only the new Phase 13 Demo pair, while the old registered fingerprints remain valid for existing extraction and integration tests.

The sample is synthetic, contains no personal data, and is excluded from Offline Evaluation. Tests prove that the new pair parses through the same provider-neutral extraction service and that frozen candidate/evaluation files remain untouched.

## Workbench UX

- Use the title `AI 人岗匹配推荐工作台` and state that JD is the Query over a Candidate Pool.
- Keep both Resume and JD fields, but label their different roles explicitly.
- Expand Story Mode to seven steps: input Query, structured extraction, retrieval, feature computation, LambdaMART ranking, Evidence explanation, historical review.
- Present results as `岗位候选池 Top-K 推荐`, including indexed candidate count and final recommendation depth.
- Show the friendly candidate label/direction/strengths first and technical Candidate ID second.
- Label the raw model value `排序模型分值（LTR Score）` and keep the explicit non-probability disclaimer.
- Chinese-localize recruiter-visible explanation, trace, history feedback, and Bad Case copy. Closed backend enum values may remain as technical secondary text where translating them would alter a contract.
- Preserve the existing Phase 0.5 visual system and responsive behavior; do not introduce a UI framework or new application route.

## README and evidence

The Chinese-first README keeps the recommendation algorithm as the main story: Structured Extraction → Candidate/Job Representation → Hybrid Retrieval → Feature Engineering → LambdaMART → Evidence-grounded Explanation → Feedback/Bad Case → Offline Evaluation. It explains why LLMs do not rank and keeps all frozen Phase 11 numbers and limitations unchanged.

Screenshots are regenerated only from the final running application with the new Chinese synthetic samples. Required evidence covers the workbench/input, Top-K ranking, Evidence explanation, and historical review/MatchRun trace. No screenshot is manually edited.

## Error handling and accessibility

Existing bounded input checks and safe Provider error mapping remain. New display metadata must fail safely to an understandable generic label. Story steps, candidate selection, dialog controls, and Bad Case navigation remain keyboard-accessible and keep visible focus/ARIA semantics.

## Verification

Implementation follows RED → minimal GREEN. Required gates are:

- backend fixture/contract/API tests for Chinese deterministic extraction;
- frontend metadata, story, copy, ranking-card, history, and Bad Case tests;
- Node 22 frontend test/typecheck/lint/build;
- focused and full backend regression;
- real Browser → Next.js → FastAPI → PostgreSQL/Qdrant → Retrieval → LambdaMART → Explanation E2E;
- actual screenshot review;
- README link/copy review;
- secret/privacy scan;
- byte-level Phase 11 protection audit and frozen-path diff audit;
- one final checkpoint commit and no push.

## Rejected alternatives

- Modifying `data/samples/candidates.jsonl` is rejected because it is Dataset `1.0.0` and Phase 11 evidence.
- Creating a second 30–50-person ranking corpus is rejected because it would add new indexing/ranking semantics and expand the task beyond product polish.
- Frontend-only fake ranking data is rejected because screenshots and E2E must exercise the real pipeline.
