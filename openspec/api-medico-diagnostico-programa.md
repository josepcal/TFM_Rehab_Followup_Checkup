# Proposal: Complete Doctor API View (UC-01 Diagnostic + UC-02 Rehab Program)

**Change Name**: `api-medico-diagnostico-programa`  
**Date**: 2026-06-11  
**Status**: Approved for Specification  

---

## Intent

The clinical workflow requires doctors to search for patient diagnostics, create new diagnoses with rehab programs, and assign exercises to those programs. Currently, the API has **partial CRUD** (5 endpoints, no validation, no schemas, 1:1 diagnostic-program coupling). This change completes the doctor's clinical view by adding **validation, response schemas, pagination, and explicit program creation**, enabling AC-01–AC-05 to be fully satisfied without breaking existing endpoints.

---

## Scope

### In Scope

**CRUD Endpoints**:
- ✅ `GET /diagnostics` — List diagnostics authored by the authenticated doctor (paginated)
- ✅ `GET /diagnostics/{id}` — Retrieve single diagnostic detail
- ✅ `PATCH /diagnostics/{id}` — Update diagnostic fields (description, history, symptoms)
- ✅ `POST /programs` — Explicit rehab program creation (decouple from diagnostic)
- ✅ `GET /programs` — List rehab programs for diagnostics owned by the authenticated doctor (paginated)
- ✅ `GET /programs/{id}` — Retrieve program detail with linked exercises
- ✅ `GET /programs/{id}/exercises` — List exercises in program (with frequency/pauta)

