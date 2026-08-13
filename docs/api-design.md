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
| POST | `/api/v1/candidates/parse` | **Planned** | Parse candidate input into a structured reviewable profile |
| GET | `/api/v1/candidates` | **Implemented** | List stored candidate profiles with pagination and structured filters |
| GET | `/api/v1/candidates/{candidate_id}` | **Implemented** | Read one canonical candidate profile, projects, and evidence |
| POST | `/api/v1/candidates` | **Implemented** | Create a validated `user_created` candidate with a server-generated ID |
| PATCH | `/api/v1/candidates/{candidate_id}` | **Implemented** | Partially update a mutable profile, then validate the complete result |
| DELETE | `/api/v1/candidates/{candidate_id}` | **Implemented** | Delete a mutable profile and its nested records |
| POST | `/api/v1/jobs/parse` | **Planned** | Parse a job description into a structured reviewable profile |
| GET | `/api/v1/jobs` | **Implemented** | List stored job profiles with pagination and structured filters |
| GET | `/api/v1/jobs/{job_id}` | **Implemented** | Read one canonical job profile and its requirements |
| POST | `/api/v1/jobs` | **Implemented** | Create a validated `user_created` job with a server-generated ID |
| PATCH | `/api/v1/jobs/{job_id}` | **Implemented** | Partially update a mutable job, then validate the complete result |
| DELETE | `/api/v1/jobs/{job_id}` | **Implemented** | Delete a mutable job and its requirements |
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

Candidate GitHub URL policy is origin-aware. `synthetic_sandbox` records accept only `sandbox://` or `example.invalid` references; `user_created` and future `llm_parsed` records may use `None` or a valid HTTP(S) URL. Mutation clients cannot provide `data_origin`, `dataset_version`, or `archetype`; POST assigns `user_created`, a null dataset version, and a null archetype.

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
