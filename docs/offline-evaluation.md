# Phase 11 — Offline Evaluation Architecture and Protocol

## Document Status

- **Phase:** Phase 11 — Offline Evaluation
- **Architecture status:** Frozen for implementation
- **Implementation status:** Dev-frozen; formal Test sealed / not run
- **Protocol:** `phase11_eval_protocol_v1`
- **Metric semantics:** `phase11_metric_semantics_v1`
- **Architecture baseline:** `f45f7e34800ae7b1d48e55763737cdaca73ce289`
- **Scope:** Local, synthetic/sandbox, offline evaluation only

This document is the Phase 11 source of truth for evaluation questions,
judgment semantics, split usage, comparable strategy cohorts, metric semantics,
artifact provenance, leakage prevention, claim boundaries, and implementation
acceptance gates. The repository now implements the file-backed evaluator and
records a reproducible Dev artifact; formal Test remains sealed for a separate
closure run. No evaluation API, model change, dataset change, or runtime-default
change was introduced.

Current disk and Git state, `AGENTS.md`, the dataset freeze manifest, and the
frozen phase contracts remain authoritative. Historical Phase 4, 6, and 7
reports remain immutable stage evidence; this protocol does not rewrite or
reinterpret them as Phase 11 results.

## Implementation and Dev Freeze Status

The implementation is isolated under `backend/app/services/evaluation/` with a
PowerShell-compatible entry point at `scripts/run_offline_evaluation.py` and a
closed `phase11_evaluation_manifest_v1` contract. It provides strict frozen
judgment loading, pure Recall/NDCG/MRR/pairwise metrics, standard-Precision
rejection, R1/R2/R3 adapters over frozen services, full-pool comparability,
Qdrant vector-state fingerprints, predeclared slice diagnostics, Phase 10 truth
guards, deterministic explanation-integrity checks, immutable atomic artifacts,
and the explicit Test seal.

The Dev-only run uses Jobs `job_015`–`job_019`, the full 48-Candidate universe,
and the named derived Qdrant index state recorded in its manifest. Two fresh
runs from identical source, dataset, model, strategy, and index inputs produced
byte-identical report quality content and the same
`quality_result_fingerprint`. The selected immutable Dev artifact is stored
under `data/eval/phase11/runs/`; its manifest and report are the evidence source
for exact fingerprints, per-query orders, exclusions, and metrics. Exact run
identity stays in the immutable manifest rather than creating a self-reference
from this protocol document into the source-tree fingerprint.

The predeclared Dev leaders are Sparse for R1 and frozen LTR for R2. The optional
CE experiment remains weaker than LTR and remains experiment-only. These are
descriptive synthetic Dev findings, not a production winner or hiring-accuracy
claim. The selected Phase 11 vector-state fingerprint was rebuilt from the
complete local `all-MiniLM-L6-v2` snapshot in explicit offline mode and
reproduces the frozen Phase 4 R1 Dev Recall values. The historical Phase 4
report remains unchanged and retains its original protocol and exposure caveat.

Explanation-run evaluation and the 50-observation-per-stage latency campaign
are `NOT RUN`: no frozen persisted Dev ExplanationRun input set was registered,
and the full latency campaign was disproportionate to this quality freeze.
Their deterministic validators/summarizers are implemented and tested; single
run service timings are not substituted into quality results. Phase 10 review
exports were also not supplied and therefore were not converted into truth or
metrics.

Formal Phase 11 Test evaluation is `SEALED — NOT RUN`. Test Jobs remain absent
from implementation evaluation output. The next authorized step is the single
formal Test closure run under this frozen implementation and exact Test seal.

Fresh freeze verification from the repository root used:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_phase11_evaluation_artifacts.py backend/tests/test_phase11_evaluation_diagnostics.py backend/tests/test_phase11_evaluation_integrity.py backend/tests/test_phase11_evaluation_metrics.py backend/tests/test_phase11_evaluation_runner.py backend/tests/test_phase11_evaluation_slices.py -q
backend/.venv/Scripts/python.exe -m pytest backend/tests -q
backend/.venv/Scripts/python.exe scripts/run_offline_evaluation.py --split dev --include-r3 --output-root <artifact-root> --run-id <new-run-id>
```

The final focused result is 24 passed. The fresh full backend result is 792
passed and 58 environment-gated skips; required adapter integration had already
passed 13 tests with zero skips against explicitly disposable PostgreSQL and
Qdrant state, and the later formatting-only writer change did not touch adapter
semantics. Those exact disposable resources were removed after the final Dev
runs. No Test evaluation command was executed.

## Source-of-Truth Basis

This design was reconciled against the actual repository rather than a prior
conversation summary:

- `AGENTS.md`, `README.md`, `docs/PRD.md`, `docs/development-roadmap.md`, and
  `docs/architecture.md`;
- `data/eval/dataset_freeze_manifest.json`, `data/eval/query_splits.json`, the
  dataset card/labeling guidance/quality review, `data/samples/labels.jsonl`, and
  the executable graded/pairwise schemas;
- Phase 4 retrieval design, evaluator, frozen reports, and v4 exposure notes;
- Phase 5 feature contract, exact model-feature order, and fingerprint rules;
- Phase 6 LTR dataset/evaluation code, native-model metadata, and frozen Dev
  report;
- Phase 7 CE design, text/model manifests, Dev report, and local latency report;
- Phase 8 MatchRun architecture and historical request/result contracts;
- Phase 9 Evidence Bundle/Facts, explanation-plan/output, grounding, rendering,
  and immutable explanation-history contracts;
- Phase 10 Feedback/BadCase design, implementation notes, bounded projection
  behavior, and `phase10_review_export_v1`.

Two phase-local documents retain temporal pre-freeze prose: the Phase 7 document
ends by calling Phase 9 planned, and the Phase 9 explanation document still
labels its status in progress. The later canonical README, roadmap,
architecture, Git history, and Phase 10 final notes establish Phases 7 and 9 as
completed/frozen. The later canonical sources win; the old prose is preserved as
historical context and does not block Phase 11 architecture.

## Scope and Non-goals

Phase 11 answers:

> How do we evaluate this matching system reproducibly and honestly under
> incomplete synthetic judgments, frozen historical model stages, and
> non-pristine Phase 4 Test exposure?

Phase 11 v1 includes:

- stage-aware retrieval, ranking, and explicit pairwise evaluation;
- deterministic explanation integrity evaluation;
- predeclared diagnostic slices;
- separate local latency observations;
- immutable, versioned evaluation artifacts and human-readable reports;
- a Dev-selection and Test-seal protocol that prevents Test-driven tuning.

Phase 11 v1 does not include:

- changing labels, splits, profiles, retrieval configuration, features,
  LambdaMART, or the Cross-Encoder;
- training or fine-tuning;
- changing the runtime default or selecting a production winner;
- an evaluation API, database table, frontend, dashboard, or background job;
- automatic conversion of Feedback, SystemSignal, BadCase, or `VERIFIED` state
  into relevance truth;
- production latency, capacity, QPS, SLA, hiring accuracy, business impact, or
  real-world generalization claims.

## Architecture Decision

### Decision

Use one stage-aware offline evaluation module with four independent evidence
tracks:

1. full-corpus retrieval recall;
2. candidate-pool-controlled ranking and explicit pairwise evaluation;
3. deterministic explanation and review diagnostics;
4. separately reported local latency observations.

Each run validates frozen inputs before executing, records exact strategy and
candidate-pool provenance, computes per-query results before macro aggregation,
and finalizes a new immutable artifact directory. Quality, explanation, review,
and latency results remain separate sections and cannot be fused into one
universal score.

```text
frozen manifests + artifacts + contracts
                  |
                  v
        fail-closed input validation
                  |
        +---------+----------+----------------+
        |                    |                |
  retrieval cohort     ranking cohort   diagnostics
  full corpus           common pool      explanation/review/latency
        |                    |                |
        +---------+----------+----------------+
                  |
       immutable run artifacts + report
