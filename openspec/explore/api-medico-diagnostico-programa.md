# Exploration: Doctor API View (Diagnostic + Rehab Program Creation)

**Date**: 2026-06-11  
**Scope**: UC-01 (Diagnostic Assessment) + UC-02 (Rehab Program Setup)  
**Mode**: openspec  
**Status**: ✅ Exploration Complete

---

## Current State

The system has a **partial implementation** of the clinical workflow:

### ✅ Already Implemented

**`api/app/clinical/router.py` — 86 lines, 5 endpoints**:

1. **`POST /patients`** — Create patient (medical/admin roles)
   - Creates `Patient` + `PseudonymMap` + `CareAssignment` (establishes therapeutic relationship)
   - Returns: `{"id": "<patient_id>"}`

2. **`GET /patients`** — List patients (medical/admin roles)
   - RLS-filtered: doctor only sees assigned patients via `CareAssignment`
   - Returns: `[{"id", "nombre", "apellidos"}]`

3. **`POST /patients/claim`** — Claim patient by `national_id` (medical role)
   - Calls PostgreSQL function `clinical.claim_patient()` (SECURITY DEFINER)
   - Creates `CareAssignment` for the current doctor
   - Returns: `{"patient_id": "<uuid>"}`

4. **`POST /diagnostics`** — Create diagnostic (medical role)
   - **Schema**: `DiagnosticIn(patient_id, doctor_id, dolencia, descripcion)`
   - Creates `Diagnostic` + auto-creates a **linked `RehabProgram`** (1:1 in current impl)
   - Returns: `{"diagnostic_id": "<uuid>", "program_id": "<uuid>"}`

5. **`POST /programs/exercises`** — Assign exercise to program (medical role)
   - **Schema**: `AssignExerciseIn(program_id, exercise_id, pauta)`
   - Creates `ProgramExercise` (links catalog exercise to program)
   - Returns: `{"program_exercise_id": "<uuid>"}`

### 🛠️ Data Model (SQLAlchemy)

**`api/app/clinical/models.py` — 80 lines, 6 models**:
- `Patient`, `Doctor`, `CareAssignment`, `Diagnostic`, `RehabProgram`, `ProgramExercise`, `PseudonymMap`
- All models use `UUID` as primary key with `uuid.uuid4()` default
- Schema: `clinical` (PostgreSQL RLS-enabled)

**Exercise Catalog** (`api/app/catalog/models.py`):
- `RehabExercise` (id, nombre, descripcion, tipo)
- **Schema**: `catalog`

### 🔒 Security Implementation

- **Authentication**: `require_role()` dependency enforces RBAC (JWT via Keycloak or dev bypass)
- **RLS Context**: `get_db()` injects `SET app.identity_id` per request (see `api/app/db.py`)
- **Therapeutic Relationship**: `CareAssignment` table controls which doctors see which patients

---

## Gap Analysis: UC-01 + UC-02 Requirements

### AC-01: ✅ Diagnostic Search (Doctor)
**"Doctor searches for Patient → finds diagnosis history"**
- **Implemented**: `GET /patients` returns RLS-filtered patient list
- **Missing**:
  - No `/patients/{id}/diagnostics` endpoint to list diagnostics per patient
  - No `/diagnostics` endpoint to search diagnostics by doctor
  - No diagnostic detail view (`GET /diagnostics/{id}`)

### AC-02: ❌ Diagnostic Search (Patient)
**"Patient searches for Diagnostic → finds all their diagnostic history"**
- **Implemented**: None (no patient-facing diagnostic list endpoint)
- **Missing**:
  - `GET /diagnostics` with `role=patient` filtered by RLS to return only their diagnostics
  - Patient view not yet implemented (out of scope for this exploration — doctor-only focus)

### AC-03: ✅ Diagnostic Creation
**"Doctor can create a Diagnosis linked to the user"**
- **Implemented**: `POST /diagnostics` creates diagnostic and auto-generates linked rehab program
- **Issues**:
  - **No validation**: Doesn't check if `patient_id` exists or is assigned to the doctor
  - **No validation**: Doesn't check if `doctor_id` matches the authenticated user
  - **Missing fields**: `history`, `symptoms`, `signature`, `signed_at`, `content_hash` (attestation per ADR-0012)
  - **Response**: Returns raw dict, not Pydantic schema

### AC-04: ✅ Setup Rehab Plan
**"Doctor creates a rehab plan linked to Diagnostic"**
- **Implemented**: `POST /diagnostics` auto-creates `RehabProgram` (1:1 coupling)
- **Issues**:
  - **No separate creation**: Can't create multiple programs for same diagnostic (SDD §7.1 says 1 diagnostic → N programs)
  - **Missing endpoint**: No `POST /programs` to create program explicitly
  - **Missing fields**: `physiotherapist_id`, `name`, `start_date`, `end_date`

