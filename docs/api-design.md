# API Design

## Conventions

- Base URL in local development: `http://localhost:8000`
- Implemented versioned prefix: `/api/v1`
- Liveness remains unversioned at `/health`.
- All implemented responses use `success`, `data`, `error`, and `request_id`.
- `X-Request-ID` is propagated when supplied and generated otherwise.
- `Planned` endpoints are documentation only; they do not return fake data.

## Endpoint Inventory

| Method | Path | Status | Intended responsibility |
|---|---|---|---|
| GET | `/health` | **Implemented** | Application liveness; no downstream readiness checks |
| POST | `/api/v1/candidates/parse` | **Implemented** | Validate a deterministic mock candidate extraction preview and optionally persist it |
| GET | `/api/v1/candidates` | **Implemented** | List stored candidate profiles with pagination and structured filters |
| GET | `/api/v1/candidates/{candidate_id}` | **Implemented** | Read one canonical candidate profile, projects, and evidence |
| POST | `/api/v1/candidates` | **Implemented** | Create a validated `user_created` candidate with a server-generated ID |
| PATCH | `/api/v1/candidates/{candidate_id}` | **Implemented** | Partially update a mutable profile, then validate the complete result |
| DELETE | `/api/v1/candidates/{candidate_id}` | **Implemented** | Delete a mutable profile and its nested records |
| POST | `/api/v1/jobs/parse` | **Implemented** | Validate a deterministic mock job extraction preview and optionally persist it |
| GET | `/api/v1/jobs` | **Implemented** | List stored job profiles with pagination and structured filters |
| GET | `/api/v1/jobs/{job_id}` | **Implemented** | Read one canonical job profile and its requirements |
| POST | `/api/v1/jobs` | **Implemented** | Create a validated `user_created` job with a server-generated ID |
| PATCH | `/api/v1/jobs/{job_id}` | **Implemented** | Partially update a mutable job, then validate the complete result |
| DELETE | `/api/v1/jobs/{job_id}` | **Implemented** | Delete a mutable job and its requirements |
| POST | `/api/v1/retrieval/jobs/{job_id}/candidates` | **Implemented / Phase 4 Completed** | Retrieve a first-stage Candidate recall set for one stored Job |
| POST | `/api/v1/retrieval/candidates/{candidate_id}/jobs` | **Implemented / Phase 4 Completed** | Retrieve a first-stage Job recall set for one stored Candidate |
| POST | `/api/v1/features/jobs/{job_id}/candidates` | **Implemented / Phase 5 Completed / Frozen** | Preserve Job-to-Candidate retrieval order and attach versioned pair features |
| POST | `/api/v1/features/candidates/{candidate_id}/jobs` | **Implemented / Phase 5 Completed / Frozen** | Preserve Candidate-to-Job retrieval order and attach versioned pair features |
| POST | `/api/v1/ranking/jobs/{job_id}/candidates` | **Implemented / Phase 6 PASS / FROZEN** | Rerank one Hybrid Candidate pool with the deterministic LambdaMART baseline |
| POST | `/api/v1/reranking/jobs/{job_id}/candidates` | **Implemented / Phase 7 PASS / FROZEN / Optional experimental comparison** | Apply the pinned frozen Cross-Encoder to the Phase 6 LTR shortlist (Job → Candidates only); Phase 6 remains the stronger current synthetic Dev baseline |
| POST | `/api/v1/match/retrieve` | **Planned** | Run retrieval for an explicit candidate/job query |
| POST | `/api/v1/match/score` | **Planned** | Compute versioned evidence-aware features |
| POST | `/api/v1/match/rerank` | **Planned** | Apply later ranking/reranking stages |
| POST | `/api/v1/match/explain` | **Planned** | Generate an explanation grounded in an existing ranking result |
| GET | `/api/v1/match/runs` | **Planned** | List traceable match runs |
| GET | `/api/v1/match/runs/{id}` | **Planned** | Read stage details for one match run |
| POST | `/api/v1/feedback` | **Planned** | Record explicit feedback linked to an immutable match run |
| GET | `/api/v1/bad-cases` | **Planned** | List bad cases and failure categories |
| GET | `/api/v1/bad-cases/{id}` | **Planned** | Inspect one attributed bad case |
| POST | `/api/v1/eval/run` | **Planned** | Start a sandbox offline evaluation |
| GET | `/api/v1/eval/runs` | **Planned** | List offline evaluation runs |
| GET | `/api/v1/eval/runs/{id}` | **Planned** | Read one run's documented configuration and results |

## Implemented Health Response