```

### Reason

The 288 explicit judgments cover only 25% of the 1,152 possible Job/Candidate
pairs. Full-list ranking metrics would be dishonest if the other 864 pairs were
silently assigned grade 0. At the same time, comparing LTR or CE against a
retriever with a different candidate set confounds recall with ordering. The
separate cohorts preserve unknown judgments, isolate the stage being measured,
and make every comparison auditable.

### Rejected alternatives

| Alternative | Rejection reason |
|---|---|
| Treat every unjudged pair as grade 0 | Converts unknowns into negatives and inflates apparent precision/order certainty. |
| Compute each strategy on its own top-k pool | Candidate-universe differences would be mislabeled as model-quality differences. |
| Use standard Precision@K over the full output | Its denominator would require unjudged results to be known non-relevant. |
| Use only the 12 judged Candidates as the strategy input | Removes the real full-corpus competition before scoring and overstates operational behavior. |
| Collapse ranking, explanation, review, and latency into one score | Mixes distinct questions and makes trade-offs or failures impossible to interpret. |
| Promote Phase 10 review records into labels | Human observations and case workflow states are not independently adjudicated relevance truth. |
| Rerun and overwrite Phase 4/6/7 reports | Destroys historical provenance and changes the meaning of frozen evidence. |

### Integrity implications

- Unknown remains unknown.
- A ranking comparison is valid only inside a named common-pool cohort.
- Test cannot define metrics, slices, thresholds, strategy eligibility, or a
  winner.
- A poor result is retained with its limitations; it does not authorize tuning.
- A protocol-semantic change produces a new protocol version and new artifacts.

## Evaluation Questions and Evidence Map

Every metric must answer a declared question. A run may omit a metric track
when its required inputs are unavailable, but it must record the omission; it
may not manufacture an empty success.

| ID | Evaluation question | Primary evidence | Interpretation boundary |
|---|---|---|---|
| `RQ-1` | At K=5, 10, and 20, how often does each frozen Dense, Sparse, or Hybrid retriever include explicitly judged relevant Candidates? | `retrieval_recall_at_k` and per-query recall | First-stage coverage only; not final ranking quality. |
| `RQ-2` | On one identical full Candidate pool, how well do frozen Hybrid ordering, LTR, and optional CE order the explicit graded judgments? | `judged_condensed_ndcg_at_5/10` | Conditional ordering over judged Candidates; not end-to-end precision. |
| `RQ-3` | How early does the first explicitly broad-relevant Candidate appear in that controlled judged ordering? | `judged_condensed_mrr_at_10` | First relevant rank only; not graded-list quality. |
| `RQ-4` | Do strategy scores agree with the 48 explicit pairwise preferences? | `explicit_pairwise_accuracy` | Explicit pairs only; complementary to, but not independent of, the synthetic curation process. |
| `RQ-5` | What relevant-label coverage survives the actual bounded runtime cascade? | `shortlist_relevant_coverage_at_k` diagnostic | Coverage of a named cascade and output depth; unequal cascades are not model-only comparisons. |
| `EQ-1` | Does every persisted explanation claim resolve to compatible Evidence Facts owned by the same historical result? | Grounding and ownership pass/failure counts | Explanation integrity only; not ranking accuracy. |
| `EQ-2` | Does explanation output preserve schema, historical, ranking-reference, and deterministic-repeatability invariants? | Separate consistency checks | No vague aggregate “quality” score. |
| `BQ-1` | Where do predeclared synthetic mismatch or Phase 10 review categories concentrate errors or exposure? | Slice diagnostics and linked cases | Diagnostic hypothesis generation only; not new truth or measured improvement. |
| `LQ-1` | What latency is observed for named stages on one recorded local environment? | Local p50/p95 and raw count | Local observation only; not production capacity or QPS. |

## Frozen Dataset and Judgment Semantics

### Dataset identity

Phase 11 v1 accepts only the dataset identity validated by
`data/eval/dataset_freeze_manifest.json`:

| Field | Frozen value |
|---|---|
| Dataset version | `1.0.0` |
| Schema version | `1.0` |
| Origin | `synthetic_sandbox` |
| Annotation source | `synthetic_curated` |
| Candidates | 48 |
| Jobs | 24 |
| Explicit graded judgments | 288, exactly 12 per Job |
| Explicit pairwise preferences | 48, exactly 2 per Job |
| Possible Job/Candidate pairs | 1,152 |
| Unjudged pairs | 864 |

The judgment matrix is incomplete. `unjudged != negative` is a protocol
invariant, not a reporting preference.

Dataset `1.0.0` labels and Test queries are immutable inputs to this protocol.
A genuine annotation correction requires a documented reason, a new dataset
version, regenerated freeze manifest/hashes, and re-reporting of every affected
experiment. A disappointing metric is not an annotation-correction reason.

### Relevance grades

The protocol uses the existing `RelevanceGrade` contract without adding or
renaming grades:

| Grade | Frozen dataset meaning | Broad binary role | NDCG gain |
|---|---|---|---|
| `0` | Explicit non-match | Judged non-relevant | `0` |
| `1` | Weak or misleading match | Judged non-relevant | `1` |
| `2` | Plausible match | Judged relevant | `3` |
| `3` | Strong match | Judged relevant | `7` |

The NDCG gain is `2^grade - 1`, giving `[0, 1, 3, 7]`. Grade 1 retains graded
utility in NDCG while remaining below the binary relevance threshold. This is
intentional and is not an inconsistency.

The predeclared binary thresholds are:

- `broad_relevance_v1`: grade >= 2. This is primary for Recall and MRR.
- `strong_relevance_v1`: grade == 3. This is optional diagnostic evidence and
  cannot select a strategy or replace the primary threshold.

No threshold may be selected or changed after inspecting Test results. Adding a
threshold or changing its role requires a protocol change.

### Concept definitions

| Concept | Meaning in Phase 11 | Evaluation use |
|---|---|---|
| Judged relevant | Explicit grade 2 or 3 under `broad_relevance_v1` | Primary binary Recall/MRR truth. |
| Judged non-relevant | Explicit grade 0 or 1 | Graded NDCG input and explicit non-relevant diagnostics. |
| Graded relevance | One explicit frozen grade 0–3 | NDCG only; never inferred from runtime scores. |
| Unjudged | No explicit row for that Job/Candidate pair | Unknown; never grade 0, never a negative. |
| Pairwise preferred | Explicit `winner_candidate_id` in one frozen preference row | Winner side of pairwise accuracy. |
| Pairwise non-preferred | Explicit `loser_candidate_id` in that same row | Loser side of pairwise accuracy; not a global negative. |
| Synthetic curated judgment | Manually curated sandbox label created with repository guidance | Valid only for this fixed synthetic benchmark and its documented limitations. |
| Human review observation | Immutable Phase 10 Feedback | Diagnostic/audit source only. |
| SystemSignal | Deterministic integrity or operational observation | Diagnostic/audit source only. |
| BadCase | Auditable investigation aggregate around historical evidence | Diagnostic slice or qualitative review source only. |
| `VERIFIED` case | Case-specific immutable verification reference exists | Proof only that that case's verification rule was satisfied; not ranking truth or aggregate improvement. |

### Truth-source allowlist

| Source | Ranking metric truth | Diagnostic use | Prohibited conversion |
|---|---:|---:|---|
| Frozen graded judgment | Yes | Yes | None beyond its explicit pair. |
| Frozen explicit pairwise preference | Pairwise metric only | Yes | Do not turn loser into a global grade 0. |
| Candidate/Job structured attributes | No | Predeclared slices only | Do not infer relevance. |
| Label mismatch codes and hard-negative flags | No new relevance; retain existing grade | Predeclared pair slices | Do not make a pipeline failure or model defect automatically. |
| FeedbackRecord | No | Review/audit slice | No grade, preference, training row, or accuracy label. |
| SystemSignal | No | Integrity diagnostic | No suitability or quality label. |
| BadCase/root cause/action | No | Case-level diagnostic | No grade, correctness label, or improvement metric. |
| `VERIFIED` | No | Verification audit | No model-improvement or evaluation-success claim. |

The labels and model features share concepts such as evidence, role direction,
and constraints. Every ranking report must disclose this construct-alignment
limitation; the benchmark is not an independently measured real-world outcome.

## Dataset Split and Test Seal

### Split unit and usage

The split unit is the Job query. All judgments and preferences for one Job stay
in one split.

| Split | Query IDs | Permitted use |
|---|---|---|
| Train | `job_001`–`job_014` | Existing frozen LTR training provenance; implementation fixtures and diagnostics that do not refit or alter the model. |
| Dev | `job_015`–`job_019` | Metric implementation debugging, strategy comparison, predeclared threshold confirmation, slice eligibility review, and report design. |
| Test | `job_020`–`job_024` | One sealed final evaluation or exact reproduction after all protocol and artifact gates pass. |

Phase 11 v1 does not retrain the Phase 6 model. “Train permitted” describes the
dataset role, not authorization to create a new model.

### Test prohibitions

Test queries, labels, preferences, outputs, or aggregate results must not be
used for:

- feature design or feature changes;
- retrieval weights, filters, embedding, or BM25 changes;
- model training, fine-tuning, hyperparameters, or reranker selection;
- threshold, gain, K, tie, missing-judgment, or metric-definition changes;
- strategy eligibility or candidate-pool changes;
- slice discovery, slice thresholds, or cherry-picking;
- repeated optimization, report selection, or winner selection;
- editing dataset labels because a result is disappointing.

### Freeze gate before Test

A Test run is legal only when all of the following are recorded in the input
manifest before execution:

1. `phase11_eval_protocol_v1` is frozen in Git.
2. Metric implementations and adversarial semantics tests pass on non-Test
   fixtures.
3. Dataset and strategy artifact fingerprints are validated.
4. Strategy IDs, roles, configurations, candidate-pool cohorts, and reporting
   order are frozen.
5. Primary metrics, K values, thresholds, aggregation, exclusions, and slice
   definitions are frozen.
6. Dev evaluation is complete and the descriptive Dev leader is recorded.
7. The report template and claim matrix are frozen.
8. The command includes an explicit `--allow-test` guard.

The future CLI must default to rejecting `split=test`. `--allow-test` is a
visible local engineering safety rail, not an access-control system. The Test
manifest must record the flag, operator-supplied reason (`final` or
`reproduction`), protocol Git commit, strategy-set fingerprint, freeze-gate
attestation, and the known Phase 4 exposure caveat.

A reproduction run may execute Test again only against the exact frozen input
fingerprint. It creates a new immutable run directory, must match the prior
deterministic quality-result fingerprint, and cannot authorize changes. A
different input fingerprint requires a new protocol/dataset or an explicit new
experiment scope; it must not silently reuse the v1 final-Test claim.

## Phase 4 Test Exposure

The Phase 4 v1–v3 repair process already exposed the five Test queries. The
accepted v4 result is therefore a **post-exposure fixed synthetic sandbox
benchmark**, not a pristine unseen held-out estimate.

Phase 11 must keep two evidence classes separate:

| Evidence class | Permitted use | Forbidden interpretation |
|---|---|---|
| Existing Phase 4 v4 report | Immutable historical reporting, regression visibility, and explicitly caveated sandbox context | Pristine holdout, selection-independent generalization, or proof of retriever superiority in general. |
| New Phase 11 Test artifact | Protocol-controlled comparison of frozen strategies with the same post-exposure caveat | Erasure of prior exposure or a new unseen-query claim. |

Phase 11 references old artifacts by version and SHA-256. It never imports
their values as newly computed Phase 11 metrics and never overwrites them. If a
genuinely pristine claim is later required, it needs new previously unseen Job
queries under a new documented dataset/evaluation version that was not
inspected during development. Creating that dataset is outside Phase 11 v1.

## Strategy Taxonomy

| Strategy ID | Stage | Input universe/pool | Score/order semantics | Frozen role |
|---|---|---|---|---|
| `dense_v4` | Retrieval | All 48 eligible Candidates, no primary filters | MiniLM cosine score; score descending, then Candidate ID | Frozen retrieval baseline |
| `sparse_bm25_v4` | Retrieval | Same 48-Candidate corpus | BM25 score; score descending, then Candidate ID; zero-score Candidates may be absent | Frozen retrieval baseline |
| `hybrid_rrf_v4` | Retrieval / baseline ordering | Same corpus; union of Dense/Sparse pools | Equal-weight RRF, then best channel rank, then Candidate ID | Frozen first-stage baseline |
| `ltr_ranker_v1` | Learned ranking | One Hybrid Candidate pool | Raw LightGBM margin; then retrieval rank, then Candidate ID | Default/core frozen ranking baseline |
| `cross_encoder_experiment_v1` | Semantic reranking | One LTR-ordered shortlist/pool | Raw CE logit; then LTR rank, retrieval rank, Candidate ID | Optional explicit frozen experiment only |

Raw cosine/BM25/RRF values, the LTR margin, and the CE logit have different
scales. They are never normalized into a universal score or interpreted as
probability, confidence, percentage, or hiring suitability.

The CE model remains the pinned, non-fine-tuned
`cross-encoder/ms-marco-MiniLM-L6-v2` experiment. The accepted Dev evidence is
a degradation relative to LTR. Phase 11 cannot change its model, text contract,
weights, input order, or role until it wins. LTR remains the runtime default
regardless of a Phase 11 descriptive comparison.

## Comparable Strategy Matrix

### Cohort R1 — Full-corpus retrieval comparison

Dense, Sparse, and Hybrid are compared with exactly the same:

- Job query IDs and split;
- 48-Candidate corpus and dataset fingerprint;
- `retrieval_doc_v4` documents and configuration fingerprint;
- no filters for the primary benchmark;
- K values 5, 10, and 20;
- broad relevance threshold and missing-judgment policy;
- index freshness checks and deterministic tie rules.

The Sparse result list may contain fewer than K Candidates when fewer positive
BM25 scores exist. Missing output positions are misses, not fabricated
zero-score results. The candidate universe is still the same 48-Candidate
corpus and the returned count is recorded.

Only retrieval metrics are compared in R1. R1 does not claim which strategy is
the better final ranker.

### Cohort R2 — Full-pool controlled ordering comparison

R2 isolates ordering rather than first-stage coverage:

1. Build one no-filter Hybrid pool containing all 48 unique Candidates for a
   Job. A query is invalid if corpus, eligible, returned, Dense pool, or Hybrid
   set integrity does not prove full Candidate coverage. Sparse provenance is
   recorded and may have fewer positive-scoring members.
2. Freeze and fingerprint that exact Candidate set.
3. Produce three orders over that same set: Hybrid order, LTR order, and the
   optional CE order. LTR scores all 48 Candidates; CE uses the allowed frozen
   `retrieval_pool_k=48`, `cross_encoder_pool_k=48`, `top_k=48` evaluation
   configuration and does not change model behavior.
4. Condense each full order to the same 12 explicitly judged Candidates, in
   strategy order, before computing graded ranking metrics.

R2 is intentionally not the default runtime cascade. Its claim is conditional:
“ordering over the identical full pool, evaluated on explicit judgments.” It
must not be described as end-to-end Top-K precision or as the product's normal
latency profile.

### Cohort R3 — Runtime-cascade diagnostics

R3 preserves actual frozen defaults:

- LTR: Hybrid pool 20 -> LTR top 10;
- optional CE: Hybrid pool 20 -> LTR top 10 -> CE top 5.

R3 reports candidate-pool retention, explicitly judged relevant coverage,
historical provenance, and separately measured latency. Since the output depths
and effective pools differ, R3 values cannot be used as an unqualified
LTR-versus-CE model-quality comparison. The report must name the cascade and K
in every metric field.

### Comparison legality

| Comparison | Status | Reason |
|---|---|---|
| Dense vs Sparse vs Hybrid in R1 | Allowed | Same queries, corpus, K, and judgment policy. |
| Hybrid order vs LTR vs CE in R2 | Allowed | Same 48-Candidate set, then same judged condensation. |
| LTR vs CE default runtime output in R3 | Restricted diagnostic | LTR returns 10 and CE returns 5 after another truncation. |
| Any R1 metric vs any R2 metric as one “winner” | Rejected | They answer coverage and conditional ordering questions, respectively. |
| Metrics with different pool fingerprints | Rejected | Candidate-pool provenance is not comparable. |
| Historical Phase 6/7 Dev values vs new Phase 11 values without protocol labels | Rejected | Candidate, cutoff, and metric semantics can differ. |

## Candidate Pool Provenance

Every query/strategy result records:

- candidate universe ID and the expected 48 Candidate IDs;
- source retrieval strategy and frozen configuration fingerprint;
- requested pool K, returned count, eligible count, filters, and index state;
- ordered source Candidate IDs and an order fingerprint;
- sorted unique Candidate IDs and the candidate-pool fingerprint;
- ranking strategy, rerank depth, score semantics, and canonical tie policy;
- feature version/fingerprint/order when LTR is involved;
- LTR model ID and native artifact SHA-256 when LTR or CE is involved;
- CE model revision, snapshot fingerprint, and text-contract fingerprint when CE
  is involved;
- dataset version, manifest SHA-256, split, query ID, and judgment-policy ID.

The pool fingerprint is SHA-256 over canonical JSON containing the query ID,
sorted unique Candidate IDs, source strategy ID/configuration, filters, and
requested/observed pool depth. It represents set identity, not ranking order.
A separate order fingerprint preserves the exact Candidate sequence. R2 refuses
to compare strategies unless their query-level pool fingerprints match.

Duplicate Candidates, unknown Candidate IDs, missing expected judged Candidates,
or an unproven full-pool claim make that query/strategy invalid. They are not
silently dropped.

## Strategy Selection Policy

Phase 11 does not change the product's default strategy. It records a
descriptive Dev leader within each comparable cohort so Test reporting is not
selected after seeing Test.

The predeclared R1 Dev ordering rule is:

1. macro `retrieval_recall_at_10` under broad relevance;
2. exact tie: macro `retrieval_recall_at_20`;
3. exact tie: macro `retrieval_recall_at_5`;
4. remaining tie: report co-leaders in stable strategy-ID order.

The predeclared R2 Dev ordering rule is:

1. macro `judged_condensed_ndcg_at_5`;
2. exact tie: macro `judged_condensed_ndcg_at_10`;
3. exact tie: macro `explicit_pairwise_accuracy`;
4. remaining tie: report co-leaders in stable strategy-ID order.

MRR, strict-threshold diagnostics, latency, and slices do not break ties. CE may
be named a descriptive cohort leader but remains experiment-only and cannot be
promoted to runtime default by Phase 11 v1. Test reports the already frozen Dev
leader(s) plus all predeclared baselines and the optional CE diagnostic in the
same fixed order. Test never reselects the leader.

## Missing-Judgment Policy

### Primary policy

Phase 11 v1 uses a stage-specific policy rather than one ambiguous global rule:

- **Retrieval and runtime shortlist:** keep the original full-corpus ranking.
  Unjudged Candidates may occupy Top-K positions but never enter the relevant
  numerator or denominator. They therefore consume scarce retrieval positions
  without being declared wrong.
- **Controlled ranking:** start from a real full 48-Candidate strategy order,
  then condense that order to the exact explicit judged set shared by all R2
  strategies. Compute metrics only after verifying the full pool and exact
  judged coverage.
- **Pairwise:** use only explicit preference rows and their two exact Candidate
  IDs. No preference is derived from graded labels.

This preserves operational retrieval pressure while avoiding grade invention in
ranking metrics.

### Query eligibility and exclusions

For dataset `1.0.0`, each expected query must have exactly 12 unique graded
judgments and 2 valid unique pairwise preferences. A missing query, duplicate
pair, unknown ID, or all-unjudged query makes the run `INVALID`; it is not an
ordinary metric exclusion.

For a valid future dataset, a query with explicit judgments but no relevant
Candidate under a requested binary threshold is ineligible for Recall and MRR
under that threshold and is recorded with `no_relevant_judgment`. NDCG is
ineligible when ideal DCG is zero. No undefined metric becomes numeric zero.
If a required metric has zero eligible queries, the run is `INVALID`.

Every aggregate reports total query count, eligible count, excluded count, and
each excluded query/reason. The complete per-query records remain available.

### What happens when Top-K contains an unjudged Candidate

| Metric context | Treatment |
|---|---|
| Retrieval Recall@K | Candidate occupies its rank; it is neither hit nor denominator member. |
| Runtime shortlist relevant coverage | Same as retrieval; unknown is not an error or negative. |
| R2 NDCG/MRR | Full order is first validated, then unjudged Candidates are removed by the declared judged-condensation step. |
| Standard Precision@K | Metric is not computed in v1. |
| Pairwise accuracy | Unrelated unless the Candidate is named in an explicit preference. |

## Metric Semantics

### Shared rules

- K values are fixed before Test.
- Per-query metrics are primary records; macro arithmetic mean is the primary
  aggregate.
- Weighted and micro aggregates are not part of v1 because they can let one
  query or candidate count dominate another.
- The report includes mean, total/eligible/excluded query counts, per-query
  values, and per-query strategy deltas. Min/max may be displayed as descriptive
  context, never as a selection criterion.
- With only 24 Jobs and 5 Test Jobs, v1 makes descriptive comparisons only. It
  does not report p-values, “statistical significance,” or generalizable gain.
  Bootstrap intervals are deferred because five exposed Test queries cannot
  support the intended inferential reading.
- All ranking ties use the frozen strategy's canonical order. The evaluator may
  not add a new score perturbation. Numeric score ties in pairwise accuracy score
  0.5 even when a deterministic ID fallback determines display order.

### Recall@K

For Job `q`, threshold `t`, and strategy order `R_q`:

```text
Rel(q, t) = {candidate | an explicit judgment exists and grade meets t}
Recall@K(q, t) = |topK(R_q) intersect Rel(q, t)| / |Rel(q, t)|
```

Primary retrieval metrics are `retrieval_recall_at_5`,
`retrieval_recall_at_10`, and `retrieval_recall_at_20` under
`broad_relevance_v1`. Their denominator contains all explicitly judged
relevant Candidates for that query, whether or not the retriever returned them.
Unjudged Candidates never enter the denominator.

R3 may report `shortlist_relevant_coverage_at_5/10` with the same formula, but
the field name, cascade ID, and output depth must remain explicit. Retrieval
Recall and final-shortlist coverage are not combined.

Strict grade-3 Recall may be emitted as `diagnostic_strong_recall_at_k` only if
enabled before Test for every strategy. It cannot be the headline or selection
metric.

### Precision@K legality

| Form | Decision for v1 | Reason |
|---|---|---|
| Standard full-ranking Precision@K | **REJECT** | An unjudged Top-K Candidate would be counted as non-relevant. |
| “Judged-only Precision@K” over original Top-K | **RESTRICT / NOT IMPLEMENTED** | Its variable judged denominator makes cross-query and cross-strategy values unstable and easy to mislabel. |
| Precision over the condensed 12-Candidate order | **REJECT AS REDUNDANT** | It is conditional on an artificial judged view and adds little beyond Recall/NDCG while inviting a standard-precision claim. |

Phase 11 v1 records the raw `judged_count_at_k` and
`judged_relevant_count_at_k` diagnostics when helpful, without dividing them
into “Precision.” Standard Precision becomes legal only under a future protocol
with a complete or independently justified pooling/adjudication policy.

### NDCG@K

R2 primary metrics are `judged_condensed_ndcg_at_5` and
`judged_condensed_ndcg_at_10`.

For the judged-condensed grade sequence `g_1 ... g_n`:

```text
gain(g) = 2^g - 1
DCG@K = sum from i=1 to min(K,n) of gain(g_i) / log2(i + 1)
IDCG@K = DCG@K of the same judged grades sorted descending
NDCG@K = DCG@K / IDCG@K
```

The ideal ranking uses exactly the same 12 explicit judgments for that query,
not the full 48 Candidates and not fabricated grades for unknowns. If IDCG is
zero, NDCG is undefined and the query is excluded with a reason; it is never
reported as zero. Strategy output ties retain the frozen deterministic
strategy order before condensation.

The chosen K values match the current shortlist review depths while leaving
enough distinction in a 12-judgment group. More K values are not added merely
to find a favorable result.

### MRR

The primary MRR is `judged_condensed_mrr_at_10` under
`broad_relevance_v1`:

```text
MRR@10(q) = 1 / first_rank  if the first grade >= 2 occurs at rank <= 10
            0               if no grade >= 2 occurs in the first 10
