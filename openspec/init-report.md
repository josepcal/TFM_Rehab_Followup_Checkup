# SDD Initialization Report: tfm_rehab_followup_checkup

**Date**: 2026-06-11  
**Mode**: openspec  
**Status**: ✅ Initialized

---

## Executive Summary

FastAPI + SQLAlchemy + PostgreSQL backend for a rehabilitation follow-up system with voice analysis capabilities. Infrastructure as Code via Terraform (Google Cloud). **No test runner detected** — Strict TDD Mode is **disabled** by default.

---

## Technology Stack

### Primary Languages
- **Python 3.12** (API backend)
- **HCL/Terraform** (Infrastructure as Code)
- **SQL** (PostgreSQL with Alembic migrations)

### Core Frameworks & Libraries
- **FastAPI** (≥0.110) — REST API framework
- **SQLAlchemy** (≥2.0) — ORM with declarative models
- **Alembic** (≥1.13) — Database migrations
- **Pydantic Settings** (≥2.2) — Configuration management
- **python-jose** (≥3.3) — JWT authentication (Keycloak OIDC)
- **psycopg2-binary** (≥2.9) — PostgreSQL driver

### Audio Analysis Stack
- **librosa** (≥0.10) — Audio feature extraction
- **numpy** (≥1.26), **scipy** (≥1.12) — Numerical processing
- **soundfile** (≥0.12) — Audio I/O

### Infrastructure & Storage
- **Terraform** — Google Cloud Platform provisioning
- **Google Cloud Storage** (≥2.16) — WAV file storage
- **Docker** — Containerization (Python 3.12-slim base)
- **Uvicorn** (≥0.29) — ASGI server

---

## Project Structure

```
tfm_rehab_followup_checkup/
├── api/
│   ├── app/
│   │   ├── ai/           # LLM service integration
│   │   ├── analysis/     # Audio analysis functions & models
│   │   ├── catalog/      # Exercise catalog
│   │   ├── clinical/     # Patients, diagnostics, rehab programs
│   │   ├── iam/          # Identity & access management
│   │   ├── metrics/      # Session metrics & analytics
│   │   ├── recording/    # Audio recording management
│   │   ├── reporting/    # Report generation
│   │   ├── auth.py       # JWT/Keycloak authentication
│   │   ├── config.py     # Pydantic settings
│   │   ├── context.py    # ContextVars for RLS
│   │   ├── db.py         # SQLAlchemy setup + RLS injection
│   │   ├── jobs.py       # Background job model
│   │   ├── main.py       # FastAPI app + router registration
│   │   ├── storage.py    # GCS/local file storage
│   │   └── worker.py     # Background worker
│   ├── migrations/       # Alembic database migrations
│   ├── requirements.txt  # Python dependencies
│   ├── alembic.ini       # Alembic configuration
│   └── Dockerfile        # Production image
├── terraform/
│   ├── modules/          # Reusable Terraform modules (network, postgresql, nginx, keycloak, app)
│   ├── environments/     # dev/prod environment configs
│   ├── main.tf           # Root Terraform config
│   └── *.tf              # Variables, outputs, versions
├── bbdd_dev_setup/       # Alembic seed scripts for dev
└── doc/                  # Documentation
```

---

## Testing Capabilities

### Test Runner
**❌ NOT DETECTED**

No test framework (pytest, unittest, nose) found in `requirements.txt`.  
No test files (`test_*.py`, `*_test.py`) found in the codebase.  
No test configuration files (`pytest.ini`, `setup.cfg`, `.coveragerc`, `tox.ini`) detected.

### Coverage Tools
**❌ NOT AVAILABLE**

### Linter/Formatter
**Not explicitly configured** (no `ruff.toml`, `.flake8`, `pyproject.toml` with tool config detected).

### Type Checker
**Not explicitly configured** (no `mypy.ini` or `pyproject.toml` with `[tool.mypy]` detected).

### CI/CD
**Not detected** (no `.github/workflows/`, `.gitlab-ci.yml`, or `.circleci/` found).

---

## Strict TDD Mode

**Status**: ❌ **DISABLED**

**Reason**: No test runner detected. To enable Strict TDD Mode, the project requires:
1. A test framework (e.g., `pytest`) installed in `requirements.txt`
2. Coverage tooling (e.g., `pytest-cov`, `coverage`)
3. At least 3 existing test files demonstrating test conventions

**Recommendation**: Add `pytest>=8.0` and `pytest-cov>=4.0` to `requirements.txt`, create a `pytest.ini` or `pyproject.toml` test config, and write initial tests for critical paths (auth, RLS, audio analysis).

---

## Key Conventions Detected

