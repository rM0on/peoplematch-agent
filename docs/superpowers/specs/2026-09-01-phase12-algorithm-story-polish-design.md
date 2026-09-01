# Phase 12 Algorithm Story Polish Design

## Decision

Use a targeted, algorithm-first polish of the existing single-page product. Do not add placeholder pages or change any retrieval, feature, ranking, reranking, evaluation, dataset, or Phase 11 artifact semantics.

## Product framing

PeopleMatch Agent is presented as a Job-query-driven Candidate Retrieval + Ranking recommendation system. The interactive Resume input is a convenient way to add one candidate profile to the local candidate corpus; it is not a one-resume-to-one-job scoring workflow. A Job description becomes the query, Hybrid Retrieval builds a candidate pool, LambdaMART orders it, and the UI returns a Top-K recommendation list.

## UI design

- Keep the existing Phase 0.5 visual system and single-page workbench.
- Remove disabled navigation entries. Retain only the real recommendation workbench and Bad Case review route.
- Add a concise six-stage story rail: structured extraction, candidate retrieval, feature computation, LambdaMART ranking, Evidence explanation, MatchRun review.
- Explain before execution why one Resume/JD input can produce multiple candidates: the supplied candidate joins the local corpus and the Job drives Top-K retrieval and ranking.
- Present candidates with a human-readable rank label first and the opaque Candidate ID as secondary audit metadata.
- Label the raw value as `LTR Score` and state beside it that it is not a probability, match percentage, or hiring probability.
- Chinese-localize recruiter-visible headings while retaining necessary technical terms such as LTR, MatchRun, Evidence, Top-K, Retrieval, and Ranking.

## README design

- Make the first screen state `AI-powered Talent Matching & Recommendation System` and explain the four primary technical pillars in Chinese.
- Put the recommendation-system pipeline before long implementation detail.
- Describe Dense, Sparse, and Hybrid Retrieval by responsibility rather than as generic vector search.
- List the exact frozen ten-feature `MODEL_FEATURE_ORDER` without changing it.
- Separate Ranking ownership from LLM responsibilities.
- Preserve all frozen Phase 11 values and disclose synthetic data, 25% judgment coverage, five Test Jobs, and Phase 4 Test exposure next to the metrics.

## Screenshot design

Generate screenshots only from the final running application and deterministic synthetic demo. Capture the input/story workbench, Top-K result, LTR/Evidence detail, and MatchRun trace. Do not alter application data or screenshot content by hand.

## Integrity

- Phase 11 files, selected evaluation artifacts, labels, splits, Test results, Test seal, metrics, feature order, LTR model, CE experiment, and ranking logic remain byte-for-byte untouched.
- No production, hiring-accuracy, customer, user, QPS, business-impact, or Bonjour-integration claim is allowed.
- The existing Docker explanation-contract path bugfix remains a separate minimal runtime packaging repair with its RED/GREEN regression test.

## Rejected alternatives

- Adding Overview/Candidates/Jobs/Runs/Evaluation pages would expand scope beyond polish and create new product/API commitments.
- README-only changes would not resolve the demonstrated Top-K confusion in the real product.