### AC-05: ✅ Assign Program Exercises
**"Doctor assigns a program exercise linked to rehab program"**
- **Implemented**: `POST /programs/exercises`
- **Issues**:
  - **No validation**: Doesn't check if `program_id` exists or is visible to the doctor via RLS
  - **No validation**: Doesn't check if `exercise_id` exists in catalog
  - **Missing**: No `frequency` support (SDD model has `frequency`, payload has `pauta`)

### AC-06: ❌ Rehab Program Search (Doctor)
**"Doctor searches for Rehab program → finds all Rehab programs"**
- **Missing**:
  - No `GET /programs` endpoint
  - No `GET /patients/{id}/programs` endpoint
  - No `GET /programs/{id}` detail view

### AC-07: ❌ Rehab Program Search (Patient)
**"Patient finds all their Rehab programs linked to Diagnostics"**
- **Missing**: (Patient view out of current scope)

### AC-08: ❌ Rehab Exercise Search (Doctor)
**"Doctor searches for Rehab exercise → finds all Rehab exercises"**
- **Partial**: `GET /catalog/exercises` exists in `catalog/router.py`
- **Issue**: Returns raw dicts, not Pydantic schemas

---

## Identified Constraints

### 1. Security (Critical)

**Row-Level Security (RLS)**:
- PostgreSQL RLS policies enforce `clinical.current_patient_id()` / `clinical.current_doctor_id()`
- The API must set `app.identity_id` context variable per request (already implemented in `get_db()`)
- **Contract**: Doctors see patients they're assigned via `CareAssignment`
- **Risk**: If validation is missing, RLS will block unauthorized reads/writes → API returns 0 rows (silent failure vs explicit 403)

**Role Enforcement**:
- `require_role("medical")` enforces RBAC
- Dev mode bypass: `x-dev-role` header (blocked in prod via `config.py`)

### 2. Data Model Relationships

**Diagnostic → RehabProgram → ProgramExercise → Exercise Recording**

- **1 Diagnostic → N RehabProgram** (per SDD §7.1, but current impl auto-creates 1:1)
- **1 RehabProgram → N ProgramExercise**
- **1 ProgramExercise → 0..1 AnalysisSetup** (lives in `setup` schema, configured by technician)
- **1 ProgramExercise → N ExerciseRecording**

**Dependencies**:
- Creating diagnostic requires existing `patient_id` and `doctor_id`
- Assigning exercise requires existing `program_id` and `exercise_id` (catalog)
- RLS filters all reads by `CareAssignment`

### 3. Business Rules (FR-09, FR-11, FR-12, FR-13)

- **FR-09**: Patient only sees their data (RLS enforced)
- **FR-11**: Doctor can create Diagnostic ✅
- **FR-12**: Doctor can create Rehab Exercise ❌ (no endpoint)
- **FR-13**: Doctor can create Rehab Program ⚠️ (auto-created with diagnostic, no explicit endpoint)
- **FR-15**: All actions must be logged to `audit.event_log` ❌ (not implemented)

### 4. Attestation (ADR-0012)

**Diagnostic signature fields**:
- `signature`, `signed_at`, `content_hash`
- Current impl: `signature` is nullable, `signed_at` defaults to `now()` in schema
- ADR-0012: "Attestation = identity (`sub` + `colegiado_id`) + timestamp + hash"
- **Missing**: Hash computation, explicit signature generation

---

## Missing Features (Prioritized)

### 🔴 Critical (Blocks UC-01/UC-02)

1. **Validation** — All POST endpoints lack:
   - Patient/doctor existence checks
   - Foreign key validation (does `exercise_id` exist?)
   - RLS-aware authorization checks (is this doctor assigned to this patient?)

2. **Response Schemas** — All endpoints return raw dicts:
   - Should use Pydantic `BaseModel` for consistent typing
   - OpenAPI spec will be incomplete without them

3. **Error Handling** — No explicit 404/403/422 responses:
   - Currently: SQLAlchemy foreign key violations → 500 Internal Server Error
   - Expected: 404 "Patient not found", 403 "Not authorized", 422 "Validation error"

### 🟡 High (Completes UC-01/UC-02)

4. **GET /diagnostics** — List diagnostics:
   - For doctor: all diagnostics for assigned patients
   - For patient: only their diagnostics (future)
   - Filters: `patient_id`, `doctor_id`, date range

5. **GET /diagnostics/{id}** — Diagnostic detail:
   - Returns full diagnostic + linked rehab programs
   - Includes signature/attestation metadata

