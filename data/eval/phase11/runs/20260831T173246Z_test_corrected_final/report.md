# Phase 11 Offline Evaluation — Test

Protocol: `phase11_eval_protocol_v1`
Metric semantics: `phase11_metric_semantics_v1`

This report is descriptive evidence on synthetic sandbox judgments. It is not production, hiring-accuracy, or generalization evidence.

## R1 Retrieval

- dense_v4: Recall@5=0.420000, Recall@10=0.420000, Recall@20=0.700000
- sparse_bm25_v4: Recall@5=0.670000, Recall@10=0.800000, Recall@20=0.950000
- hybrid_rrf_v4: Recall@5=0.470000, Recall@10=0.660000, Recall@20=0.900000

Predeclared Dev leader: sparse_bm25_v4
Observed Test ordering: sparse_bm25_v4; no reselection.

## R2 Controlled Ranking

- hybrid_rrf_v4: NDCG@5=0.792028, NDCG@10=0.834257, MRR@10=0.900000, pairwise=0.800000
- ltr_ranker_v1: NDCG@5=0.959290, NDCG@10=0.959723, MRR@10=1.000000, pairwise=1.000000
- cross_encoder_experiment: NDCG@5=0.899127, NDCG@10=0.921153, MRR@10=1.000000, pairwise=0.900000

Predeclared Dev leader: ltr_ranker_v1
Observed Test ordering: ltr_ranker_v1; no reselection.

## Boundaries

- Standard Precision@K: rejected under incomplete judgments.
- Explanation diagnostics: NOT RUN; no frozen persisted Test ExplanationRun input set is registered.
- Phase 10 review diagnostics: NOT RUN; review exports are diagnostic-only and not relevance truth.
- Formal Test: EXECUTED under frozen seal; access reason=final.
- Phase 4 Test queries were previously exposed; this is a post-exposure fixed synthetic sandbox evaluation, not a pristine held-out, unseen-query generalization, selection-independent, or real-world validation claim.
