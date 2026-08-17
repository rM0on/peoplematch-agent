# Phase 6 Learning-to-Rank

## Status and scope

Phase 6 introduces one deterministic LightGBM LambdaMART baseline over the
frozen Phase 5 `FeatureVector`. The implementation is local and synthetic;
it is approved for Phase 6 closeout. It does not change Phase 5 feature
semantics, Phase 4 retrieval, the frozen dataset, labels, or query splits.

The canonical query is a Job and the documents are Candidates. Phase 6 v1
supports Job → Candidates only. Candidate → Jobs remains a Phase 4/5
inspection capability and is not claimed to be validated by this ranker.

## Dependency and model contract

The native project runtime is Python 3.9.13 and the backend image uses Python
3.11 with the same pinned dependency. LightGBM 4.7.0 requires Python
3.10 or newer, so the latest compatible pinned release is `lightgbm==4.6.0`.
The compatibility probe passes for `lambdarank`, `rank_xendcg`, `label_gain`,
`lambdarank_truncation_level`, `deterministic`, and `force_row_wise`.
`rank_xendcg` is capability-only and is not a second Phase 6 model.

The ranker contract is:

- `ranker_version`: `ltr_ranker_v1`;
- objective: `lambdarank` with graded labels `0/1/2/3`;
- metric: `ndcg`;
- label gain: `[0, 1, 3, 7]`;
- CPU deterministic training, one thread, seed `42`, 100 rounds;
- Phase 5 feature version: `feature_schema_v1`;
- Phase 5 feature fingerprint:
  `dc85c7237c6c67785199d221c919ae48c31c9a6323857070e6399d3eae365e42`.

The model matrix contains exactly, and only, this order:

1. `semantic_score`
2. `sparse_score`
3. `skill_fit_score`
4. `project_evidence_score`
5. `role_direction_score`
6. `ai_tool_score`
7. `location_score`
8. `seniority_score`
9. `missing_penalty`
10. `overclaim_penalty`

Nullable Phase 5 values are passed as `NaN` and handled by LightGBM's native
missing-value behavior. IDs, retrieval ranks, dense/sparse ranks, fusion
score, diagnostics, labels, split names, pairwise metadata, hard negatives,
archetype, and raw profile/project/evidence text are offline metadata or
diagnostics only and never model columns.

## Derived dataset and training boundary

`data/eval/phase6/ltr_dataset_v1.json` is a deterministic derived artifact
containing only explicit judged Train and Dev pairs. The frozen Hybrid
retrieval + Phase 5 feature path is called with `top_k=48`, then labels are
joined by `(job_id, candidate_id)`:

- Train: 14 Jobs, 168 rows, 14 groups of 12;
- Dev: 5 Jobs, 60 rows, 5 groups of 12;
- Test: no rows and never used.

Unjudged pairs are excluded, not converted to grade 0. Pairwise preferences
are used only for Dev diagnostics. Hard-negative annotations remain
descriptive and are not features, weights, or implicit labels.

Offline modules may read frozen labels and split metadata. Runtime ranking
imports only retrieval, the Phase 5 feature service, the ranker contract, and
the validated native model artifact. The loader fails closed on missing
artifacts, stale SHA-256, LightGBM/version mismatch, feature version/fingerprint
mismatch, or feature-order mismatch.

## Runtime API

`POST /api/v1/ranking/jobs/{job_id}/candidates` performs one Hybrid retrieval
call, extracts the frozen ten-feature vector, scores that pool, and returns
the requested top results. The request distinguishes `candidate_pool_k` from
`top_k` and enforces `1 <= top_k <= candidate_pool_k <= 50`.

Results expose `entity_id`, `ltr_rank`, and `ltr_score_raw`, plus existing
retrieval and feature context and model/feature provenance. `ltr_score_raw`
is the raw LightGBM ranking score (model margin), not a probability,
calibrated percentage, or final production match score. Ordering is score
descending, then original retrieval rank ascending, then entity ID ascending.
Retrieval rank is only a deterministic tie-break and is never passed to the
model. No Candidate → Jobs LTR endpoint, explanation, Cross-Encoder, or
`final_match_score` is implemented.

