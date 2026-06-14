# Tasks: Doctor Diagnostic & Program Management API

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~830 (foundation ~250 + diagnostic ~300 + program ~280) |
| 400-line budget risk | **Medium** (total exceeds 400, but each PR ≤ 400) |
| Chained PRs recommended | **Yes** |
| Suggested split | PR #1 (Foundation) → PR #2 (Diagnostic CRUD) → PR #3 (Program CRUD) |
| Delivery strategy | auto-chain (PR #1 base=main; PR #2 base=PR #1 branch; PR #3 base=PR #2 branch) |
| Chain strategy | stacked-to-main (each PR merges to main in order; no rollup branch) |

**Decision needed before apply**: No  
**Chained PRs recommended**: Yes  
**Chain strategy**: stacked-to-main  
**400-line budget risk**: Medium

---

## Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Establish Pydantic schemas and validation helpers | PR #1 | Base: main. Foundation for all CRUD endpoints. Tests included. |
| 2 | Implement diagnostic CRUD endpoints | PR #2 | Base: PR #1 branch. Depends on schemas + validation from PR #1. |
| 3 | Implement program + exercise assignment endpoints | PR #3 | Base: PR #2 branch. Depends on PR #1 + PR #2 schemas and helpers. |

Each PR:
- Passes all tests independently
- Includes unit + integration tests
- No half-done state (all endpoints + tests ship together)
- Reviewable in ≤20 min (under 400 lines per PR)


## Implementation Checkpoint Status

**Last updated**: 2026-06-14  
**Verification**: `api/.venv/bin/python -m pytest api/tests -q` → `44 passed`; `RUN_INTEGRATION=1 ... pytest api/tests/integration -q` → `23 passed`

Checked items below reflect implementation/unit-test checkpoints currently present in code.
Program detail/exercise assignment integration checkpoints now have real TestClient/PostgreSQL coverage; remaining endpoint/integration/RLS tasks stay unchecked until covered.

---


### Current implementation notes

- `ProgramExerciseOut` currently exposes `estado` but not `created_at`; task 2.4 remains unchecked until schema/model support exists.
- `check_diagnostic_authorized` now authorizes through `clinical.app_user.external_subject` + `clinical.doctor.doctor_id`, matching the SDD/ERD database; isolated unit tests keep a legacy assignment fallback only for old DummyDB coverage.
- `check_program_belongs_to_diagnostic(program_id, None, db)` is now supported as an existence-only lookup for program detail/exercise assignment before follow-up diagnostic authorization.
- `api/app/main.py` registers routers directly because the FastAPI app already uses `root_path="/api"`; this satisfies router registration without an extra include prefix.
- The deprecated `/programs/exercises` wrapper still uses its local `AssignExerciseIn` and a placeholder principal dependency, so PR #3 task 5.2 remains unchecked.
- Minimal API ORM alignment now maps compatibility attributes (`id`, `descripcion`, `estado`, `pauta`) onto the SDD/ERD database columns (`*_id`, `description`, `status`, `frequency`) for the program/detail exercise path.
- Program endpoints now route through a small hexagonal slice: `ProgramService` + `ProgramRepository` port + `PostgresProgramRepository`, keeping SQLAlchemy details out of `program_router.py`.
- Diagnostic endpoints now route through a matching hexagonal slice: `DiagnosticService` + `DiagnosticRepository` port + `PostgresDiagnosticRepository`, removing direct SQLAlchemy query/persistence logic from `diagnostic_router.py`.
- Diagnostic creation/update now generates ADR-0012 MVP attestation metadata (`signature`, `signed_at`, `content_hash`) instead of the previous `unsigned:<uuid>` placeholder.
- Deprecated clinical compatibility endpoints now delegate to services: `POST /diagnostics` creates diagnostic + initial program through the hexagonal services, and `POST /programs/exercises` delegates to `ProgramService.assign_exercise`.
- Fast hexagonal service unit tests now cover `DiagnosticService` and `ProgramService` with fake repositories, proving orchestration without PostgreSQL.
- Diagnostic invalid pagination integration tests now cover FastAPI/Pydantic bounds (`limit=200`, `offset=-1`) returning 422; OpenSpec tasks 6.6–6.7 remain unchecked because the task text expects 400.

## PR #1: Foundation (Schemas & Validation)

**Scope**: Create `clinical/schemas.py` and `clinical/validation.py` with types, validators, and helper functions.  
**Base branch**: main  
**Estimated lines**: ~250  
**Review time**: 15 min  
**Risk**: Low (new files, no existing code modified)

### Phase 1: Pydantic Schemas (Request Models)

- [x] 1.1 Create `api/app/clinical/schemas.py` (empty file, placeholder)
- [x] 1.2 Add `DiagnosticIn` model: patient_id, dolencia (1-500), descripcion (0-5000, optional)
- [x] 1.3 Add `DiagnosticPatchIn` model: dolencia and descripcion as optional fields with same validators
- [x] 1.4 Add `ProgramIn` model: diagnostic_id (UUID, required)
- [x] 1.5 Add `ProgramExerciseIn` model: exercise_id (UUID), pauta (string, optional)
- [x] 1.6 Add `ListQuery` model: limit (0-100, default 20), offset (≥0, default 0) with field validators

### Phase 2: Pydantic Schemas (Response Models)

- [x] 2.1 Add `PatientOut` model: id, nombre (from existing Patient ORM)
- [x] 2.2 Add `DiagnosticOut` model: id, patient_id, doctor_id, dolencia, descripcion, signature, signed_at, created_at
- [x] 2.3 Add `ProgramOut` model: id, diagnostic_id, estado, created_at (from existing RehabProgram ORM)
- [ ] 2.4 Add `ProgramExerciseOut` model: id, program_id, exercise_id, pauta, estado, created_at
- [x] 2.5 Add generic `PaginatedResponse[T]` model: data (list), total, limit, offset

### Phase 3: Validation Helpers (Core Functions)

- [x] 3.1 Create `api/app/clinical/validation.py` (empty file, placeholder)
- [x] 3.2 Implement `check_patient_exists_and_assigned(db, patient_id, doctor_keycloak_id) → Patient`
  - Query Patient by id → raise HTTPException(404, "Patient not found") if missing
  - Query CareAssignment(patient_id, doctor_keycloak_id) → raise HTTPException(403, "Patient not assigned to you") if missing
  - Return Patient object on success
- [x] 3.3 Implement `check_diagnostic_authorized(db, diagnostic_id, doctor_keycloak_id) → Diagnostic`
  - Query Diagnostic by id → raise HTTPException(404, "Diagnostic not found") if missing
  - Verify doctor_id == doctor_keycloak_id → raise HTTPException(403, "You are not the author of this diagnostic") if mismatch
  - Return Diagnostic object on success
- [x] 3.4 Implement `check_program_belongs_to_diagnostic(db, program_id, diagnostic_id) → RehabProgram`
  - Query RehabProgram by id with diagnostic_id filter → raise HTTPException(404, "Program not found") if missing or mismatch
  - Return RehabProgram object on success
- [x] 3.5 Implement `check_exercise_exists(db, exercise_id) → UUID`
  - Query catalog.rehab_exercise by id → raise HTTPException(404, "Exercise not found in catalog") if missing
  - Return exercise_id on success
- [x] 3.6 Implement `parse_pagination(limit: int, offset: int) → tuple[int, int]`
  - Validate limit ∈ [0, 100] → raise HTTPException(400, "limit must be 0-100") if invalid
  - Validate offset ≥ 0 → raise HTTPException(400, "offset must be ≥ 0") if invalid
  - Return (limit, offset) tuple on success

### Phase 4: Unit Tests for Schemas

- [x] 4.1 Test `DiagnosticIn` validator: valid input (1-500 char dolencia) passes
- [x] 4.2 Test `DiagnosticIn` validator: dolencia < 1 char raises ValueError
- [x] 4.3 Test `DiagnosticIn` validator: dolencia > 500 chars raises ValueError
- [x] 4.4 Test `DiagnosticIn` validator: descripcion > 5000 chars raises ValueError
- [ ] 4.5 Test `ListQuery` validator: limit=20, offset=0 passes
- [ ] 4.6 Test `ListQuery` validator: limit > 100 raises ValueError
- [ ] 4.7 Test `ListQuery` validator: limit < 0 raises ValueError
- [ ] 4.8 Test `ListQuery` validator: offset < 0 raises ValueError

### Phase 5: Unit Tests for Validation Helpers

- [x] 5.1 Test `check_patient_exists_and_assigned` happy path: returns Patient when patient exists and assigned
- [x] 5.2 Test `check_patient_exists_and_assigned`: raises 404 when patient doesn't exist
- [x] 5.3 Test `check_patient_exists_and_assigned`: raises 403 when patient exists but not assigned
- [x] 5.4 Test `check_diagnostic_authorized` happy path: returns Diagnostic when doctor is author
- [x] 5.5 Test `check_diagnostic_authorized`: raises 404 when diagnostic doesn't exist
- [x] 5.6 Test `check_diagnostic_authorized`: raises 403 when doctor is not author
- [x] 5.7 Test `check_program_belongs_to_diagnostic` happy path: returns RehabProgram when match found
- [ ] 5.8 Test `check_program_belongs_to_diagnostic`: raises 404 when program doesn't exist or mismatch
- [x] 5.9 Test `check_exercise_exists` happy path: returns exercise_id when found
- [x] 5.10 Test `check_exercise_exists`: raises 404 when exercise not found
- [x] 5.11 Test `parse_pagination` happy path: returns tuple on valid input
- [x] 5.12 Test `parse_pagination`: raises 400 on invalid limit
- [x] 5.13 Test `check_program_belongs_to_diagnostic`: allows `diagnostic_id=None` for existence-only lookup before follow-up authorization

---

## PR #2: Diagnostic CRUD (Endpoints + Integration Tests)

**Scope**: Create `clinical/diagnostic_router.py` with 4 endpoints (POST, GET, GET/{id}, PATCH).  
**Base branch**: PR #1 branch  
**Estimated lines**: ~300  
**Review time**: 20 min  
**Risk**: Medium (new endpoints; RLS context injection must work; old endpoint refactoring)

### Phase 1: Diagnostic Router Setup

- [x] 1.1 Create `api/app/clinical/diagnostic_router.py` (empty file, placeholder)
- [x] 1.2 Import router, Depends, HTTPException from fastapi; Session from sqlalchemy.orm; required models, schemas, validation
- [x] 1.3 Instantiate `router = APIRouter(prefix="/diagnostics", tags=["diagnostic"])`

### Phase 2: Create Diagnostic Endpoint (POST)

- [x] 2.1 Implement `POST /diagnostics` endpoint: accept `DiagnosticIn`, require_role("medical")
  - Extract doctor_keycloak_id from principal["sub"]
  - Call `check_patient_exists_and_assigned(db, body.patient_id, doctor_keycloak_id)`
  - Create Diagnostic(patient_id, doctor_id=doctor_keycloak_id, dolencia, descripcion)
  - db.add() + db.flush() to get id
  - Return 201 DiagnosticOut
- [x] 2.2 Add error handling: catch HTTPException from validation helpers; propagate with 403/404 status

### Phase 3: List & Filter Diagnostic Endpoints (GET)

- [ ] 3.1 Implement `GET /diagnostics` endpoint: accept ListQuery (limit, offset), optional patient_id query param
  - Validate query params via ListQuery Pydantic model (auto-400 on invalid)
  - If patient_id provided: call `check_patient_exists_and_assigned(db, patient_id, doctor_keycloak_id)`
  - Build SELECT query with WHERE clause (optional patient_id filter)
  - Apply .offset(offset).limit(limit)
  - Count total via SELECT COUNT(*)
  - Return 200 PaginatedResponse[DiagnosticOut]
- [x] 3.2 Implement `GET /diagnostics/{id}` endpoint: require_role("medical"), require valid diagnostic_id
  - Call `check_diagnostic_authorized(db, diagnostic_id, doctor_keycloak_id)`
  - Return 200 DiagnosticOut on success (403/404 from validator)

### Phase 4: Update Diagnostic Endpoint (PATCH)

- [x] 4.1 Implement `PATCH /diagnostics/{id}` endpoint: accept `DiagnosticPatchIn`, require_role("medical")
  - Call `check_diagnostic_authorized(db, diagnostic_id, doctor_keycloak_id)` to verify ownership
  - Update only provided fields (dolencia and/or descripcion) on retrieved Diagnostic
  - db.flush() to apply changes
  - Return 200 DiagnosticOut on success (403/404 from validator)

### Phase 5: Router Registration & Old Endpoint Refactoring

- [x] 5.1 Update `api/app/main.py` to include diagnostic_router: `app.include_router(diagnostic_router, prefix="/api")`
- [x] 5.2 Refactor old `POST /diagnostics` in `api/app/clinical/router.py` to use DiagnosticIn schema
  - Remove inline schema definition if present
  - Import DiagnosticIn, DiagnosticOut from schemas
  - Keep endpoint live for backward compatibility (document as deprecated in docstring)
  - Or: **Decide with team** whether to remove old endpoint (breaking change) or keep both

### Phase 6: Integration Tests for Diagnostic CRUD

- [x] 6.1 Test `POST /diagnostics` happy path: 201 with valid DiagnosticIn, new Diagnostic created in DB
- [x] 6.2 Test `POST /diagnostics`: 422 Validation Error on empty dolencia (Pydantic catch)
- [ ] 6.3 Test `POST /diagnostics`: 403 when patient_id not assigned to doctor
- [x] 6.4 Test `POST /diagnostics`: 404 when patient_id doesn't exist
- [x] 6.5 Test `GET /diagnostics?limit=20&offset=0` happy path: 200 with PaginatedResponse, data array, total count
- [ ] 6.6 Test `GET /diagnostics?limit=200` (exceeds max): 400 Validation Error from ListQuery
- [ ] 6.7 Test `GET /diagnostics?offset=-1` (invalid): 400 Validation Error from ListQuery
- [x] 6.8 Test `GET /diagnostics` with RLS: create diagnostics for doctor-1 and doctor-2; query as doctor-1; assert only doctor-1's diagnostics returned
- [ ] 6.9 Test `GET /diagnostics?patient_id=<uuid>` filtering: create 5 diagnostics for patient-A and patient-B; query with patient-A filter; assert only patient-A's diagnostics returned
- [x] 6.10 Test `GET /diagnostics/{id}` happy path: 200 with DiagnosticOut matching id
- [x] 6.11 Test `GET /diagnostics/{id}`: 404 when diagnostic_id doesn't exist
- [x] 6.12 Test `GET /diagnostics/{id}`: 403 when diagnostic owned by different doctor
- [x] 6.13 Test `PATCH /diagnostics/{id}` happy path: update dolencia; 200 with updated DiagnosticOut
- [x] 6.14 Test `PATCH /diagnostics/{id}`: update descripcion only; 200 with dolencia unchanged
- [x] 6.15 Test `PATCH /diagnostics/{id}`: 403 when diagnostic owned by different doctor

---

## PR #3: Program CRUD (Endpoints + Exercise Assignment)

**Scope**: Create `clinical/program_router.py` with 5 endpoints (POST, GET, GET/{id}, POST/{id}/exercises). Refactor old endpoint.  
**Base branch**: PR #2 branch  
**Estimated lines**: ~280  
**Review time**: 20 min  
**Risk**: Medium (new endpoints; exercise assignment cross-table; old endpoint refactoring)

### Phase 1: Program Router Setup

- [x] 1.1 Create `api/app/clinical/program_router.py` (empty file, placeholder)
- [x] 1.2 Import router, Depends, HTTPException from fastapi; Session from sqlalchemy.orm; required models, schemas, validation
- [x] 1.3 Instantiate `router = APIRouter(prefix="/programs", tags=["program"])`

### Phase 2: Create Program Endpoint (POST)

- [x] 2.1 Implement `POST /programs` endpoint: accept `ProgramIn`, require_role("medical")
  - Extract doctor_keycloak_id from principal["sub"]
  - Call `check_diagnostic_authorized(db, body.diagnostic_id, doctor_keycloak_id)` to verify doctor owns the diagnostic
  - Create RehabProgram(diagnostic_id, estado="creado") [or equivalent initial state per ORM]
  - db.add() + db.flush() to get id
  - Return 201 ProgramOut
- [x] 2.2 Add error handling: propagate 403/404 from validation helpers

### Phase 3: List & Filter Program Endpoints (GET)

- [ ] 3.1 Implement `GET /programs` endpoint: accept ListQuery (limit, offset), optional diagnostic_id query param
  - Validate query params via ListQuery
  - If diagnostic_id provided: optionally verify it exists (can use check_diagnostic_authorized for ownership)
  - Build SELECT query with WHERE diagnostic_id = diagnostic_id (if provided)
  - Apply .offset(offset).limit(limit)
  - Count total
  - Return 200 PaginatedResponse[ProgramOut]
- [x] 3.2 Implement `GET /programs/{id}` endpoint: require_role("medical")
  - Query RehabProgram by id → 404 if missing
  - Verify doctor owns the diagnostic via check_diagnostic_authorized(diagnostic_id, doctor_keycloak_id)
  - Return 200 ProgramOut on success

### Phase 4: Exercise Assignment Endpoint (POST /{id}/exercises)

- [x] 4.1 Implement `POST /programs/{id}/exercises` endpoint: accept `ProgramExerciseIn`, require_role("medical")
  - Extract doctor_keycloak_id from principal["sub"]
  - Call `check_program_belongs_to_diagnostic(db, program_id, diagnostic_id_from_query_or_param)` (requires diagnostic_id)
  - Call `check_diagnostic_authorized(db, diagnostic_id, doctor_keycloak_id)` to verify ownership
  - Call `check_exercise_exists(db, body.exercise_id)`
  - Create ProgramExercise(program_id, exercise_id, pauta, estado="asignado")
  - db.add() + db.flush()
  - Return 201 ProgramExerciseOut
- [x] 4.2 Add error handling: propagate 403/404 from validators; allow duplicate exercises (per spec edge cases 804–807)

### Phase 5: Router Registration & Old Endpoint Refactoring

- [x] 5.1 Update `api/app/main.py` to include program_router: `app.include_router(program_router, prefix="/api")`
- [x] 5.2 Refactor old `POST /programs/{id}/exercises` in `api/app/clinical/router.py` to use ProgramExerciseIn schema
  - Import ProgramExerciseIn, ProgramExerciseOut from schemas
  - Keep endpoint live (or mark deprecated per team decision)

### Phase 6: Integration Tests for Program CRUD

- [ ] 6.1 Test `POST /programs` happy path: 201 with valid diagnostic_id, new RehabProgram created in DB
- [ ] 6.2 Test `POST /programs`: 403 when diagnostic owned by different doctor
- [ ] 6.3 Test `POST /programs`: 404 when diagnostic_id doesn't exist
- [ ] 6.4 Test `GET /programs?limit=20&offset=0` happy path: 200 with PaginatedResponse
- [ ] 6.5 Test `GET /programs?diagnostic_id=<uuid>` filtering: 200 with only programs for that diagnostic
- [ ] 6.6 Test `GET /programs` with RLS: create programs for diagnostic-A (doctor-1) and diagnostic-B (doctor-2); query as doctor-1; assert only doctor-1's programs returned
- [x] 6.7 Test `GET /programs/{id}` happy path: 200 with ProgramOut matching id
- [x] 6.8 Test `GET /programs/{id}`: 404 when program_id doesn't exist
- [x] 6.9 Test `GET /programs/{id}`: 403 when program's diagnostic owned by different doctor
- [x] 6.10 Test `POST /programs/{id}/exercises` happy path: 201 with valid exercise_id, new ProgramExercise created in DB
- [x] 6.11 Test `POST /programs/{id}/exercises`: 403 when program's diagnostic owned by different doctor
- [x] 6.12 Test `POST /programs/{id}/exercises`: 404 when exercise_id doesn't exist
- [x] 6.13 Test `POST /programs/{id}/exercises`: 404 when program_id doesn't exist
- [x] 6.14 Test `POST /programs/{id}/exercises` duplicate assignment: 201 allows same exercise assigned twice (per spec)

---

## Task Dependencies & Ordering

```
PR #1: Foundation (schemas.py, validation.py)
  ├─ No external dependencies
  └─ All PR #2 & PR #3 tasks depend on this

PR #2: Diagnostic CRUD (diagnostic_router.py)
  ├─ Depends on PR #1 (schemas, validation)
  └─ PR #3 integration tests may depend on working diagnostics

PR #3: Program CRUD (program_router.py)
  ├─ Depends on PR #1 (schemas, validation)
  ├─ Depends on PR #2 (diagnostic authorization)
  └─ Can be developed in parallel with PR #2 (test fixtures can mock PR #2)
```

**Recommended merge order**: PR #1 → PR #2 → PR #3 (each must pass CI before next merges)

---

## Rollback Strategy

### PR #1 Rollback
- **Safe**: New files only (schemas.py, validation.py); no modifications to existing code
- **Revert by**: `git rm api/app/clinical/schemas.py api/app/clinical/validation.py`
- **Side effects**: None (no other code imports these files yet)

### PR #2 Rollback
- **Changes**: diagnostic_router.py created; router.py refactored; main.py updated
- **Revert by**: 
  - `git rm api/app/clinical/diagnostic_router.py`
  - `git revert <PR #2 commit>` for router.py and main.py changes
  - OR: Keep old `POST /diagnostics` endpoint in router.py alongside new one (grace period)
- **Side effects**: New diagnostics API unavailable; clients must revert to old endpoint
- **Mitigation**: Run both endpoints in parallel for 1–2 sprints during migration

### PR #3 Rollback
- **Changes**: program_router.py created; router.py refactored; main.py updated
- **Revert by**:
  - `git rm api/app/clinical/program_router.py`
  - `git revert <PR #3 commit>` for router.py and main.py changes
  - OR: Keep old `POST /programs/{id}/exercises` endpoint in router.py (grace period)
- **Side effects**: New programs API unavailable; clients must revert to old endpoint
- **Mitigation**: Run both endpoints in parallel for 1–2 sprints during migration

---

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|-----------|
| RLS context injection fails | Medium | PR #2 integration test (6.8) explicitly tests RLS filtering; will catch context bugs early |
| Authorization checks bypass | Medium | Each endpoint has explicit validator (check_diagnostic_authorized, etc.); tests verify 403 responses |
| Pagination off-by-one errors | Low | Test fixtures create 25+ records; edge cases (limit=1, offset=24) verified in integration tests |
| Circular imports (validation ← router) | Low | Explicit import rule in design: validation.py has NO router imports; code review enforces this |
| Old endpoint breaking changes | High | Recommendation: Run old + new endpoints in parallel for grace period; document deprecation |
| Exercise duplicate assignment logic | Low | Per spec, duplicates allowed; integration test (6.14) verifies this behavior; no constraint applied |

---

## Implementation Notes

### Pydantic & Field Validators
- Use `@field_validator` decorator (Pydantic v2) with `mode="before"` or `mode="after"` as needed
- Dolencia/descripcion length checks are string length; no special encoding logic needed
- ListQuery validators run on every list endpoint automatically (FastAPI dependency injection)

### RLS Context Injection
- **No changes needed to get_db()**: Already calls `_apply_rls(session)` which injects `app.user` and `app.role` into PostgreSQL session
- **Handler layer**: Each endpoint that queries depends on `get_db`, which automatically sets context
- **Database layer**: PostgreSQL RLS policies (via `current_setting('app.user')`) filter rows based on this context
- **Defense in depth**: Explicit check_diagnostic_authorized() call provides fail-fast + clear error messages (in addition to RLS filter)

### Transaction Management
- **Implicit commit**: FastAPI's `with session.begin()` in get_db() auto-commits on successful return
- **db.flush()**: Call after db.add() to get generated IDs without committing; allows serialization before implicit commit
- **No explicit rollback needed**: HTTPException causes automatic rollback; response built from ORM objects with expire_on_commit=False

### Testing Approach
- **Unit tests** (Phase 4–5, PR #1): Mock database; verify validators and helpers raise correct HTTPException types
- **Integration tests** (Phase 6, PR #2–3): Use TestClient; create real fixtures in test DB; verify endpoint behavior + RLS filtering
- **Fixtures**: Use pytest fixtures for patient + diagnostic + program setup; reuse across tests

---

## Estimated Timeline (1 Developer)

| Phase | Tasks | Time | Notes |
|-------|-------|------|-------|
| PR #1 | 1.1–5.12 (30 tasks) | 3–4 hours | Schemas + validators + 12 unit tests; straightforward |
| PR #2 | 1.1–6.15 (31 tasks) | 2–3 hours | Diagnostic CRUD + 15 integration tests; RLS test (6.8) is key |
| PR #3 | 1.1–6.14 (30 tasks) | 2–3 hours | Program CRUD + 14 integration tests; exercise duplication behavior verified |
| **Total** | 91 tasks | **7–10 hours** | Includes writing + testing; CI runs in parallel |

---

## Next Steps (After Task Breakdown)

1. **PR #1 Ready for sdd-apply**: Implement schemas.py + validation.py + unit tests
2. **PR #2 Ready for sdd-apply**: Implement diagnostic_router.py + integration tests (after PR #1 merges)
3. **PR #3 Ready for sdd-apply**: Implement program_router.py + integration tests (after PR #2 merges)
4. **Deprecation Plan** (async): Coordinate with frontend/mobile teams on old endpoint migration timeline

---

## Sign-Off

- **Task count**: 91 total (30 PR #1, 31 PR #2, 30 PR #3)
- **Artifact location**: `openspec/tasks/api-medico-diagnostico-programa.md`
- **Ready for implementation**: Yes
- **Chained PR strategy**: Stacked-to-main (auto-chain, no decision needed)