6. **POST /programs** — Explicit rehab program creation:
   - Decouple from diagnostic creation
   - Schema: `RehabProgramIn(diagnostic_id, physiotherapist_id, name, start_date, end_date)`

7. **GET /programs** — List rehab programs:
   - For doctor: programs for assigned patients
   - Filters: `diagnostic_id`, `patient_id`, `status`

8. **GET /programs/{id}** — Program detail:
   - Returns program + list of `ProgramExercise` + exercise names
   - Aggregates assigned exercises with their pauta/frequency

9. **GET /programs/{id}/exercises** — List exercises in program:
   - Returns `ProgramExercise` joined with catalog `RehabExercise`

### 🟢 Medium (Improves robustness)

10. **PATCH /diagnostics/{id}** — Update diagnostic:
    - Update `description`, `history`, `symptoms`
    - Regenerate `content_hash` if modified

11. **DELETE /programs/exercises/{id}** — Remove exercise from program:
    - Only allowed if no `AnalysisSetup` exists (per UC-16)

12. **Audit Logging** — `audit.event_log` inserts:
    - Hook into `POST/PATCH/DELETE` operations
    - Record `entity_type`, `entity_id`, `action`, `actor_id`

---

## Approach Options

### Option A: Monolithic Router Completion ⚙️
**Extend `clinical/router.py` with all missing endpoints**

**Structure**:
```
clinical/
├── router.py       # All patient/diagnostic/program endpoints (200+ lines)
├── models.py       # SQLAlchemy models
├── schemas.py      # Pydantic request/response schemas (NEW)
└── validation.py   # Business rule checks (NEW)
```

**Pros**:
- Single file = simple deployment
- All clinical logic in one place
- No routing complexity

**Cons**:
- Violation of SRP: router grows to 200+ lines (patient + diagnostic + program)
- Testing becomes harder (one large test suite)
- Merge conflicts in team settings

**Effort**: Low (2-3 hours for all CRUD endpoints)

---

### Option B: Split by Domain Entity 📂
**Separate routers: `diagnostic_router.py`, `program_router.py`**

**Structure**:
```
clinical/
├── __init__.py
├── models.py
├── schemas.py       # Shared Pydantic schemas
├── validation.py    # Shared validation logic
├── patient_router.py     # POST/GET /patients, /patients/claim
├── diagnostic_router.py  # POST/GET /diagnostics, /diagnostics/{id}
└── program_router.py     # POST/GET /programs, /programs/{id}/exercises
```

**Pros**:
- Clear separation of concerns (one router = one entity)
- Easier to test (mock only relevant dependencies)
- Scales better for team collaboration
- Each file stays < 100 lines

**Cons**:
- More files to navigate
- Need to register 3 routers in `main.py`

**Effort**: Medium (4-5 hours, includes refactoring)

---

### Option C: Service Layer Extraction 🏗️
**Introduce `clinical/services.py` for business logic**

**Structure**:
```
clinical/
├── __init__.py
├── models.py
├── schemas.py
├── services.py      # DiagnosticService, ProgramService (NEW)
├── validation.py
├── patient_router.py
├── diagnostic_router.py
└── program_router.py
```

**Service Example**:
```python
class DiagnosticService:
    def __init__(self, db: Session, principal: dict):
        self.db = db
        self.principal = principal

    def create_diagnostic(self, data: DiagnosticIn) -> Diagnostic:
        # 1. Validate patient exists and is assigned to doctor
        # 2. Create Diagnostic
        # 3. Log to audit.event_log
        # 4. Return entity
        ...
```

**Pros**:
- Routers become thin controllers (validation + service call)
- Business logic testable without HTTP layer
- Reusable across REST/GraphQL/CLI
- Clear dependency injection

**Cons**:
- Over-engineering for MVP (20-day deadline)
- Adds abstraction layer (learning curve)
- More boilerplate

**Effort**: High (6-8 hours, includes service design)

---

## Recommended Approach

**🏆 Option B: Split by Domain Entity** (with phased rollout)

**Reasoning**:
1. **Maintainability**: Keeps routers focused (< 100 lines each)
2. **Testability**: Easier to mock and test in isolation
3. **Scalability**: Prepares for future features (reports, follow-ups)
4. **MVP-friendly**: Can be done incrementally without breaking existing code
5. **No over-engineering**: Avoids service layer abstraction (defer to post-MVP)

**Phased Implementation** (3 PRs):

### PR #1: Foundation (Schemas + Validation)
- Create `clinical/schemas.py` (Pydantic request/response models)
- Create `clinical/validation.py` (patient/doctor existence checks)
- Refactor existing endpoints to use schemas
- **Deliverable**: No new features, improved type safety

