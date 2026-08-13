# PeopleMatch Sandbox Dataset

This directory contains **synthetic sandbox data** for PeopleMatch Agent Phase 1. It is an engineering fixture for later local extraction, retrieval, ranking, and evaluation work; it is not a representation of a real hiring market.

## Versions and provenance

- Dataset version: `1.0.0`
- Canonical schema version: `1.0`
- Record origin: `synthetic_sandbox`
- Label annotation source: `synthetic_curated`
- Split policy: grouped by job query

The relevance and pairwise labels were constructed for this sandbox and have not received independent annotator review. Their provenance must remain `synthetic_curated`.

## Files

| Path | Purpose |
|---|---|
| `samples/candidates.jsonl` | 48 canonical candidate profiles with claims, projects, and evidence kept separate |
| `samples/jobs.jsonl` | 24 canonical fictional job profiles with typed requirements and constraints |
| `samples/labels.jsonl` | Job-to-candidate relevance grades and data-level mismatch reasons |
| `eval/pairwise_preferences.jsonl` | Explicit winner/loser judgments for future ranking diagnostics |
| `eval/query_splits.json` | Fixed 14/5/5 train/dev/test job-query split |
| `eval/dataset_stats.json` | Descriptive dataset counts only; no model or ranking metrics |
| `eval/dataset_freeze_manifest.json` | Dataset `1.0.0` canonical-file hashes and frozen query IDs |
| `schemas/*.schema.json` | Deterministic exports from the canonical Pydantic v2 models |
| `seed/manifest.json` | Hashes and versions for later Phase 2 consumption |

Every JSONL file is UTF-8, contains one JSON object per non-empty line, and has no comments.

## Validate the frozen baseline (PowerShell)

Run from the repository root with the backend virtual environment:

```powershell
& .\backend\.venv\Scripts\python.exe scripts\export_json_schemas.py
& .\backend\.venv\Scripts\python.exe scripts\validate_dataset.py
& .\backend\.venv\Scripts\python.exe scripts\dataset_stats.py
& .\backend\.venv\Scripts\python.exe scripts\prepare_seed_bundle.py
& .\backend\.venv\Scripts\python.exe scripts\freeze_dataset.py
```

Pydantic models under `backend/app/schemas/` are the contract source of truth; exported JSON Schema files must not be edited by hand. The Phase 1 generator remains available for provenance, but must not be run to tune or silently replace the frozen `1.0.0` records.

## Split and leakage policy

The unit of splitting is a job query, not a candidate pair. All relevance labels and pairwise preferences for one `job_id` remain in exactly one of `train`, `dev`, or `test`. This prevents the same query and its judgments from appearing in multiple splits.

The test jobs `job_020` through `job_024` are frozen. A later annotation correction requires a documented reason, a dataset-version increment, a regenerated freeze manifest, and re-reporting of affected experiments; labels must never be adjusted because a model performs poorly.

## Privacy and integrity

- Candidate names are identifiers such as `Candidate 001`; companies are fictional.
- Artifact references use `sandbox://`; profile URLs use `example.invalid`.
- No resume, personal email, phone number, address, private repository, or employer record is included.
- Raw profiles do not contain relevance grades, expected ranks, hard-negative flags, or match scores.
- The dataset contains no Recall, NDCG, MRR, latency, business-impact, or online-experiment result.

## Limitations

The catalog intentionally oversamples ambiguous and difficult AI-role matching cases. Its archetype mix, city coverage, seniority distribution, and written evidence style are designed for local engineering tests and do not estimate real-world candidate or job distributions. Because labels are `synthetic_curated`, future offline metrics describe only performance on this fixed sandbox set, not real hiring accuracy, production improvement, user impact, or online lift. Labels and later feature signals share evidence, direction, and constraint concepts, so results support engineering comparison and pipeline debugging rather than real-world effectiveness claims.

Database insertion is explicitly deferred to Phase 2. The Phase 1 seed manifest prepares files and hashes only; it does not connect to PostgreSQL or claim a successful database seed.
