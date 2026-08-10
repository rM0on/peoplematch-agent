# PeopleMatch Agent Phase 0 Bootstrap Design

## Status

Approved for implementation by the user's Phase 0 specification on 2026-08-10.

## Objective

Create a local, maintainable monorepo foundation for PeopleMatch Agent without implementing any matching, ranking, LLM, retrieval, feedback, or evaluation business logic.

## Product boundary

PeopleMatch Agent is an autonomous, local-running prototype for evidence-aware AI Builder candidate/job matching. The eventual product must distinguish claimed skills from project evidence, separate semantic similarity from role-direction fit, account for constraints such as location and seniority, explain ranking evidence, and support bad-case review plus sandbox-only offline evaluation.

Phase 0 delivers only product documentation, engineering boundaries, a liveness endpoint, a minimal frontend shell, and local infrastructure configuration. Every future capability is documented as planned rather than represented by fake endpoints or sample results.

## Architecture

The repository is a monorepo with independent `backend`, `frontend`, `data`, `docs`, and `infra` areas. FastAPI exposes a typed `GET /health` liveness endpoint with a uniform response envelope and request ID propagation. Next.js renders a small server-independent product shell and a client-side system-status feature that makes a real request to the backend.

PostgreSQL, Redis, and Qdrant are provisioned by Docker Compose for future phases but are not used by Phase 0 business code. Alembic is wired to empty SQLAlchemy metadata without inventing domain tables. Future matching service directories are represented by a single boundary document instead of empty Python packages.

## Backend components

- `app.main`: application factory, metadata, middleware, CORS, routers, and exception handlers.
- `app.core.config`: cached Pydantic settings aligned with `.env.example`.
- `app.core.logging`: standard environment-aware Python logging.
- `app.api.router` and `app.api.routes.health`: HTTP routing and the liveness response.
- `app.middleware.request_id`: propagation or generation of `X-Request-ID` using request state.
- `app.schemas.common`: typed success/error envelopes.
- `app.models.base`: empty SQLAlchemy declarative metadata for future Alembic revisions.

Validation errors, unknown routes, and unexpected exceptions use the same envelope. The liveness endpoint does not depend on infrastructure readiness.

## Frontend components

- App Router layout/page and global Tailwind CSS.
- Presentational project overview and planned-module components.
- A feature-oriented `system-status` client component with loading, success, and failure states.
- A typed API client and health response types.

No metrics, recommendation records, charts, complete dashboard, or future product workflows are displayed.

## Data and error flow

The browser calls `${NEXT_PUBLIC_API_BASE_URL}/health`. The request ID middleware stores a supplied or generated identifier on `request.state`, then mirrors it into the response header. Route and error bodies read the same value. A failed frontend fetch is surfaced as `Unavailable`; it never falls back to a hard-coded healthy state.

## Testing and verification

Backend tests exercise health success, generated request IDs, propagated request IDs, 404 envelopes, and validation envelopes without external services. Frontend static quality gates are ESLint, `tsc --noEmit`, and the Next.js production build. Compose configuration and runtime startup are verified when Docker is available; unavailable Docker must be reported as `NOT VERIFIED`.

## Integrity constraints

Only synthetic/sandbox data, public job-description examples, and manually created labels may be used in future phases. The repository must contain no fake product metrics, online experimentation claims, production-readiness claims, employer integrations, private candidate data, or fabricated business impact.

## Scope self-review

- No placeholders or unresolved design choices remain for Phase 0.
- Current and planned architecture are explicitly separated.
- The design contains no Phase 1+ implementation.
- The frontend and backend interfaces use the same health response and environment-variable names.