```

It is computed on the R2 judged-condensed order and macro-averaged over eligible
queries. A strict grade-3 version may be emitted only as a predeclared
diagnostic. Historical Phase 6/7 `mrr` evaluated the full judged group without
this v1 field name/cutoff; those values remain historical and must not be mixed
with the new metric.

### Pairwise accuracy

`explicit_pairwise_accuracy` uses only the 48 frozen pairwise rows:

```text
1.0  if strategy_score(explicit_winner) > strategy_score(explicit_loser)
0.5  if the two raw strategy scores are exactly equal
0.0  otherwise
```

Each strategy must provide finite raw scores for both Candidates from the same
R2 pool. A missing Candidate, missing/non-finite score, cross-query pair,
duplicate pair, or mismatched pool fingerprint makes the query/strategy invalid;
it does not score 0. Pairwise truth is never synthesized from graded labels.

The pairwise labels and graded judgments come from the same synthetic curation
process. Pairwise accuracy is complementary evidence about explicit preference
direction, not an independently collected ground-truth validation and not a
second copy of NDCG.

## BadCase and Slice Protocol

Slice definitions are protocol inputs. Their membership rules and minimum
counts must be frozen on Train/Dev before Test. A slice may diagnose where a
metric changes; it cannot redefine the primary metric or select the winner.

### Frozen label/profile slices

The v1 slice registry may contain only the following predeclared deterministic
rules from existing fields:

| Slice ID | Membership rule | Applicable evidence |
|---|---|---|
| `hard_negative_v1` | Explicit judgment has `hard_negative=true` | Top-K/rank exposure and pairwise error diagnostics; not positive relevance. |
| `direction_mismatch_v1` | Explicit judgment contains `DIRECTION_MISMATCH` | Pair rank/exposure and query-cohort metric deltas. |
| `evidence_insufficient_v1` | Contains `EVIDENCE_INSUFFICIENT` | Same, with construct-alignment disclosure. |
| `must_have_missing_v1` | Contains `MUST_HAVE_MISSING` | Same; no automatic filter-failure claim. |
| `location_mismatch_v1` | Contains `LOCATION_MISMATCH` | Same; no suitability claim. |
| `seniority_mismatch_v1` | Contains `SENIORITY_MISMATCH` | Same; no employability claim. |
| `project_depth_gap_v1` | Contains `PROJECT_DEPTH_GAP` | Same, evidence-depth diagnostic only. |
| `overclaim_label_v1` | Contains `OVERCLAIM_RISK` | Same; not a claim about Candidate truthfulness. |
| `profile_high_overclaim_v1` | Frozen Candidate `overclaim_risk.level == high` | Top-K profile exposure only; never relevance truth. |

Other existing mismatch codes may be added only by a protocol revision or a
pre-Test registry amendment committed before any Test execution. Empty codes
such as a code with no current members do not produce a zero-valued success.

For an aggregate slice result, v1 requires at least 5 explicit judged pairs
across at least 2 Job queries. Otherwise the report lists case IDs/counts with
`SMALL_N` and emits no aggregate metric. Any slice spanning fewer than 5 queries
is explicitly descriptive; this warning necessarily applies to every Test
slice because Test has only 5 Jobs.

Mismatch slices do not compute a standalone NDCG after retaining only
non-relevant/mismatch rows, because the ideal gain may be zero and the meaning
would be inverted. Allowed diagnostics are:

- rank and Top-K presence of explicit slice members;
- primary per-query metric deltas on the predeclared query cohort containing at
  least one slice member;
- explicit pairwise errors whose named Candidates are slice members;
- linked qualitative cases with stable IDs.

### Phase 10 review slices

`phase10_review_export_v1` may define case-level cohorts by its closed symptom,
root-cause, evidence-kind, action, status, and verification fields. Such cohorts
report case counts, immutable historical links, and qualitative examples only.
They do not produce relevance metrics, correctness rates, or improvement rates.

The export must be complete and schema-valid. A truncated aggregate, missing
verification provenance for `VERIFIED`, unknown taxonomy value, or free-form
substitute is rejected. Phase 11 must not introduce a handwritten UUID workflow
or a source-discovery API to obtain review inputs.

## Explanation Evaluation Protocol

Explanation evaluation is a separate deterministic integrity suite over a
completed historical MatchRun, its persisted Evidence Bundle/Facts, one
completed ExplanationRun, and `explanation_output_v1`. It never changes or
scores ranking quality.

### Evaluation units and checks

| Check | Exact meaning | Output |
|---|---|---|
| `schema_validity` | Bundle, facts, plan boundary where available, and output validate their exact closed contract versions and bounds. | Pass/fail plus contract errors. |
| `evidence_reference_validity` | Every persisted output evidence reference exists in the bound Facts/Bundle and has a kind compatible with the rendered section/operation. | Valid/invalid reference counts. |
| `evidence_ownership_consistency` | Every Candidate-owned reference belongs to the same Candidate ID and result rank; comparison references bind the permitted top-1 owner. | Pass/fail plus offending IDs. |
| `unsupported_claim_count` | Each rendered factual claim unit has at least one semantically compatible persisted Evidence Fact. | Unsupported count and `unsupported_claim_rate = unsupported / total factual claim units`. |
| `ranking_reference_consistency` | Candidate IDs, ranks, ranking variant, and top-1 comparisons equal the immutable MatchResult history. | Pass/fail. |
| `historical_snapshot_consistency` | Bundle/result/input fingerprints and ExplanationRun ownership bind to the same completed MatchRun snapshot. | Pass/fail. |
| `ranking_invariance` | MatchRun result fingerprint and ordered MatchResults are unchanged before and after explanation generation/read evaluation. | Pass/fail; any change is an integrity failure. |
| `deterministic_repeatability` | For the deterministic mock and identical normalized inputs/contracts, rebuilt facts and rendered output have the same content fingerprints. | Pass/fail and fingerprints. |

A factual claim unit is one persisted summary, match reason, risk point, missing
requirement statement, interview question operation, top-1 comparison, or
rewrite operation carrying evidence references. Structural headings are not
claims. A zero-claim completed output is invalid under the existing output
contract rather than a perfect unsupported-claim rate.

“Explanation consistency” is not one ambiguous 0–1 score. Reports keep schema,
reference, ownership, ranking, historical, and repeatability checks separate.
External provider plans may vary; their primary acceptance remains closed-schema
validation and deterministic backend grounding. LLM-as-judge is excluded from
v1 primary evaluation. A future optional judge would require a versioned rubric,
recorded model/revision/prompts, deterministic reference cases, and an explicit
non-authoritative claim boundary.

## Latency Protocol

Latency is a distinct local observation artifact. It never changes a quality
leader or enters a combined score.

### In-scope measurements

- Dense, Sparse, and Hybrid retrieval for a named corpus/index state;
- feature construction plus LTR scoring for a named pool depth;
- CE scoring for named batch and pool depths, including default depth 10 and
  controlled R2 depth 48 when requested;
- deterministic mock evidence/facts/grounding/rendering;
- optional full MatchRun latency for a named local Compose topology.

External provider/network latency is excluded from the primary local summary.
If observed, it is stored in a separate provider-specific section with endpoint
class, provider/model, timeout policy, sample count, and nondeterministic flag.
It is never combined with deterministic local latency.

### Measurement method

- single client/concurrency unless a different value is explicitly named;
- fixed Dev query sequence and exact candidate-pool configuration;
- one untimed five-query warm-up pass;
- 50 measured observations per stage/configuration, cycling the five Dev Jobs
  ten times in stable order;
- monotonic high-resolution clock around only the named stage boundary;
- raw observation count plus median/p50 and linearly interpolated p95;
- failures reported separately and excluded from timing only with exact reasons;
  a failed operation never becomes a zero-duration observation;
- cold model/index load, if measured, is a separate diagnostic with at least 5
  fresh-process observations and raw/median/min/max values; no p95 is claimed for
  five cold samples.

The environment record includes OS/build, CPU model/logical cores, RAM, Python,
relevant library versions, model revisions/hashes, thread counts, device,
Docker/native topology, database/Qdrant versions when involved, batch size,
pool depth, warm-up/count, clock, and source commit. Results are described only
as local sandbox observations. They are not production latency, throughput,
capacity, QPS, concurrency, or SLA evidence.

The historical Phase 7 latency report remains frozen local evidence with its
own method. A new Phase 11 measurement references it but does not merge or
overwrite it.

## Phase 10 Review Artifact Boundary

Phase 11 may consume a schema-valid, complete `phase10_review_export_v1` only
for:

- diagnostic categorization;
- stable audit links to one historical MatchRun/MatchResult;
- qualitative BadCase review;
- case-level slice membership and hypothesis generation.

It must not automatically:

- convert Feedback to a relevance grade or pairwise preference;
- convert SystemSignal to recommendation correctness;
- convert BadCase/root cause to a model-quality label;
- convert a completed ResolutionAction to measured improvement;
- convert `VERIFIED` to ranking or explanation ground truth;
- calculate a case “accuracy” or improvement rate.

Creating derived evaluation labels would require a separate, explicitly
authorized adjudication process with independent reviewers, a versioned label
contract, disagreement handling, provenance, and a new dataset/evaluation
version. That process is not part of Phase 11 v1.

## Runtime and Evaluation Separation

Phase 11 implementation belongs in an independent application-service boundary
and local scripts. It may call frozen stage interfaces or consume frozen
artifacts, but it cannot place metric behavior in an API endpoint, MatchRun
execution, ranking service, explanation provider, Feedback service, or BadCase
workflow.

The minimal proposed implementation structure is:

```text
backend/app/services/evaluation/
  contracts.py       # protocol, manifest, metric specifications
  judgments.py       # explicit judgment joins and eligibility
  metrics.py         # pure reference-tested metrics
  strategies.py      # adapters over frozen stage interfaces
  runner.py          # split/test gates and cohort orchestration
  artifacts.py       # canonical hashing and immutable finalization
