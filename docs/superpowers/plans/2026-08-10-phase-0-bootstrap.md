# PeopleMatch Agent Phase 0 Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the documented, runnable Phase 0 monorepo foundation with one real health integration and no future matching behavior.

**Architecture:** A FastAPI application factory exposes a uniform request-traced liveness API; a feature-oriented Next.js App Router frontend consumes it. Docker Compose provisions the application plus PostgreSQL, Redis, and Qdrant while keeping infrastructure readiness separate from liveness.

**Tech Stack:** Python, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.0, Alembic, pytest, Next.js, React, TypeScript, Tailwind CSS, npm, Docker Compose, PostgreSQL, Redis, Qdrant.

## Global Constraints

- Implement only `Phase 0 — Product Definition & Engineering Bootstrap`.
- Use npm because no alternative lockfile exists.
- Keep all local-development commands executable in Windows PowerShell.
- Do not create fake candidates, jobs, metrics, retrieval, ranking, LLM, feedback, or evaluation behavior.
- Do not use real personal data or make production, customer, traffic, or impact claims.
- Report Docker runtime checks as `NOT VERIFIED` if Docker is unavailable.

---

### Task 1: Repository contract and backend behavior tests

**Files:**
- Create: `.gitignore`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`
- Create: `backend/tests/test_errors.py`

**Interfaces:**
- Consumes: the user-approved health envelope and `X-Request-ID` contract.
- Produces: executable API behavior specifications imported from `app.main:create_app`.

- [ ] **Step 1: Create repository ignores and backend test configuration**

  Add Python, Node, environment, build, IDE, log, database, and model-artifact ignores while preserving `.env.example`, docs, and sample data. Add the backend directory to `sys.path` for tests.

- [ ] **Step 2: Write failing API tests**

  Tests must assert HTTP 200 health data, UUID generation, caller ID propagation, consistent 404 errors, and consistent validation errors.

- [ ] **Step 3: Run tests to verify RED**

  Run: `python -m pytest backend/tests -v`

  Expected: collection fails because `app.main` does not exist.

### Task 2: Minimal FastAPI application

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/logging.py`
- Create: `backend/app/api/router.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/api/routes/validation_probe.py`
- Create: `backend/app/middleware/request_id.py`
- Create: `backend/app/schemas/common.py`
- Create: `backend/requirements.txt`

**Interfaces:**
- Consumes: `X-Request-ID: str | absent`.
- Produces: `create_app() -> FastAPI`, `GET /health`, and `ApiResponse`/`ApiError` envelopes.

- [ ] **Step 1: Implement settings, schemas, and middleware**

  `Settings` loads the root `.env`, request middleware uses a supplied ID or `uuid4`, and every response returns `X-Request-ID`.

- [ ] **Step 2: Implement router and application factory**

  Register CORS, liveness, a schema-only validation probe excluded from OpenAPI, and handlers for HTTP, validation, and unknown exceptions.

- [ ] **Step 3: Run tests to verify GREEN**

  Run: `python -m pytest backend/tests -v`

  Expected: all backend tests pass without PostgreSQL, Redis, Qdrant, or LLM access.

### Task 3: Frontend shell and live health integration

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json` through `npm install`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/eslint.config.mjs`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/src/components/module-card.tsx`
- Create: `frontend/src/features/system-status/system-status.tsx`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/types/api.ts`

**Interfaces:**
- Consumes: `NEXT_PUBLIC_API_BASE_URL` and backend `GET /health`.
- Produces: responsive product overview with loading, `Healthy`, and `Unavailable` backend states.

- [ ] **Step 1: Add npm scripts and typed frontend boundaries**

  Define `dev`, `build`, `start`, `lint`, and `typecheck`; keep dependencies limited to the actually used Next.js/React/Tailwind/TypeScript/ESLint toolchain.

- [ ] **Step 2: Implement the page and health feature**

  Use semantic HTML, accessible status announcements, visible focus styling, and planned labels for all future modules. Fetch real backend state and do not cache or fake success.

- [ ] **Step 3: Install and verify**

  Run: `npm install`, `npm run lint`, `npm run typecheck`, `npm run build` from `frontend`.

  Expected: all commands exit 0.

### Task 4: Local infrastructure and database migration foundation

**Files:**
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/.gitkeep`
- Create: `backend/app/models/base.py`
- Create: `infra/docker/README.md`

**Interfaces:**
- Consumes: root environment variables shared by Compose and Pydantic Settings.
- Produces: five local services, named volumes, healthchecks, and empty SQLAlchemy metadata for later migrations.

- [ ] **Step 1: Add aligned configuration and images**

  Use local-only example values, development-friendly Dockerfiles, and no mandatory unused LLM secret.

- [ ] **Step 2: Add Compose services**

  Configure PostgreSQL, Redis, Qdrant, backend, and frontend with named volumes, clear ports, bounded healthchecks, sensible restart policies, and dependency health conditions.

- [ ] **Step 3: Validate configuration**

  Run: `docker compose config`.

  Expected: exit 0, or `NOT VERIFIED` only if Docker is unavailable.

### Task 5: Product and engineering documentation

**Files:**
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `docs/PRD.md`
- Create: `docs/architecture.md`
- Create: `docs/api-design.md`
- Create: `docs/development-roadmap.md`
- Create: `backend/app/services/README.md`
- Create: `data/samples/.gitkeep`
- Create: `data/schemas/.gitkeep`
- Create: `data/eval/.gitkeep`
- Create: `postman/.gitkeep`
- Create: `scripts/.gitkeep`
- Create: `screenshots/.gitkeep`

**Interfaces:**
- Consumes: actual repository paths, scripts, ports, and implemented feature set.
- Produces: an accurate product definition, architecture, API inventory, Phase 0–12 roadmap, Windows-first runbook, and future-agent rules.

- [ ] **Step 1: Document product and architecture**

  Distinguish every CURRENT item from PLANNED items and include the required Mermaid diagrams, personas, workflows, design principles, privacy rules, and success criteria.

- [ ] **Step 2: Document local use and contributor rules**

  README commands must include PowerShell equivalents and match Compose/package/test scripts. AGENTS.md must enforce scope, testing, AI ranking, integrity, privacy, and Git safety.

- [ ] **Step 3: Scan for integrity violations**

  Search for production claims, real-user claims, fake metrics, and accidental future-API implementations; correct any occurrence.

### Task 6: End-to-end verification and handoff

**Files:**
- Modify only files needed to correct verification failures.

**Interfaces:**
- Consumes: complete repository.
- Produces: fresh command evidence for the final report.

- [ ] **Step 1: Run static and unit checks**

  Run backend pytest and frontend lint, typecheck, and build from clean commands.

- [ ] **Step 2: Run Docker checks**

  Run `docker compose config`, `docker compose up -d --build`, `docker compose ps`, and a PowerShell request to `http://localhost:8000/health` when Docker is available.

- [ ] **Step 3: Inspect scope and Git state**

  Run `git diff --check`, inspect `git diff`, list the branch, and run `git status --short`.

- [ ] **Step 4: Report honestly**

  Mark each verification `PASS`, `FAIL`, or `NOT VERIFIED` from actual output; recommend only Phase 0.5 without beginning it.