### Code Style
- **Module structure**: Feature-based modules (`clinical/`, `analysis/`, etc.) with `models.py`, `router.py`, `__init__.py`
- **Naming**: Snake_case for variables/functions, PascalCase for classes
- **Database schemas**: Explicit schema prefix (`SCHEMA = "clinical"`)
- **Model base**: `app.db.Base` (SQLAlchemy `DeclarativeBase`)

### Authentication & Security
- **Two-mode auth**: `auth_mode=dev` (bypass with `x-dev-role` header) vs. `auth_mode=keycloak` (OIDC JWT)
- **Production guard**: `auth_mode=dev` is **blocked** when `app_env=prod` (see `config.py:28`)
- **Row-Level Security (RLS)**: PostgreSQL session variables (`app.user`, `app.role`) injected via `_apply_rls()` before every transaction
- **Principal injection**: `current_principal` dependency → `get_db` dependency chain ensures RLS context is set

### Database Patterns
- **UUIDs as primary keys** (`UUID(as_uuid=True)`, defaults to `uuid.uuid4()`)
- **Timestamp tracking**: `created_at = Column(DateTime, default=datetime.utcnow)`
- **Alembic migrations**: Located in `api/migrations/`, config in `api/alembic.ini`
- **Schema separation**: `clinical`, `analysis`, `catalog`, `iam`, `metrics` schemas

### Configuration Management
- **Pydantic Settings**: `app.config.Settings` with `.env` file support
- **Cached singleton**: `@lru_cache` on `get_settings()` for performance
- **Environment-aware**: `app_env` (dev/prod), `auth_mode` (dev/keycloak), `wav_bucket` (GCS/local)

### API Design
- **Router-based**: Each domain module has a `router.py` with `APIRouter(tags=[...])`
- **Dependency injection**: `Depends(require_role(...))`, `Depends(get_db)`
- **Health check**: `/health` endpoint returns `{"status": "ok", "env": ..., "auth": ...}`
- **Root path**: `/api` prefix for nginx reverse proxy routing

### Infrastructure
- **Terraform modules**: Modular IaC for network, postgresql, nginx, keycloak, app
- **Environments**: Separate `dev`/`prod` configs under `terraform/environments/`
- **Docker**: Slim Python 3.12 image, installs deps via pip (see `api/Dockerfile`)

---

## File Inventory

- **42 Python files** (`.py`)
- **26 Terraform files** (`.tf`)
- **1 Alembic config** (`alembic.ini`)
- **1 Docker Compose dev setup** (`docker-compose.dev.yml`)

---

## Persistence Artifacts

### Engram Observations
- **Topic**: `sdd/tfm_rehab_followup_checkup/init-report`
- **Type**: architecture
- **Scope**: project

### Openspec Files
- ✅ `openspec/init-report.md` (this file)

---

## Next Steps

### To Enable Testing
1. Add to `requirements.txt`:
   ```
   pytest>=8.0
   pytest-cov>=4.0
   pytest-asyncio>=0.23  # for async FastAPI tests
   httpx>=0.27           # already installed, use for TestClient
   ```
2. Create `pytest.ini`:
   ```ini
   [pytest]
   testpaths = tests
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*
   addopts = --cov=app --cov-report=term-missing --cov-fail-under=80
   ```
3. Create `tests/` directory with initial test files:
   - `tests/test_auth.py` — JWT validation, dev mode bypass, role extraction
   - `tests/test_rls.py` — PostgreSQL RLS context injection
   - `tests/test_health.py` — Basic health endpoint

### Recommended SDD Workflow
1. **Explore**: `/sdd-explore` to map technical constraints and user requirements
2. **Propose**: `/sdd-propose` to define intent, scope, and approach for a change
3. **Spec**: `/sdd-spec` to write behavior-driven scenarios
4. **Design**: `/sdd-design` to create technical architecture
5. **Tasks**: `/sdd-tasks` to break work into reviewable units
6. **Apply**: `/sdd-apply` to implement tasks
7. **Verify**: `/sdd-verify` to prove implementation matches specs (manual verification until tests exist)
8. **Archive**: `/sdd-archive` to sync delta specs when done

---

## Risks & Constraints

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **No automated tests** | Regressions undetected; RLS bypass risks | Add pytest + coverage; write auth/RLS tests first |
| **Dev auth bypass** | Accidental prod misconfiguration | Guard already exists (`config.py:28`); enforce via CI |
| **Audio processing deps** | librosa/scipy installation complexity | Docker image pre-installs; document system deps |
| **GCS credential management** | Misconfigured service accounts | Verify Terraform IAM bindings; use Workload Identity |
| **RLS context leak** | Pooled connections reuse old `app.user` | Already mitigated: `is_local=true` in `set_config()` |

---

**Generated by**: SDD Init (openspec mode)  
**Agent**: claude-sonnet-4-5  
**Engram Session**: tfm_rehab_followup_checkup-init