scripts/
  run_offline_evaluation.py
data/contracts/
  phase11_evaluation_manifest_v1.json
data/eval/phase11/runs/
  <evaluation_run_id>/
docs/
  offline-evaluation.md
```

This is a proposed implementation boundary, not a requirement to create every
file before behavior needs it. No Phase 11 database migration, public endpoint,
frontend route, or evaluation service process is approved. Metrics and artifact
logic should remain pure/file-backed; PostgreSQL/Qdrant integration is required
only for adapters that actually execute the existing runtime stages and must use
disposable seeded infrastructure.

## Evaluation Artifact and Manifest Contract

### Artifact set

Every attempt receives a new directory and never overwrites an older path:

```text
data/eval/phase11/runs/<evaluation_run_id>/
  manifest.json
  per_query.json
  report.json
  report.md
  latency.json             # only when latency was requested
  failure.json             # only for FAILED or INVALID attempts
```

The future JSON Schema contract is `phase11_evaluation_manifest_v1`. A run ID
contains UTC start time plus a prefix of the evaluation-input fingerprint; the
timestamp distinguishes immutable attempts while the fingerprint identifies
equivalent inputs.

### Required manifest identity and provenance

The manifest contains only fields needed to interpret and reproduce the run:

| Group | Required fields |
|---|---|
| Run identity | `evaluation_run_id`, contract/protocol/metric-semantics versions, run kind, status, start/end UTC timestamps |
| Source | source commit SHA, dirty-state flag (must be false for sealed Test), command/arguments, implementation package version |
| Determinism | `random_seed` (`null` when no randomness is used), deterministic/nondeterministic component flags, and affected fields |
| Dataset | version/schema/origin/annotation source, freeze-manifest SHA-256, canonical file hashes, split, exact query IDs, graded/pairwise counts |
| Judgment policy | broad/strict threshold IDs, gain, missing-judgment policy, query eligibility/exclusion policy |
| Metrics | exact metric IDs, K, gain/threshold, cutoff, condensation, tie, aggregation, and selector role |
| Strategies | IDs, stage/role, full frozen configuration, score semantics, output/order fingerprints |
| Pools | universe ID, filters, requested/observed depths, per-query pool and order fingerprints, comparability cohort |
| Frozen artifacts | retrieval document/config/index fingerprints; feature version/fingerprint/order; LTR model ID/SHA; CE model/revision/snapshot/text fingerprints when applicable |
| Test seal | allow flag, access reason, protocol/strategy/report freeze SHAs, Phase 4 exposure flag/caveat, prior final-run reference for reproduction |
| Outputs | per-query and aggregate artifact paths/SHA-256, eligible/excluded queries/reasons, warnings, claim limitations |
| Optional diagnostics | slice registry fingerprint, Phase 10 export version/hash, explanation contract/fingerprints, latency environment/sample metadata |

Environment hardware details are required only for latency. Hostnames, usernames,
absolute personal paths, credentials, raw profiles, prompts, provider responses,
and free-form private notes are excluded.

### Fingerprints

The artifact set uses canonical JSON, finite float64 values, sorted object keys,
and explicit array ordering:

- `evaluation_input_fingerprint`: protocol, dataset, query split, judgment and
  metric specifications, strategy configs, source artifact hashes, and pool
  cohort rules;
- `quality_result_fingerprint`: exact strategy output orders, per-query quality
  metrics, exclusions, and aggregates; excludes run ID, timestamps, environment,
  and latency;
- `manifest_fingerprint`: completed canonical manifest excluding its own
  fingerprint field;
- per-file SHA-256 values, including a separate latency artifact hash because
  latency is intentionally nondeterministic.

The same clean commit, frozen artifacts, dataset manifest, protocol, and strategy
configuration must reproduce the same deterministic strategy outputs and
`quality_result_fingerprint`. Any intentional nondeterminism records its seed,
source, and affected fields; silent randomness is invalid.

### Run lifecycle and immutability

Allowed statuses are `RUNNING`, `COMPLETED`, `FAILED`, and `INVALID`.

- `RUNNING` is created before stage execution.
- `COMPLETED` requires every requested cohort, required metric, output hash,
  exclusion record, and limitation to be present and schema-valid.
- `FAILED` means an operational dependency/stage failed after valid inputs.
- `INVALID` means protocol, dataset, artifact, Test-seal, or comparability
  validation failed.

Implementation writes into a new staging directory and atomically finalizes the
new run directory. An existing final directory or artifact is never updated.
An overwrite attempt fails. A partial run cannot be promoted to `COMPLETED` and
cannot expose normal-looking aggregate metrics as a success artifact.

## Protocol and Metric Versioning

`phase11_eval_protocol_v1` must change when any of the following semantics
change:

- judgment or missing-judgment policy;
- relevance threshold, gain, metric definition, or query eligibility;
- comparable candidate-pool/cohort rule;
- strategy selection or Test-seal rule;
- slice membership meaning;
- artifact schema meaning or claim boundary.

Typos, clarifications that do not change executable meaning, and added links do
not require a protocol bump. Metric semantics use the single
`phase11_metric_semantics_v1` identifier plus explicit metric parameters in the
manifest; separate `ndcg_v1`, `recall_v1`, and similar versions are unnecessary
unless one metric's semantics changes independently.

## Reproducibility and Historical Artifact Policy

- No unrecorded randomness is permitted in quality evaluation. If a future
  component needs randomness, the seed and algorithm are manifest inputs.
- Runtime dependencies load only pinned local model artifacts and fail on
  fingerprint mismatch; Phase 11 does not download or regenerate them silently.
- Dataset validation precedes profile, label, model, retrieval, or explanation
  execution.
- Per-query output orders are retained so a metric can be independently
  recomputed.
- Historical Phase 4/6/7 artifacts are referenced by version/hash and described
  under their original protocol. A rerun under Phase 11 creates a new artifact
  with Phase 11 semantics.
- Evaluation artifacts are append-only like MatchRun, ExplanationRun, and Phase
  10 review history. A new protocol, model, strategy config, dataset, or source
  commit produces a new run.

The native LTR model and CE snapshot remain ignored local artifacts. A missing
artifact means the affected strategy is unavailable and the requested run
fails; a report cannot silently omit it after the strategy set was frozen.

## Failure Semantics

The future runner fails closed on at least:

- dataset file/hash/version/schema mismatch;
- missing, duplicate, cross-split, or unknown query/Candidate IDs;
- unexpected judgment counts, invalid grades, or invalid pairwise ownership;
- missing strategy/model artifact or non-finite score;
- LTR model hash, feature order, or feature fingerprint mismatch;
- CE revision/snapshot/text-contract mismatch;
- retrieval document/config/index/freshness mismatch;
- candidate-pool provenance absent or fingerprints different in R2;
- a full-pool claim that does not contain all 48 unique Candidates;
- a judged Candidate or explicit pairwise Candidate missing from the controlled
  pool or strategy score map;
- unknown/undefined metric, no eligible query for a required metric, or illegal
  Precision request;
- Test without explicit permission or with an incomplete/mismatched seal;
- Test-driven strategy/metric/slice mutation detected by frozen fingerprints;
- truncated or invalid Phase 10 export, or any attempt to use review state as
  relevance truth;
- artifact overwrite, output hash mismatch, or partial run completion.

Failures produce bounded safe details and a `FAILED` or `INVALID` manifest. They
never become zero metrics, an empty success, a skipped strategy presented as a
comparison, or a normal `COMPLETED` report.

## Claim Matrix

Every report associates a metric with its evidence scope and allowed language.

| Evidence | Allowed claim pattern | Forbidden interpretation |
|---|---|---|
| R1 Dev | “On five synthetic Dev Jobs under protocol X, strategy A had higher judged-relevant Recall@10 than B.” | “A generally retrieves better Candidates” or production recall. |
| R1 Test | Same, plus “post-exposure fixed synthetic sandbox benchmark.” | Pristine holdout or unseen-query generalization. |
| R2 | “Over the identical full Candidate pool and judged-condensed ordering, A had higher NDCG@5 than B.” | Full-corpus Precision, hiring accuracy, or causal model improvement. |
| Pairwise | “A agreed with more explicit synthetic pairwise preferences.” | Independent human-ground-truth accuracy or general preference quality. |
| Explanation | “All/ some persisted claim references passed deterministic grounding checks.” | The prose is universally useful, unbiased, or persuasive. |
| Phase 10 slice | “Cases with symptom X are listed/concentrated in this diagnostic cohort.” | X is a measured model defect rate or a verified improvement. |
| Latency | “On recorded local hardware, median/p95 for stage X was Y.” | Production capacity, QPS, SLA, or customer latency. |

Explicitly allowed project-level claims remain limited to a locally runnable
prototype over synthetic/sandbox data, frozen retrieval/LTR/optional CE stages,
historical orchestration, deterministic evidence-grounded explanation,
structured review, and reproducible local offline evaluation once implementation
and runs are actually complete.

Reports must not claim production readiness, real users/recruiters/customers,
Bonjour or ATS integration, online A/B testing, real traffic, hiring outcomes,
business impact, real-world generalization, or model improvement inferred from
Feedback/actions/`VERIFIED` cases.

## Report Structure

Every completed Phase 11 report follows this order:

1. protocol and run identity;
2. dataset, split, judgment coverage, and limitations;
3. strategy taxonomy and comparable cohort matrix;
4. retrieval metrics and per-query values;
5. controlled ranking metrics and per-query deltas;
6. explicit pairwise metrics;
7. explanation integrity diagnostics;
8. predeclared label/profile and Phase 10 review slices;
9. local latency observations in a separate section;
10. exclusions, failures, and warnings;
11. claim boundary and Phase 4 exposure statement;
12. reproducibility manifest and artifact hashes.

No section is silently removed. An unavailable section states `NOT RUN` or
`NOT APPLICABLE` with the exact reason; it does not imply PASS.

## Implementation TDD / RED Gates

Phase 11 implementation must begin with failing tests that prove at least:

### Judgment and metric semantics

- an unjudged Candidate is not treated as negative;
- a missing query judgment set invalidates dataset `1.0.0`;
- all Candidates unjudged invalidates the run;
- no relevant judged Candidate makes the affected metric undefined/excluded,
  not a fabricated zero;
- NDCG uses gains `[0, 1, 3, 7]`, log2 discount, same judged-set ideal, and exact
  K truncation;
- deterministic ranking ties preserve the frozen tie order;
- standard Precision@K is rejected under incomplete judgments;
- macro aggregation reports total/eligible/excluded queries and reasons.

### Pairwise and comparability semantics

- only explicit pairwise rows are used;
- a numeric score tie contributes 0.5;
- a missing/non-finite pair Candidate score fails;
- duplicate/cross-query preference fails;
- a missing Candidate in the controlled pool fails;
- different candidate-pool fingerprints cannot be compared;
- duplicate or unknown Candidate IDs fail;
- Hybrid/LTR/CE condensation yields the exact same 12 judged Candidate set.

### Provenance and leakage

- dataset hash/version mismatch fails;
- model artifact or feature order/fingerprint mismatch fails;
- CE snapshot/text-contract mismatch fails;
- Test without `--allow-test` fails;
- Test with a changed strategy/metric/slice/report freeze fingerprint fails;
- Dev and Test query IDs cannot coexist in one run;
- output and manifest fingerprints are stable over canonical serialization.

### Review, explanation, and immutability

- a truncated Phase 10 export is rejected;
- Feedback, SystemSignal, BadCase, completed action, or `VERIFIED` used as
  evaluation truth fails validation;
- cross-owner or unsupported explanation references fail;
- explanation evaluation cannot mutate ranking and detects a changed result
  fingerprint;
- artifact overwrite fails;
- a partial run cannot become `COMPLETED`;
- empty required output cannot look like success.

RED must be observed before implementation for each new behavior. Reference
metric tests use hand-calculated fixtures independent of the production
implementation. Integration tests use disposable infrastructure only when a
strategy adapter actually requires PostgreSQL/Qdrant; pure metric/artifact tests
need neither.

## Implementation Acceptance Gate

Phase 11 implementation is complete only when all of the following evidence is
fresh and recorded:

1. The protocol, metric semantics, candidate-pool cohorts, strategy roles,
   slice registry, report template, and Test guard are frozen.
2. Pure metric reference tests and all adversarial unjudged/pairwise/tie/empty
   cases pass.
3. Candidate-pool comparability and per-query provenance are enforced, not only
   documented.
4. Dataset/model/feature/retrieval/CE hashes and contract versions validate
   before execution.
5. Artifact JSON Schema, canonical fingerprints, immutable finalization, and
   failure states pass tests.
6. The Test guard and freeze-fingerprint checks pass attack tests.
7. Two identical clean Dev runs reproduce exact strategy orders, quality
   metrics, exclusions, and `quality_result_fingerprint`.
8. A Dev evaluation completes before any formal Test run; no Test tuning occurs.
9. Formal Test executes only after the full freeze gate and retains the Phase 4
   post-exposure caveat.
10. Historical Phase 4/6/7 reports and Phase 8–10 production behavior/artifacts
    remain byte-for-byte or Git-diff unchanged.
11. Reports include per-query results, exclusions, limitations, and the exact
    claim boundary even when a frozen strategy degrades.
12. Focused evaluation tests and the full relevant backend regression pass.
    PostgreSQL/Qdrant tests are required only for adapters that use them and run
    against explicitly disposable state.
13. Frontend verification is not required unless a later authorized scope adds
    frontend behavior. If it does, align the environment with README's Node 22
    LTS prerequisite before claiming verification; the current Node 20.13.1
    observation is not an architecture blocker.

The gate forbids implementation completion claims based on skipped integration
tests, Test-selected metrics, overwritten artifacts, or presentation-only
reports without reproducibility data.

## Architecture Freeze Review

The design was reviewed against these failure modes:

| Review question | Frozen control |
|---|---|
| Can Test influence design or selection? | Explicit freeze gate, `--allow-test`, fingerprints, Dev-only leader selection. |
| Can unjudged become negative? | Full-ranking retrieval policy, judged condensation for R2, Precision rejection. |
| Can Feedback or `VERIFIED` become truth? | Truth-source allowlist and hard validation failure. |
| Can different pools be called a model comparison? | Named R1/R2/R3 cohorts and mandatory pool fingerprints. |
| Can post-exposure Test appear pristine? | Mandatory manifest/report exposure flag and claim wording. |
| Can Precision become the headline? | Standard and conditional Precision excluded from v1. |
| Can explanation quality alter ranking quality? | Separate evaluation unit, fields, artifacts, and report section. |
| Can latency select a quality winner? | Separate artifact and selection prohibition. |
| Can provenance be omitted? | Completion requires dataset/strategy/pool/model/feature/source fingerprints. |
| Can history be overwritten? | New run directory, atomic finalization, overwrite failure. |
| Can a failure look like zero or success? | Explicit `FAILED`/`INVALID`; required metric and eligible-query gates. |
| Can the report imply production evidence? | Metric-to-claim matrix and mandatory limitations. |

No architecture blocker remains. The protocol is ready for a separately
authorized RED-first implementation phase. No Phase 11 executable behavior or
formal evaluation is authorized by this document alone.