### PR #2: Diagnostic CRUD
- Create `clinical/diagnostic_router.py`
- Endpoints: `GET /diagnostics`, `GET /diagnostics/{id}`, `PATCH /diagnostics/{id}`
- Move `POST /diagnostics` from main router (or keep both, mark old as deprecated)
- **Deliverable**: AC-01, AC-03 complete

### PR #3: Program CRUD
- Create `clinical/program_router.py`
- Endpoints: `POST /programs`, `GET /programs`, `GET /programs/{id}`, `GET /programs/{id}/exercises`
- Decouple program creation from diagnostic
- **Deliverable**: AC-04, AC-05, AC-06 complete

**Rollback Plan**:
- Each PR is isolated (no breaking changes)
- Old router stays functional during migration
- Can feature-flag new endpoints if needed

---

## Risks

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **RLS silent failures** | API returns empty arrays instead of 403 | Medium | Add explicit `CareAssignment` checks before RLS queries |
| **No tests** | Breaking changes undetected | High | Add integration tests for auth/RLS (use `pytest` + `TestClient`) |
| **Audit log missing** | Compliance failure (FR-15) | Medium | Implement decorator `@audit_log` for all writes |
| **Attestation incomplete** | Legal issues (signature not verifiable) | Low (MVP) | Document ADR-0012 as "simple attestation, not eIDAS" |

### Product Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **1:1 Diagnostic→Program** | Can't create multiple programs for same diagnostic | High | Decouple in PR #3 (`POST /programs` endpoint) |
| **No patient view** | Patients can't self-serve | High (known) | Out of scope for this exploration (doctor-only) |
| **No pagination** | List endpoints fail with 1000+ diagnostics | Medium | Add `?limit=20&offset=0` in GET endpoints |

---

## Dependencies

### External Dependencies
- **Keycloak** (OIDC IdP) — Already integrated (`api/app/auth.py`)
- **PostgreSQL 15+** with RLS — Schema exists (`doc/bbdd/ftm_schema.sql`)
- **Catalog data** — `catalog.rehab_exercise` must be seeded (see `bbdd_dev_setup/`)

### Internal Dependencies
- **`catalog` module** — `RehabExercise` model (already implemented)
- **`setup` module** — `AnalysisSetup` (exists but not exposed via API yet)
- **`audit` module** — `EventLog` model (not implemented)

---

## Acceptance Criteria Summary

| AC | Description | Status | Missing |
|----|-------------|--------|---------|
| AC-01 | Doctor searches for patient diagnosis history | ⚠️ Partial | GET /patients/{id}/diagnostics |
| AC-02 | Patient searches for diagnostic history | ❌ | Patient role endpoints |
| AC-03 | Doctor creates diagnosis linked to patient | ✅ | Validation, attestation |
| AC-04 | Doctor creates rehab plan linked to diagnostic | ⚠️ Partial | Explicit POST /programs |
| AC-05 | Doctor assigns program exercise to rehab program | ✅ | Validation |
| AC-06 | Doctor searches for Rehab program | ❌ | GET /programs |
| AC-07 | Patient searches for Rehab program | ❌ | Patient role endpoints |
| AC-08 | Doctor searches for Rehab exercise | ✅ | In catalog/router.py |

**✅ 2 complete** · **⚠️ 2 partial** · **❌ 4 missing**

---

## Ready for Proposal?

**✅ YES** — with constraints:

**What's clear**:
- Technical stack is proven (FastAPI + SQLAlchemy + PostgreSQL RLS)
- Data model is complete (SDD §7 + `ftm_schema.sql`)
- Auth/RLS infrastructure works (tested in existing endpoints)

**What needs user input**:
- **Priority**: Should we complete doctor view first (AC-01 to AC-06) or build patient view in parallel?
- **Attestation**: Is simple attestation (ADR-0012) acceptable for MVP, or do we need eIDAS integration?
- **Pagination**: What's the expected scale? (100 patients? 1000? 10,000?)

**Recommended next phase**: `sdd-propose` to define:
1. Scope: Doctor view completion (AC-01, AC-03, AC-04, AC-06) + validation + schemas
2. Out of scope: Patient view (AC-02, AC-07), audit logging (FR-15), attestation crypto
3. Delivery: 3 PRs (foundation → diagnostics → programs), ~400 changed lines per PR
4. Verification: Manual (Postman/curl) until tests exist

---

**Artifacts Created**:
- `openspec/explore/api-medico-diagnostico-programa.md` (this file)

**Next Recommended Phase**: `sdd-propose`
