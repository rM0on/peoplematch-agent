# API Design

## Conventions

- Base URL in local development: `http://localhost:8000`
- Planned versioned prefix: `/api/v1`
- Liveness remains unversioned at `/health`.
- All implemented responses use `success`, `data`, `error`, and `request_id`.
- `X-Request-ID` is propagated when supplied and generated otherwise.
- `Planned` endpoints are documentation only; they do not return fake data.

## Endpoint Inventory

| Method | Path | Status | Intended responsibility |
|---|---|---|---|
| GET | `/health` | **Implemented** | Application liveness; no downstream readiness checks |
| POST | `/api/v1/candidates/parse` | **Planned** | Parse candidate input into a structured reviewable profile |
| GET | `/api/v1/candidates` | **Planned** | List stored sandbox candidate profiles |
| GET | `/api/v1/candidates/{id}` | **Planned** | Read one candidate profile |
| POST | `/api/v1/jobs/parse` | **Planned** | Parse a job description into a structured reviewable profile |
| GET | `/api/v1/jobs` | **Planned** | List stored sandbox job profiles |
| GET | `/api/v1/jobs/{id}` | **Planned** | Read one job profile |
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

Phase 0 implements consistent 404, validation, and internal application-error envelopes. Internal exception messages are not exposed.

## Future API Design Rules

- Parsing endpoints return structured output for review; they do not silently persist unless the phase contract says so.
- Ranking stages operate on versioned match runs and never use explanation text as an implicit score mutation.
- Mutating endpoints use typed inputs and explicit error codes.
- List endpoints define pagination before implementation.
- Evaluation endpoints identify dataset/configuration versions and never imply online impact.
- Each endpoint moves from `Planned` to `Implemented` only after code, tests, and documentation are present.
