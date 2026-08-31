# Phase 11 Offline Evaluation — Dev

Protocol: `phase11_eval_protocol_v1`
Metric semantics: `phase11_metric_semantics_v1`

This report is descriptive evidence on synthetic sandbox judgments. It is not production, hiring-accuracy, or generalization evidence.

## R1 Retrieval

- dense_v4: Recall@5=0.220000, Recall@10=0.400000, Recall@20=0.700000
- sparse_bm25_v4: Recall@5=0.680000, Recall@10=0.770000, Recall@20=0.860000
- hybrid_rrf_v4: Recall@5=0.400000, Recall@10=0.660000, Recall@20=0.850000

Leader by frozen rule: sparse_bm25_v4

## R2 Controlled Ranking

- hybrid_rrf_v4: NDCG@5=0.724505, NDCG@10=0.762206, MRR@10=0.800000, pairwise=0.600000
- ltr_ranker_v1: NDCG@5=0.970492, NDCG@10=0.970999, MRR@10=1.000000, pairwise=1.000000
- cross_encoder_experiment: NDCG@5=0.740569, NDCG@10=0.835568, MRR@10=1.000000, pairwise=0.700000

Leader by frozen rule: ltr_ranker_v1

## Boundaries

- Standard Precision@K: rejected under incomplete judgments.
- Explanation diagnostics: NOT RUN; no frozen persisted Dev ExplanationRun input set is registered.
- Phase 10 review diagnostics: NOT RUN; review exports are diagnostic-only and not relevance truth.
- Formal Test: SEALED / NOT RUN.
- Phase 4 Test is already exposed and can only support a post-exposure fixed synthetic sandbox benchmark.
