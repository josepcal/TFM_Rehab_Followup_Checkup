# Plan

This guide gives coding agents the minimum operational context needed to work safely in FTM. It links to `Architecture.md` for architecture detail and uses `.github/skills/*/SKILL.md` for task-specific procedures.

# FTM Agent Guide

## Project summary

FTM is a medical rehabilitation follow-up tool. It supports a clinical flow from diagnostic assessment to rehab program setup, exercise recording, asynchronous metric extraction, optional AI insight, exercise report and follow-up check-up (see `Architecture.md`).

The project is privacy-sensitive: health data, patient identity and raw voice/audio are protected by Keycloak, PostgreSQL schemas, RLS, pseudonymization and EU data residency. Agents must not invent behavior beyond the SDD/ADR source documents.

## Technology stack

| Layer | Technology | Version / constraint | Source |
|---|---|---|---|
| Backend | Python | 3.12 | ADR-0002 |
| API | FastAPI | Version not specified | ADR-0002 |
| Validation | Pydantic | v2 | ADR-0002 |
| ORM | SQLAlchemy | 2.0 | ADR-0002 |
| Migrations | Alembic | SQL-first baseline | ADR-0017 |
| Frontend | React | 18 | ADR-0003 |
| Build | Vite | Version not specified | ADR-0003 |
| Language | TypeScript | Version not specified | ADR-0003 |
| Frontend data | TanStack Query | Version not specified | ADR-0003 |
| Charts | Recharts | Version not specified | ADR-0003 |
| Auth client | `keycloak-js` | Version not specified | ADR-0003, ADR-0004 |
| Identity provider | Keycloak | Version not specified | ADR-0004 |
| Database | PostgreSQL | Version not specified | ADR-0005 |
| Reverse proxy | nginx | Version not specified | ADR-0018 |
| Worker | Python worker container | Queue choice not decided | ADR-0007 |
| Object storage | S3/GCS managed or MinIO self-host | EU region | ADR-0006, ADR-0015, ADR-0019 |
| LLM | Claude via EU Bedrock/Vertex by default; Mistral as sovereign alternative | Contract to confirm | ADR-0019 |

## Repository structure

| Path | Purpose | Status |
|---|---|---|
| `/api` | FastAPI backend, SQLAlchemy models, tests and clinical modules. | Present in repo. |
| `/web` | React/Vite frontend. | Expected from ADR-0003; verify exact current path before editing. |
| `/infra` | Infrastructure code. | Expected from deployment ADR; verify exact current path. |
| `/bbdd_dev_setup` | App/Keycloak database setup and Alembic baseline. | Present in repo. |
| `/doc/sdd` | SDD source of truth. | Present in repo. |
| `/doc/architecture` | ADR source of truth. | Present in repo. |
| `/openspec` | Change/spec/task artifacts. | Present in repo. |
| `.github/` | CI/workflows and project skills. | Present in repo. |

## Commands

The SDD/ADR do not define exact local commands. Use the commands below as repository-local defaults and verify before relying on them in CI.

```bash
# TODO (verify): backend setup
cd api
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# TODO (verify): backend lint / type-check
cd api
ruff check .
mypy .

# Backend tests observed in this repo
api/.venv/bin/python -m pytest api/tests -q

# DB-backed integration tests require a migrated PostgreSQL app DB
RUN_INTEGRATION=1 DATABASE_URL="postgresql://<user>:<password>@localhost:5432/<db>" \
  api/.venv/bin/python -m pytest api/tests/integration -q

# TODO (verify): frontend setup/lint/build
cd web
npm install
npm run lint
npm run build

# TODO (verify): local containers
cd infra
docker compose up -d

# TODO (verify): Alembic migration command and config path
cd bbdd_dev_setup/alembic
alembic upgrade head
```

## Code conventions

- Backend code uses Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 and Alembic (ADR-0002, ADR-0017).
- Frontend code uses React 18 + Vite + TypeScript, TanStack Query, Recharts and `keycloak-js` (ADR-0003).
- Modules follow bounded contexts: `iam`, `clinical`, `recording`, `metrics`, `analysis`, `reporting` (ADR-0001).
- No module accesses another module's database tables directly except through that module's service boundary (ADR-0001).
- Migrations are SQL-first after the baseline. Views, roles, grants and RLS policies require explicit Alembic SQL (ADR-0017).
- Worker work is asynchronous and must capture timeout/error status (ADR-0007, ADR-0009).

## Non-negotiable guardrails

- **Never send identity, PII or raw audio to the LLM.** The LLM receives only pseudonymized metrics (FR-04, FR-17, ADR-0013).
- **Every patient-data access needs API authorization plus RLS assumptions.** Set JWT-derived identity/role in the DB session as required by the RLS contract (ADR-0014).
- **Voice is biometric special-category data.** Require explicit consent before recording and minimize stored data (FR-14, FR-16, SDD §6.1).
- **Never commit secrets.** Use the secret store; exact provider is TODO because the SDD/ADR do not specify it.
- **Analysis functions ship by PR + review + deploy.** No runtime code upload or arbitrary code execution (ADR-0008).
- **Keep `postgres-app` separate from `postgres-keycloak`.** The app DB and Keycloak DB are distinct (ADR-0005).
- **Do not use `create_all()` for production schema.** Use Alembic and SQL-first migration rules (ADR-0017).
- **The app must not connect as database owner.** RLS depends on role login + `SET app.identity_id` (ADR-0014).

## How to do frequent tasks

| Task | Skill |
|---|---|
| Write or refactor Python package code | `.github/skills/python/SKILL.md` |
| Create a FastAPI route or schema | `.github/skills/fastapi/SKILL.md` |
| Add SQLAlchemy model or Alembic migration | `.github/skills/sqlalchemy-alembic/SKILL.md` |
| Add schema/table/RLS policy | `.github/skills/add-schema-and-rls/SKILL.md` |
| Protect an endpoint with RBAC/RLS | `.github/skills/protect-endpoint-rbac/SKILL.md` |
| Add an audio analysis function | `.github/skills/add-analysis-function/SKILL.md` |
| Work with DSP/audio metric code | `.github/skills/audio-dsp-python/SKILL.md` |
| Call the LLM or build an insight payload | `.github/skills/llm-insight-safe/SKILL.md` |
| Build React UI | `.github/skills/react/SKILL.md` |
| Tighten TypeScript types | `.github/skills/typescript/SKILL.md` |
| Fetch frontend data, auth or charts | `.github/skills/frontend-data-auth/SKILL.md` |
| Add browser recording upload flow | `.github/skills/audio-recording-web/SKILL.md` |
| Change containers/nginx routing | `.github/skills/containers-and-nginx/SKILL.md` |

## Required tests

- Unit tests for Pydantic validation, domain/service logic and analysis functions.
- API tests for success and failure paths, including wrong role vs correct role.
- PostgreSQL-backed integration tests for schema behavior and RLS isolation by role.
- Worker tests for timeout/error persistence and `status=error` behavior.
- AI privacy tests that assert forbidden fields are absent from LLM payloads.
- Frontend tests for protected routes, loading/error states and token refresh behavior when implemented.

RLS isolation against real PostgreSQL is explicitly called out as required but not yet verified in the ADR open decisions (ADR-0014).

## References

- `Architecture.md`
- `doc/sdd/FTM_SDD_1_8.md`
- `doc/architecture/ADR_from_SDD_1.8.md`
- `.github/skills/*/SKILL.md`