**Validation & Schemas**:
- ✅ Pydantic request/response schemas for all endpoints (type safety, OpenAPI spec)
- ✅ FK validation: Patient exists, authenticated medical principal resolves to `clinical.doctor`, Exercise exists in catalog
- ✅ Doctor-scoped authorization: Explicit check before query (fail fast with 403 instead of leaking another doctor's rows)
- ✅ Business rule checks: Doctor must author/own the diagnostic context, program must belong to diagnostic

**Error Handling**:
- ✅ 404 when resource not found (patient, diagnostic, program, exercise)
- ✅ 403 when access denied (principal cannot resolve to doctor, not doctor of diagnostic)
- ✅ 422 when validation fails (missing fields, invalid FK, business rule violation)
- ✅ Clear error messages (e.g., "Patient not found", "Doctor not assigned to this patient")

**Pagination**:
- ✅ `GET /diagnostics?limit=20&offset=0` for diagnostic list
- ✅ `GET /programs?limit=20&offset=0` for program list
- ✅ Max limit: 100 (prevents abuse, matches SLA requirements)
- ✅ Response envelope: `{ "data": [...], "total": N, "limit": 20, "offset": 0 }`

### Out of Scope

- ❌ **Attestation signature generation** — ADR-0012 requires simple attestation (identity + timestamp + hash). UI will compute hash; API stores `signature`, `signed_at`, `content_hash` as-is. Crypto validation deferred.
- ❌ **Audit logging** — `audit.event_log` table not exposed; logging hook deferred to post-MVP (FR-15)
- ❌ **Patient view** — Endpoints with `role=patient` filtering. Patient-facing diagnostic/program search is a separate change.
- ❌ **Soft deletion** — `PATCH /diagnostics/{id}?action=delete` / `PATCH /programs/{id}?action=delete`. `IS_DELETED` flag exists in model but endpoint not needed for UC-01/UC-02.
- ❌ **Exercise creation** — `POST /catalog/exercises` (technician role, separate change)

---

## Capabilities

> This section defines the spec-level requirements. See `openspec/specs/` for existing capability specs.

### New Capabilities

- `doctor-diagnostic-crud`: Doctor can search, retrieve, and update diagnostics they authored
- `doctor-program-crud`: Doctor can create, search, and retrieve rehab programs (decoupled from diagnostics)
- `doctor-program-exercise-list`: Doctor can list exercises assigned to a program with frequency/pauta
- `api-schemas-validation`: All clinical API endpoints use Pydantic request/response schemas with FK and RLS validation

### Modified Capabilities

- `diagnostic-creation-rls`: Change from auto-creating linked `RehabProgram` to optional linking. Program creation becomes explicit via `POST /programs` endpoint.

---

## Approach

### Architecture: 3-Router Split

Refactor `clinical/` module into domain-focused routers:

```
api/app/clinical/
├── __init__.py           # Register patient_router, diagnostic_router, program_router
├── models.py             # Existing: Patient, Diagnostic, RehabProgram, ProgramExercise, etc.
├── schemas.py            # NEW: Pydantic In/Out models for all CRUD endpoints
├── validation.py         # NEW: Helper functions (check_patient_assigned, check_exercise_exists, etc.)
├── patient_router.py     # Refactored: POST/GET /patients, /patients/claim (existing)
├── diagnostic_router.py  # NEW: GET /diagnostics, GET /diagnostics/{id}, PATCH /diagnostics/{id}
└── program_router.py     # NEW: POST/GET /programs, GET /programs/{id}, GET /programs/{id}/exercises
```

### Implementation Sequence (3 PRs < 400 lines each)

#### PR #1: Foundation — Schemas + Validation
- **Files**: `schemas.py`, `validation.py`
- **Scope**: No endpoint changes, no DB changes
- **Deliverables**:
  - Pydantic models: `PatientOut`, `DiagnosticIn`, `DiagnosticOut`, `ProgramIn`, `ProgramOut`, `ProgramExerciseOut`, `PaginatedResponse[T]`
  - Validation helpers: `check_patient_exists_and_assigned()`, `check_exercise_exists()`, `check_program_belongs_to_diagnostic()`
  - Refactor existing endpoints to use new schemas (optional for this PR, can be done in PR #2 incremental)
- **Tests**: Schema serialization, validation function logic
- **Risk**: Low (no behavior change)
- **Estimated lines**: 200–250

#### PR #2: Diagnostic CRUD
- **Files**: `diagnostic_router.py`, refactored `patient_router.py`
- **Dependencies**: PR #1 (schemas + validation)
- **Deliverables**:
  - `GET /diagnostics?patient_id=<uuid>&limit=20&offset=0` — List diagnostics authored by the authenticated doctor, optionally filtered by patient
  - `GET /diagnostics/{id}` — Single diagnostic detail
  - `PATCH /diagnostics/{id}` — Update description, history, symptoms (regenerate `content_hash` if changed)
  - Refactor `POST /diagnostics` to use new schemas and validation
  - All endpoints use doctor-scoped checks through `clinical.app_user.external_subject` + `clinical.doctor.doctor_id` before query
- **Tests**: AC-01 (search diagnostic), AC-03 (create diagnostic), auth tests (403 if doctor identity cannot resolve / not author)
- **Risk**: Medium (changes POST behavior, must maintain backward compat)
- **Estimated lines**: 280–320

#### PR #3: Program CRUD
- **Files**: `program_router.py`
- **Dependencies**: PR #2 (diagnostic routers established)
- **Deliverables**:
  - `POST /programs` — Explicit program creation (decoupled from diagnostic)
  - `GET /programs?diagnostic_id=<uuid>&patient_id=<uuid>&limit=20&offset=0` — List programs
  - `GET /programs/{id}` — Program detail with linked diagnostic metadata
  - `GET /programs/{id}/exercises` — List assigned exercises with frequency/pauta
  - Refactor `POST /programs/exercises` to use new schemas and validation
  - All endpoints enforce RLS + foreign key checks
- **Tests**: AC-04 (create program), AC-05 (assign exercise), AC-06 (search program), auth tests
- **Risk**: Medium (decouples 1:1 relationship, must handle existing 1:1 programs gracefully)
- **Estimated lines**: 300–340

### Validation Logic

**Every POST/PATCH endpoint follows this pattern**:
```python
@router.post("/diagnostics")
def create_diagnostic(
    data: DiagnosticIn,
    db: Session = Depends(get_db),
    principal: dict = Depends(get_principal),
):
    # 1. Check doctor is authenticated
    doctor = check_doctor_exists(db, principal["sub"])
    
    # 2. Check patient exists and is assigned to doctor
    patient = check_patient_exists_and_assigned(db, data.patient_id, doctor.id)
    
    # 3. Create entity
    diagnostic = Diagnostic(
        patient_id=data.patient_id,
        doctor_id=doctor.id,
        dolencia=data.dolencia,
        descripcion=data.descripcion,
        history=data.history or "",
        symptoms=data.symptoms or "",
    )
    
    # 4. Return response schema
    db.add(diagnostic)
    db.commit()
    db.refresh(diagnostic)
    return DiagnosticOut.model_validate(diagnostic)
```

### Pagination Implementation

**Request**:
```python
class ListQuery(BaseModel):
    limit: int = 20  # Default 20
    offset: int = 0
    
    @field_validator("limit")
    def limit_max_100(cls, v):
        if v > 100:
            raise ValueError("limit must be ≤ 100")
        return v
```

**Response**:
```python
class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    total: int
    limit: int
    offset: int
```

**Usage in endpoint**:
```python
@router.get("/diagnostics")
def list_diagnostics(
    limit: int = 20,
    offset: int = 0,
    patient_id: UUID | None = None,
    db: Session = Depends(get_db),
    principal: dict = Depends(get_principal),
):
    doctor = check_doctor_exists(db, principal["sub"])
    query = db.query(Diagnostic).filter(Diagnostic.doctor_id == doctor.id)
    
    if patient_id:
        check_patient_exists_and_assigned(db, patient_id, doctor.id)
        query = query.filter(Diagnostic.patient_id == patient_id)
    
    total = query.count()
    data = query.limit(limit).offset(offset).all()
    
    return PaginatedResponse[DiagnosticOut](
        data=[DiagnosticOut.model_validate(d) for d in data],
        total=total,
        limit=limit,
        offset=offset,
    )
```

---

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/app/clinical/` | New files + refactor | Add `schemas.py`, `validation.py`, split router into 3 files |
| `api/app/main.py` | Modified | Register 3 clinical routers instead of 1 |
| `api/app/db.py` | No change | RLS context already injected; validation layer uses it |
| `api/app/auth.py` | No change | JWT/Keycloak integration unchanged |
| `api/app/catalog/` | No change | Catalog queries already return dicts; can migrate schemas in future |
| OpenAPI spec | Enhanced | New endpoints + schemas in `/docs` |

---

## Tradeoffs

### 3 PRs vs. 1 Monolithic PR

**Decision**: 3 PRs (Foundation → Diagnostic → Program)

**Tradeoff**:
- ❌ **3× ceremony**: Each PR requires CI, linting, review round (3 reviewer touchpoints)
- ✅ **Focused reviews**: \< 350 lines per PR → reviewers can provide thorough feedback
- ✅ **Independent rollback**: If diagnostic PR breaks, can revert without losing program work
- ✅ **Incremental feedback**: Users/stakeholders can test/validate after each PR

**Reasoning**: On a team, focused PRs reduce merge conflicts and cognitive load. For solo development, still worth it to maintain review quality and enable incremental testing.

### Pagination Now vs. Later

**Decision**: Add pagination now (offset/limit with max=100)

**Tradeoff**:
- ❌ **Slightly more code**: ~30 lines per endpoint for pagination logic
- ✅ **Scalability**: Without pagination, API breaks when doctor has 1000+ diagnostics
- ✅ **Hard to retrofit**: Adding pagination later requires API versioning or client changes
- ✅ **SLA compliance**: Max=100 prevents O(N) queries that could time out

**Reasoning**: Pagination is a contract between API and client. Adding it post-launch is breaking. Simpler to include now.

### Validation in API vs. RLS Only

**Decision**: Explicit validation in API + RLS as defense-in-depth

**Tradeoff**:
- ❌ **Duplication**: Validation logic mirrors RLS policies
- ✅ **Fail-fast**: API returns 403 immediately instead of 0 rows (better UX)
- ✅ **Clear errors**: "Doctor not assigned to this patient" vs. silent empty array
- ✅ **Security**: RLS still enforces data boundaries; API validation is first line

**Reasoning**: RLS is database-enforced and correct, but opaque. Explicit API validation gives users actionable feedback.

### Diagnostic-Program Coupling

**Decision**: Decouple in PR #3 with optional backward compatibility

**Current**:
```python
POST /diagnostics → auto-creates RehabProgram (1:1)
```

**New**:
```python
POST /diagnostics → creates Diagnostic only
POST /programs → creates RehabProgram (links to existing Diagnostic)
```

**Tradeoff**:
- ❌ **Breaking change for automation**: Scripts expecting `POST /diagnostics` to return `program_id` will break
- ✅ **Flexible**: Can create N programs for 1 diagnostic (per SDD §7.1)
- ✅ **Explicit**: Doctor explicitly decides to create a program (instead of implicit)

**Mitigation**: 
- Old `POST /diagnostics` endpoint **keeps** auto-creating program for backward compat
- New `POST /programs` is the recommended path going forward
- Document in PR: "Diagnostic-only creation now recommended; old endpoint deprecated but functional"

---

## Success Criteria

- [ ] **AC-01**: Doctor can search for diagnostic history of assigned patient via `GET /diagnostics?patient_id=<uuid>`
- [ ] **AC-03**: Doctor can create diagnostic via `POST /diagnostics` with validation (FK, RLS, business rules)
- [ ] **AC-04**: Doctor can create rehab program via `POST /programs` with explicit diagnostic link
- [ ] **AC-05**: Doctor can assign exercise to program via `POST /programs/{id}/exercises` with validation
- [ ] **AC-06**: Doctor can search for rehab programs via `GET /programs?patient_id=<uuid>`
- [ ] **All endpoints use Pydantic schemas**: Request/response models defined, OpenAPI spec complete
- [ ] **All endpoints validate FK + RLS**: 404 for missing resource, 403 for unauthorized access
- [ ] **Pagination works on list endpoints**: `?limit=X&offset=Y` with max=100
- [ ] **Existing endpoints not broken**: Old `POST /diagnostics` still works (auto-creates program)
- [ ] **Error responses are clear**: 422 includes field-level errors, 403 explains why access denied

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **RLS silent failures** | Medium | Doctor thinks clinical data is visible, but gets 0 results | Add explicit doctor identity/ownership check before query; always return 403 if identity resolution fails |
| **Backward compat break** | Low | Automation scripts expecting `POST /diagnostics` to return `program_id` break | Keep old endpoint functional; return both diagnostic and program IDs |
| **No test suite** | High | Breaking changes undetected until production | Add integration tests to each PR; mock RLS context via SQLAlchemy override |
| **Pagination off-by-one** | Low | Cursor skips/duplicates records on update | Use offset/limit (stateless) instead of cursor; document limit=100 max |
| **Schema validation too strict** | Medium | Required fields in schema don't match DB defaults | Use Pydantic `Field(default=None)` for optional fields; test with empty payloads |

---

## Rollback Plan

**If PR #1 (Foundation) breaks**:
- Revert commit; existing router continues working
- No data loss (schemas don't touch DB)

**If PR #2 (Diagnostic CRUD) breaks**:
- Revert commit; old `POST /diagnostics` still works
- Risk: Any clients already calling new `GET /diagnostics` endpoint will get 404. **Mitigation**: New endpoints only deployed after full test, not in partial state.

**If PR #3 (Program CRUD) breaks**:
- Revert commit; old `POST /programs/exercises` still works
- Existing diagnostics still have linked programs (1:1 relationship intact)

**Full rollback** (all 3 PRs):
- Delete `diagnostic_router.py`, `program_router.py`, remove from registration in `main.py`
- Keep `schemas.py` and `validation.py` (no API changes, only internal use)
- Restore `patient_router.py` to pre-PR state if modified

**Data rollback**: No schema changes, no migrations needed. All new tables/columns are within `clinical` schema which is managed by SQLAlchemy.

---

## Dependencies

### Pre-requisites

- ✅ PostgreSQL 15+ with RLS enabled (existing)
- ✅ Keycloak/OIDC IdP configured (existing)
- ✅ `catalog.rehab_exercise` table seeded (required for FK validation)
- ✅ `clinical.care_assignment` RLS policy functional (existing)

### Internal Module Dependencies

- ✅ `api.app.db.get_db()` — Session + RLS context injection
- ✅ `api.app.auth.get_principal()` — JWT principal extraction
- ✅ `api.app.clinical.models` — SQLAlchemy ORM models (Patient, Diagnostic, etc.)
- ✅ `api.app.catalog.models.RehabExercise` — FK reference for exercises

### Integration Points

- **OpenAPI schema generation**: Pydantic models automatically appear in `/docs`
- **RLS enforcement**: No code changes; SQL queries automatically filtered by `app.identity_id` context
- **Error response format**: Must align with existing 404/403/422 conventions (see `api/app/main.py` exception handlers)

---

## Open Questions

None at this time. Exploration confirmed:
- ✅ RLS infrastructure working in existing endpoints
- ✅ Data model complete (SDD §7)
- ✅ User has approved approach (3 PRs, pagination now, simple attestation)

---

## Next Steps

1. **Specification phase** (`sdd-spec`): Write detailed requirements for schemas, validation, pagination behavior
2. **Design phase** (`sdd-design`): Finalize API contract (request/response shapes, error codes)
3. **Implementation** (`sdd-apply`): Execute 3 PRs in sequence with integration tests
4. **Verification** (`sdd-verify`): Manual testing against acceptance criteria + acceptance test suite

---

**Artifacts**:
- `openspec/api-medico-diagnostico-programa.md` (this file)
- Previous: `openspec/explore/api-medico-diagnostico-programa.md`
