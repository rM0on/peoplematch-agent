# Phase 4 Retrieval Evaluation

## Benchmark

The evaluation uses frozen dataset `1.0.0` and schema `1.0`: 48 Candidates, 24 Jobs, 288 graded job-to-candidate judgments, and the fixed job-query splits. The current v4 results are a **post-exposure fixed synthetic sandbox benchmark**.

The matrix is incomplete: 288 of 1,152 possible Candidate/Job pairs are judged, exactly 12 judgments per Job. Recall@K uses judged-relevant Candidates only in its denominator. Unlabeled Candidates are not explicit negatives and are not included in that denominator, although they can occupy Top-K positions. Consequently Phase 4 does not report Precision@K or NDCG.

## Relevance Semantics

The threshold was fixed before test evaluation from the existing labeling guidelines:

- Grade 3 is a strong match.
- Grade 2 is a plausible match with credible direct or adjacent evidence and an explicit gap.
- Grades 0 and 1 are non-match or weak/misleading pairs.

Therefore retrieval-relevant means `relevance_grade >= 2`. This is appropriate for a recall stage, which should retain both strong and plausible Candidates for later ranking.

## Metrics

- Recall@5, Recall@10, Recall@20 over each query's judged relevant Candidates
- HitRate@5 and HitRate@10
- MRR@20 as a retrieval-position diagnostic over the retrieved Top-20 only, not an LTR evaluation

Metrics are macro-averaged across Job queries. Dense, Sparse, and Hybrid use identical query sets, corpus documents, relevance threshold, K values, and default `filters = null`.

## Dev/Test Protocol and Seal

For v4 itself, final parameters and document fields were sealed after the v4 dev run, and no algorithm or configuration was tuned after viewing the v4 test metrics. This is a **v4-internal seal only**; it does not mean the fixed test queries were previously unseen. The deterministic configuration fingerprint is:

```text
b004bc52c33f3e15bf38dba1777305039909bb5229261dcf1851b289e7c8f2e7
```

The sealed configuration is:

- document version `retrieval_doc_v4` and the fields listed in `retrieval-design.md`; dynamically derived full/base/variant project-name construction signals are removed from all Candidate text
- `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions
- BM25 `k1=1.5`, `b=0.75`
- RRF `k=60`, dense/sparse weights `1.0/1.0`
- channel pool `min(eligible corpus, max(20, top_k * 3))`
- no default metadata filter
- relevance threshold Grade >=2
- K values 5, 10, and 20

Within the v4 experiment, only after writing the v4 dev artifact and fingerprint was the fixed test split (`job_020` through `job_024`) evaluated. No algorithm, field, model, parameter, threshold, or fusion weight was changed after the v4 test results were inspected.

## Test Exposure History

The fixed test queries are `job_020`, `job_021`, `job_022`, `job_023`, and `job_024`. Artifact history records the following exposure:

| Experiment | Test split status | Subsequent action |
|---|---|---|
| `retrieval_doc_v1` | Exposed | Invalidated because direct project names carried synthetic family/variant construction signals. |
| `retrieval_doc_v2` | Exposed | Invalidated because evidence statements still repeated owned construction names. |
| `retrieval_doc_v3` | Exposed | Invalidated because summaries still contained derived base/variant construction phrases. |
| `retrieval_doc_v4` | Current fixed benchmark | Full/base/variant project-name signals are removed across Candidate semantic text. |

The v1-v3 document changes were motivated by construction-artifact and leakage-boundary review. The historical metrics do not show deliberate monotonic optimization, and no v4 parameter was changed after its own test run. Nevertheless, test results were visible before subsequent document and dense tie-policy changes, so evaluation independence cannot be proven. V4 is **not a pristine held-out estimate** and must not be described as untouched, first-time held-out, or an unbiased estimate of unseen-query generalization.

The current v4 test metrics remain useful as a fixed post-exposure sandbox comparison. A new dataset/evaluation version with previously unseen queries is required for a truly pristine held-out estimate; Phase 4 does not create that dataset.

This evaluation test exposure is distinct from runtime label leakage. Runtime retrieval has no label leakage: `RetrievalService` does not consume relevance labels, grades, pairwise outcomes, hard-negative metadata, or query splits.

## Dense Input Truncation

The real dense model is `sentence-transformers/all-MiniLM-L6-v2`; its audited model/tokenizer maximum sequence length is 256. Current v4 source-document token counts are:

| Corpus | Minimum tokens | Maximum tokens | Exceeding 256 |
|---|---:|---:|---:|
| Candidates | 317 | 452 | 48 / 48 |
| Jobs | 256 | 284 | 23 / 24 |

Dense therefore consumes a tokenizer-truncated prefix. Sparse BM25 consumes the full retrieval document. Later Candidate sections such as evidence statements and AI tools may be partially or fully absent from dense encoding. Dense and Sparse share the same source `RetrievalDocument` contract, but they do not consume exactly the same effective semantic content. The reported Dense and Hybrid metrics represent this actual baseline; no truncation repair or performance tuning is part of Phase 4 closeout.

Possible future experiments include section-aware dense encoding, chunked embeddings, multi-vector retrieval, pooling across section or chunk embeddings, and a reviewed longer-context embedding model. Each would require a new retrieval experiment/version and must not be tuned against the already exposed Phase 4 test split.

## Results

### Dev (`job_015`–`job_019`)

| Strategy | Recall@5 | Recall@10 | Recall@20 | HitRate@5 | HitRate@10 | MRR@20 |
|---|---:|---:|---:|---:|---:|---:|
| Dense | 0.22 | 0.40 | 0.70 | 0.40 | 0.80 | 0.453333 |
| Sparse | 0.68 | 0.77 | 0.86 | 1.00 | 1.00 | 0.766667 |
| Hybrid RRF | 0.40 | 0.66 | 0.85 | 0.80 | 0.80 | 0.666667 |

### Test (`job_020`–`job_024`)

| Strategy | Recall@5 | Recall@10 | Recall@20 | HitRate@5 | HitRate@10 | MRR@20 |
|---|---:|---:|---:|---:|---:|---:|
| Dense | 0.42 | 0.42 | 0.70 | 0.80 | 0.80 | 0.477778 |
| Sparse | 0.67 | 0.80 | 0.95 | 1.00 | 1.00 | 0.866667 |
| Hybrid RRF | 0.47 | 0.66 | 0.90 | 0.80 | 1.00 | 0.728571 |

Sparse outperformed equal-weight Hybrid at all reported Recall K values on this fixed synthetic sandbox. Plausible technical context includes strong lexical overlap in the synthetic corpus, MiniLM dense-input truncation at 256 tokens, and equal-weight RRF combining the weaker dense channel with sparse retrieval. These observations do not prove truncation or any single factor caused the result. The metrics are retained without changing RRF weights or otherwise tuning Hybrid, and they do not imply real hiring accuracy, production recall, recruiter impact, or business lift.

## Isolation and Corpus Integrity

Only `backend/app/services/retrieval/evaluation.py` and the evaluation CLI read labels/splits. Runtime retrieval accepts no label object and emits no grade/relevance field. Evaluation hard-fails unless the PostgreSQL Candidate ID set exactly equals the frozen 48-Candidate corpus and query IDs belong to the frozen Job corpus; it does not silently filter `user_created` or `mock_parsed` records.

## Hard-Negative Policy

Hard-negative metadata is not used in runtime retrieval. A separate aggregate hard-negative diagnostic was not implemented in this baseline report; no hard-negative metric is claimed.

## Reproduction

Build fresh real-model indexes, run dev to create the seal, then run test once:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://peoplematch:peoplematch_local@localhost:5432/peoplematch"
$env:QDRANT_URL = "http://localhost:6333"
& .\backend\.venv\Scripts\python.exe scripts\build_retrieval_index.py --entity all
& .\backend\.venv\Scripts\python.exe scripts\evaluate_retrieval.py --split dev
& .\backend\.venv\Scripts\python.exe scripts\evaluate_retrieval.py --split test
```

The test command is intentionally single-use for a sealed artifact: rerunning test, or rerunning dev over a report that already contains test metrics, hard-fails before model/index queries execute.

The active deterministic review-tree artifact is `data/eval/phase4_retrieval_report_v4.json`. Its seal is scoped to v4 and records `pristine_held_out = false` plus the exposed predecessor versions. Earlier v1-v3 reports are explicitly invalidated audit history from progressively tightening the frozen project construction-signal guard. Artifacts exclude volatile timestamps, local paths, timing measurements, and secrets.
