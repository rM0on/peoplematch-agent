# Phase 7 — Frozen Cross-Encoder Reranking

Phase 7 adds one frozen pretrained `cross-encoder/ms-marco-MiniLM-L6-v2` as a
second-stage semantic interaction reranker. It receives only the Phase 6
LambdaMART shortlist for the validated Job → Candidates direction. It does not
replace Phase 4 retrieval, Phase 5 features, or Phase 6 ranking, and it does
not generate explanations or a final hiring score.

## Runtime contract

`POST /api/v1/reranking/jobs/{job_id}/candidates` accepts:

```json
{
  "retrieval_pool_k": 20,
  "cross_encoder_pool_k": 10,
  "top_k": 5,
  "filters": null
}
```

The bounds are `1 <= top_k <= cross_encoder_pool_k <= retrieval_pool_k <= 50`.
The service calls the frozen Phase 6 `RankingService` with
`candidate_pool_k=retrieval_pool_k` and `top_k=cross_encoder_pool_k`, scores that
shortlist in one CPU batch, and sorts by raw CE logit descending. Ties use the
Phase 6 LTR rank, the Phase 4 retrieval rank, and then `entity_id`. There is no
weighted LTR/CE fusion.

Responses retain Phase 4/5/6 provenance and expose `cross_encoder_score_raw`,
which is an uncalibrated one-label sequence-classification logit. It is not a
probability, confidence, percentage, or final match score.

## Immutable model and text contract

The model revision is pinned to commit
`233902d25c440f23af6f7d6e94d2946bac0bee0a` under the Apache-2.0 license. The
ignored snapshot is prepared at
`artifacts/phase7/cross_encoder_ms_marco_minilm_l6_v2/` and is checked against
`data/eval/phase7/cross_encoder_model_manifest_v1.json`. Normal inference uses
`local_files_only=true` and `trust_remote_code=false`; the runtime does not
download from Hugging Face.

`cross_encoder_text_v1` serializes deterministic allowlisted structured fields
with pair order `text_a=Job`, `text_b=Candidate`. IDs, names, raw descriptions,
splits, labels, annotation metadata, project/evidence prose, and construction
metadata are excluded. Only `AVAILABLE` evidence skill names are emitted;
DESCRIBED and MISSING evidence never become positive evidence. The text policy
is fingerprinted in `cross_encoder_text_contract_v1.json`, and model loading
fails closed if it changes.

## Reproducibility and setup

Fresh setup is:

1. install `backend/requirements.txt`;
2. run `scripts/prepare_cross_encoder_model.py` (this is the explicit download
   step on a fresh machine);
3. run `scripts/check_cross_encoder_model.py` for the strict runtime check;
4. start/restart Compose so the ignored snapshot is available through the
   read-only `./artifacts:/app/artifacts:ro` mount.

An already-present snapshot may be reused without network access only with
`--reuse-existing`; that mode verifies the local files against the existing
manifest hashes and never regenerates expected hashes from the local bytes.

The model weights are not tracked. If the snapshot is absent, the backend and
Phase 4/5/6 routes can remain available, while the Phase 7 route returns typed
HTTP 503 `cross_encoder_model_unavailable`. A manifest/text/snapshot mismatch
returns typed HTTP 409 `cross_encoder_contract_mismatch`.

## Dev evaluation and limitations

`data/eval/phase7/cross_encoder_dev_report_v1.json` is titled
**CROSS-ENCODER JUDGED-SET DEV RERANKING EVALUATION**. It uses the same 60
explicitly judged pairs (12 per each of the five Dev Jobs) for the frozen LTR
ordering and CE ordering. Unjudged pairs are not treated as grade zero and no
Test Job is loaded, tokenized, scored, or used for a decision. Metrics are the
existing gain `2^relevance-1`, MRR threshold 2, and tie=0.5 pairwise accuracy.

The model is trained for MS MARCO passage ranking rather than Job/Candidate
matching and is not fine-tuned here. Phase 6 Dev MRR and pairwise accuracy are
already 1.0, so only NDCG@5 and NDCG@10 have aggregate headroom. A tie or
degradation is a valid result. `cross_encoder_latency_report_v1.json` reports
only local sandbox CPU timing; it is not a production latency, QPS, or capacity
claim. The frozen judged-set artifact does not carry a separate retrieval-rank
column, so offline CE ties use the canonical Phase 6 row order as the retrieval
rank fallback after LTR rank; the accepted 60-pair Dev run has no CE ties.
The accepted synthetic Dev result is a degradation relative to the frozen
LambdaMART baseline: LTR NDCG@5/NDCG@10 are
`0.9704922899797717`/`0.9709986829742865`, while Cross-Encoder
NDCG@5/NDCG@10 are `0.7405691758421714`/`0.8355679092477797`.
LambdaMART therefore remains the stronger current ranking baseline. Phase 7 is
an optional, experimental frozen semantic reranker retained for comparison;
it does not replace Phase 6. Explanations and Phase 8 orchestration remain
planned.