`GET /health` returns HTTP 200 when the FastAPI process can serve requests:

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "peoplematch-backend",
    "version": "0.1.0",
    "environment": "development"
  },
  "error": null,
  "request_id": "6a2f4a86-eae3-475c-80bf-c820de6f48ad"
}
```

This is liveness, not PostgreSQL/Redis/Qdrant readiness.

## Profile APIs

Candidate and job responses preserve the Phase 1 canonical fields and add two persistence provenance fields: nullable `dataset_version` and nullable dataset-only `archetype`. Imported baseline records have `data_origin=synthetic_sandbox` and `dataset_version=1.0.0`. API-created records have `data_origin=user_created`, no dataset version, and IDs generated as `cand_usr_<uuid>` or `job_usr_<uuid>`.

List endpoints return `data.items`, `data.total`, `data.limit`, and `data.offset`. `limit` defaults to 20 and is bounded to 1–100; `offset` defaults to 0.

Candidate filters:

- `seniority`: exact structured seniority value;
- `city`: city contained in `preferred_locations.cities`;
- `target_role`: exact value contained in `target_roles`.

Job filters:

- `role_title`: case-insensitive substring;
- `role_direction`: exact array member;
- `city`: city contained in `location.cities`;
- `seniority`: exact value contained in `seniority_requirement`.

PATCH uses replacement semantics for each supplied nested collection; omitted nested fields or requirement groups remain unchanged. Candidate project replacement preserves omitted evidence only when all existing references remain valid. Coordinated project/evidence replacement is atomic, and the merged complete domain record is validated before persistence. Every successful scalar or nested PATCH advances the parent profile's `updated_at`. Deletion cascades from a profile to its normalized nested rows.

Canonical project and evidence IDs are unique within their candidate owner, and canonical requirement IDs are unique within their job owner. Different owners may reuse them. Internal database surrogate IDs are persistence-only and never appear in API records.

Candidate GitHub URL policy is origin-aware. `synthetic_sandbox` and `mock_parsed` records accept only `sandbox://` or valid HTTP(S) references whose hostname is exactly `example.invalid`; `user_created` and future `llm_parsed` records may use `None` or a valid HTTP(S) URL. Mutation clients cannot provide `data_origin`, `dataset_version`, or `archetype`; manual POST assigns `user_created`, a null dataset version, and a null archetype.

## Structured Extraction APIs

`POST /api/v1/candidates/parse` and `POST /api/v1/jobs/parse` accept typed `{ "text": string, "persist": boolean }` requests. `persist` defaults to `false`, so parsing is a zero-write preview unless the caller opts in. Clients cannot select a provider or provide identity, source-copy, origin, dataset-version, schema-version, or archetype fields.

Successful `data` contains:

- `draft`: the validated domain-specific extraction draft;
- `record`: `null` for preview or the persisted canonical record;
- `extraction`: `provider`, `provider_kind`, `attempts`, `repaired`, `persisted`, and a SHA-256 `input_fingerprint`.

Phase 3 implements only the deterministic mock provider and only registered synthetic fixture inputs. A persisted mock draft receives a server-generated `cand_parse_<uuid>` or `job_parse_<uuid>`, the exact request source, `data_origin=mock_parsed`, `schema_version=1.0`, and null dataset version/archetype. Manual POST behavior remains `user_created`. Mock records are mutable because they are not part of frozen dataset `1.0.0`.

Provider output is decoded with strict `json.loads` and validated against Pydantic drafts that reuse the canonical nested contracts. Invalid JSON or schema/domain output receives at most one repair attempt. Repeated invalid output returns HTTP 502 `provider_output_invalid`; provider exceptions and timeouts return HTTP 503 `provider_unavailable` or `provider_timeout`; an unknown mock input returns HTTP 422 `mock_input_not_supported`. No raw provider response, prompt, source, stack trace, or database detail appears in an error response.

## Hybrid Retrieval APIs

`POST /api/v1/retrieval/jobs/{job_id}/candidates` and `POST /api/v1/retrieval/candidates/{candidate_id}/jobs` accept a strict request:

```json
{
  "strategy": "hybrid",
  "top_k": 10,
  "filters": {
    "cities": ["Shanghai"],
    "seniorities": ["mid"]
  }
}
```

`strategy` is `dense`, `sparse`, or `hybrid`; default is `hybrid`. `top_k` defaults to 10 and is bounded to 1–50. Filters are optional and explicit-only. Job-to-Candidate filters compare Candidate preferred cities and Candidate seniority; Candidate-to-Job filters compare Job cities and accepted seniorities. Callers cannot select collection names, providers/models, RRF parameters, provenance, archetypes, dataset versions, splits, labels, or grades.

Each result contains entity ID, rank, matched channels, nullable dense rank/score, nullable sparse rank/score, and nullable RRF fusion score. These are retrieval diagnostics, not a final match score. Responses never contain embedding vectors, labels, feature scores, or explanation text.

Diagnostics include query/result type, query ID, strategy, requested/returned counts, corpus/eligible counts, channel pool sizes, server-owned embedding provider/model, document version, RRF k, whether filters were applied, index freshness state, and local stage timings. Timings are development diagnostics, not a production latency SLA.

Dense and hybrid requests require an explicitly built, fresh Qdrant index. Missing collections return HTTP 503 `retrieval_index_missing`; mismatched dimensions/entity sets/document fingerprints return HTTP 409 `retrieval_index_stale`; embedding-model failures return HTTP 503 `embedding_provider_unavailable`; Qdrant failures return HTTP 503 `vector_store_unavailable`. A missing query profile uses the existing HTTP 404 `profile_not_found` contract. Raw model/Qdrant exceptions are not returned.

