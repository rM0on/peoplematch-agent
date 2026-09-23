# Engineering Decisions

## Why not pure LLM ranking?

LLMs are useful for semantic understanding, schema-constrained extraction and natural-language explanation. They are not the ranking owner because candidate ordering must support stable comparison, feature inspection, offline evaluation and historical reproduction.

A provider response may vary, time out or fail schema validation. None of those conditions should silently change an already produced shortlist. PeopleMatch Agent therefore freezes the ranking result before explanation begins.

## Why Hybrid Retrieval?

Dense retrieval captures semantic similarity and paraphrases. Sparse BM25 retrieval preserves exact technical names, tools and hard requirements. Equal-weight Reciprocal Rank Fusion combines their rank positions without pretending the two score distributions are directly comparable.

The frozen Phase 11 results also show why the architecture keeps strategy evaluation honest: Sparse was stronger than Hybrid on the small synthetic Test set. Hybrid remains a product design choice for complementary recall, not a claim of universal benchmark superiority.

## Why LambdaMART?

Talent recommendation is a query-group ranking problem: one job query competes among many candidates. LambdaMART fits that structure and lets the system combine semantic, lexical, skill, project, direction, location, seniority and risk signals while optimizing ranking metrics such as NDCG.

The model produces a raw ranking margin. It is intentionally not presented as a probability, hiring likelihood or calibrated match percentage.

## Why explicit features?

An embedding score alone cannot distinguish claimed skills from project evidence, model missing requirements, or expose overclaim/location/seniority risks. The frozen ten-feature contract makes these signals reviewable and keeps training, inference and historical MatchRuns aligned.

## Why can explanation not modify ranking?

Explanation is a post-ranking communication layer. Allowing generated text to reorder candidates would introduce sampling variance and hallucination into the decision owner, invalidate offline comparisons and make historical reproduction unreliable.

The persisted result fingerprint, candidate order and LTR margins are therefore inputs to explanation—not outputs from it.

## Why Evidence grounding?

Fluent text is not proof. The provider receives a bounded projection of candidate/job/ranking evidence using opaque references. Its structured plan must pass:

1. `ExplanationPlanV1` schema validation;
2. evidence ownership and reference validation;
3. grounding rules for strengths, risks, missing requirements and interview questions;
4. deterministic rendering before persistence.

If an output is structurally valid but violates grounding, the system may perform one constrained repair. The repair can normalize existing references but cannot create evidence or candidate facts.

## Why is Cross-Encoder optional?

Cross-Encoder reranking was implemented as a frozen experiment on the LambdaMART shortlist. The Test artifact did not show it outperforming LambdaMART on NDCG or explicit pairwise accuracy, so it was not promoted merely because it is a more fashionable model.

This is a deliberate model-governance decision: the default should follow evidence, not architecture theatre.

## Why does feedback not become training data automatically?

Reviewer feedback is contextual and may be incomplete or inconsistent. A Bad Case is an investigation object, not ground truth. Automatic promotion would contaminate labels and make evaluation provenance ambiguous.

The project keeps Feedback, Bad Case analysis, explicit judgments and evaluation artifacts as separate contracts.

## Why deterministic mock mode?

External providers are useful for real input, but CI and local review need repeatability. The deterministic mock and local MockTransport tests validate application contracts without API cost, network availability or model drift. Real-provider compatibility is reported separately and is never inferred from mock success.

## Known trade-offs

- The dataset is synthetic and small; metrics are descriptive sandbox evidence.
- Test queries were previously exposed, so the evaluation is not pristine held-out evidence.
- The default mock accepts registered fixtures rather than arbitrary text.
- A fresh clone needs the approved LambdaMART artifact or an explicitly reproduced artifact.
- MatchRun provenance is deeper than the compact visible trace in the current UI.
- The application is a local prototype, not an automated hiring decision system.