## Dev evaluation

`data/eval/phase6/ltr_dev_report_v1.json` is explicitly a
`judged_set_reranking` evaluation, not end-to-end retrieval accuracy. For
each Dev Job it keeps explicitly judged Candidates only and compares the
frozen Hybrid relative order with the LTR order using NDCG@5, NDCG@10, and
MRR with relevance threshold `>= 2`; gain is `2^relevance - 1`. Pairwise
accuracy uses only explicit Dev pairwise preferences, with ties scored as
0.5. The report records incomplete judgments and `test_evaluated=false`.

The current synthetic report is descriptive evidence for this fixed sandbox,
not a production hiring-accuracy claim or a guaranteed improvement claim.
The historical Phase 4 post-exposure fixed synthetic benchmark and Dense
truncation limitation remain unchanged. There are no real users, QPS/DAU,
online experiments, or real LLM provider in this phase.

## Reproduction and artifacts

From the repository root (PowerShell):

```powershell
& .\backend\.venv\Scripts\python.exe scripts\build_ltr_dataset.py --api-url http://127.0.0.1:8000
& .\backend\.venv\Scripts\python.exe scripts\train_ltr.py --write
& .\backend\.venv\Scripts\python.exe scripts\check_ltr_artifacts.py
```

The dataset, model metadata, and Dev report are tracked under
`data/eval/phase6/`. The native model is generated at
`artifacts/phase6/ltr_ranker_v1.txt`; repository policy ignores `artifacts/`,
so it is reproduced locally rather than committed. Metadata records the model
SHA-256, Python/LightGBM versions, parameters, groups, labels, source
fingerprints, and explicit absence of Test usage.

The normal artifact check is strict: it requires the ignored native model and
verifies its SHA-256. Metadata-only inspection is an explicitly separate mode:

```powershell
& .\backend\.venv\Scripts\python.exe scripts\check_ltr_artifacts.py --metadata-only
```

That mode is not runtime-ready and must not be used as the final closeout gate.

## Fresh-clone and Docker sequence

A fresh clone does not contain the ignored native model, so the ranking API is
not runtime-ready until the local model has been generated. The deterministic
sequence is:

1. Install `backend\requirements.txt` in the Python 3.9.13 native environment.
2. Start the local PostgreSQL/Qdrant prerequisites and a current-source backend
   with the seeded synthetic profiles available.
3. Build the Train/Dev artifact through the existing Feature API:

   ```powershell
   & .\backend\.venv\Scripts\python.exe scripts\build_ltr_dataset.py --api-url http://127.0.0.1:8000 --write
   ```

4. Train the local ignored native model and write metadata/report:

   ```powershell
   & .\backend\.venv\Scripts\python.exe scripts\train_ltr.py --write
   ```

5. Run the strict model-required artifact check:

   ```powershell
   & .\backend\.venv\Scripts\python.exe scripts\check_ltr_artifacts.py
   ```

6. Rebuild/start the Compose stack. The backend receives explicit container
   paths through `RANKING_MODEL_PATH` and `RANKING_MODEL_METADATA_PATH`; Compose
   mounts the generated model directory and tracked Phase 6 metadata directory
   read-only at `/app/artifacts` and `/app/data/eval/phase6`.

The native repository defaults remain available for non-Docker execution, but
Docker does not infer them from package-file parent counts. If the generated
model is absent, the ranking dependency fails closed with a typed
`ranking_model_unavailable` error; metadata-only verification does not claim
runtime readiness.

Known limitations are intentional: synthetic labels and judged-set metrics
are incomplete and local; `ai_tool_score` is constant zero in the current
Train/Dev audit; semantic and sparse channels were unavailable in the
profile-only Phase 5 audit; experience requirements are not modeled by the
three capability/evidence features; and no production hiring or business
impact claim is made.