These endpoints perform first-stage recall only. They do not compute skill fit, evidence fit, location/seniority scores, penalties, final ordering, LTR, or Cross-Encoder output.

## Feature Engineering APIs

`POST /api/v1/features/jobs/{job_id}/candidates` and `POST /api/v1/features/candidates/{candidate_id}/jobs` accept the same strict `strategy`, `top_k`, and explicit `filters` request as retrieval. The server first calls the existing Phase 4 retrieval service and then batch-enriches each pair; it does not duplicate dense/BM25/RRF execution and never sorts by a feature.

Top-level `data` contains `feature_version`, `feature_fingerprint`, ordered `results`, and the unchanged retrieval diagnostics. Each result contains `entity_id`, the original retrieval result, a ten-field nullable `feature_vector`, and separate `feature_diagnostics`. `null` plus `availability=false` means unavailable and remains distinct from a real zero.

The current contract is `feature_schema_v1`. Runtime inputs exclude labels, splits, hard negatives, pairwise preferences, construction metadata, raw source, Candidate/company names, project names/summaries, and evidence statements. Dense/BM25 values are copied unchanged when their channel is present. Ranks and RRF remain diagnostics, not model features. Missing profiles and retrieval infrastructure failures keep their existing typed errors; invalid profile state and contract violations return `invalid_profile_state` and `feature_contract_violation` respectively.

These endpoints are inspection/enrichment only. They do not return a final match score, learned weight, LTR/Cross-Encoder output, feature-based rank, or explanation.

## Phase 6 Job-to-Candidates ranking API

`POST /api/v1/ranking/jobs/{job_id}/candidates` performs exactly one existing
Hybrid retrieval call with a bounded `candidate_pool_k`, reuses the frozen
Phase 5 `FeatureVector`, and applies the validated native `ltr_ranker_v1`
model within that pool. The request is:

```json
{
  "candidate_pool_k": 20,
  "top_k": 10,
  "filters": null
}
```

The server enforces `1 <= top_k <= candidate_pool_k <= 50` and does not accept
an alternative retrieval strategy. Results expose `entity_id`, `ltr_rank`,
`ltr_score_raw`, retrieval/feature context, `ranker_version`, model SHA-256,
the Phase 5 feature version/fingerprint, and `candidate_pool_k`. The raw score
is a LightGBM model margin, not a probability, percentage, or final match
score. Ties use original retrieval rank and then entity ID; retrieval rank is
not a model feature. Missing or stale model artifacts fail closed with typed
`ranking_model_unavailable` (503) or `ranking_contract_mismatch` (409)
errors. There is intentionally no Candidate-to-Jobs LTR or Cross-Encoder endpoint,
explanation, or Test-label access at runtime.

## Phase 7 Cross-Encoder reranking API

`POST /api/v1/reranking/jobs/{job_id}/candidates` is a sequential second-stage
operation. It calls the frozen Phase 6 ranking service with a retrieval pool and
an LTR shortlist, then scores that shortlist in one batch with the pinned local
Cross-Encoder. The request bounds are:

```json
{
  "retrieval_pool_k": 20,
  "cross_encoder_pool_k": 10,
  "top_k": 5,
  "filters": null
}
```

The final order is `cross_encoder_score_raw` descending, then LTR rank,
retrieval rank, and entity ID. The raw field is an identity-activation model
logit (`higher_is_better`), not a probability, confidence, match percentage, or
final match score. The response records model ID/revision/snapshot fingerprint,
text schema/fingerprint, pair order, pool sizes, and the Phase 4/5/6 provenance
for each returned Candidate; it does not return the serialized input text.

If the ignored local snapshot is absent, the Phase 7 dependency raises HTTP 503
`cross_encoder_model_unavailable`; a hash, revision, dependency, or text
contract mismatch fails closed with HTTP 409 `cross_encoder_contract_mismatch`.
Normal inference is local-only and does not require network access. This phase
does not fine-tune the model, evaluate Test Jobs, or generate explanations.

## Frozen Mutation Policy

Records imported from frozen dataset `1.0.0` are read-only through mutation APIs. PATCH or DELETE returns HTTP 409 with error code `frozen_record`. This prevents API activity from silently changing the fixed evaluation fixture. API-created records remain mutable and deletable.

## Error Envelope

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "not_found",
    "message": "Not Found",
    "details": null
  },
  "request_id": "caller-or-generated-id"
}
```

Phase 2 keeps consistent 400, 404, 409, 422, and 500 envelopes. Domain validation uses 400; missing profiles use 404; duplicate nested identifiers and frozen-record mutations use 409; transport/Pydantic input errors use 422. Raw database errors, stack traces, and connection strings are never returned.

## Future API Design Rules

- Parsing endpoints return structured output for review; they do not silently persist unless the phase contract says so.
- Ranking stages operate on versioned match runs and never use explanation text as an implicit score mutation.
- Mutating endpoints use typed inputs and explicit error codes.
- List endpoints define pagination before implementation.
- Evaluation endpoints identify dataset/configuration versions and never imply online impact.
- Each endpoint moves from `Planned` to `Implemented` only after code, tests, and documentation are present.
