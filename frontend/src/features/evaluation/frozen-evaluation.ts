// Read-only projection of data/eval/phase11/runs/20260831T173246Z_test_corrected_final/report.json.
// Its source hash and every displayed mean are checked against the frozen artifact in tests.
export const frozenEvaluation = {
  runId: "20260831T173246Z_test_corrected_final",
  sourceSha256: "d8dee5f63405cf4b108f34eaced5c102d07db798d0e8e281da885bc6a769f971",
  split: "test",
  jobs: 5,
  candidates: 48,
  judgments: 288,
  judgmentCoverage: 0.25,
  retrieval: [
    { id: "dense_v4", label: "Dense", recallAt10: 0.42000000000000004 },
    { id: "hybrid_rrf_v4", label: "Hybrid RRF", recallAt10: 0.6599999999999999 },
    { id: "sparse_bm25_v4", label: "Sparse BM25", recallAt10: 0.8 },
  ],
  ranking: [
    { id: "hybrid_rrf_v4", label: "Hybrid baseline", ndcgAt5: 0.7920277935456728, ndcgAt10: 0.8342569816166554, mrrAt10: 0.9, pairwise: 0.8, role: "召回基线" },
    { id: "ltr_ranker_v1", label: "LambdaMART", ndcgAt5: 0.9592897209091713, ndcgAt10: 0.9597225137750133, mrrAt10: 1, pairwise: 1, role: "默认排序" },
    { id: "cross_encoder_experiment", label: "Cross-Encoder", ndcgAt5: 0.8991273428238072, ndcgAt10: 0.9211525021159922, mrrAt10: 1, pairwise: 0.9, role: "实验，未采用" },
  ],
} as const;
