# Design: Doctor Diagnostic & Program Management API


**Change**: `api-medico-diagnostico-programa`  
**Date**: 2026-06-11  
**Status**: Technical Design

---

## Technical Approach

This design delivers three PR-sized changes to the clinical API:
- **PR #1 (Foundation)**: Establish typed schemas and authorization helpers
- **PR #2 (Diagnostic CRUD)**: Diagnostic creation, listing, detail, and updates with RLS
- **PR #3 (Program CRUD)**: Program and exercise assignment with ownership checks

The architecture decouples endpoint handlers from validation logic, enabling consistent error handling and reuse across 8 endpoints. RLS enforcement is delegated to PostgreSQL (via `set_config`) and authorization helpers perform fail-fast checks at the handler layer.

---

## Architecture Decisions

### Decision: Pydantic Schemas in Dedicated Module

**Choice**: Create `clinical/schemas.py` with all request/response types (DiagnosticIn, DiagnosticOut, etc.)

**Alternatives considered**:
- Inline models in router.py (loses reusability, increases cognitive load)
- Shared schema registry (premature; only 6 models needed)

**Rationale**: 
- Pydantic models ARE the API contract; separate module improves discoverability and testability
- Centralized validation rules (e.g., dolencia 1–500 chars) live in one place
- Router imports from schemas, not vice versa → no circular dependencies

---

### Decision: Validation Helpers as Pure Functions

**Choice**: Create `clinical/validation.py` with 5 helper functions (check_patient_exists_and_assigned, check_exercise_exists, etc.). Each function raises HTTPException directly.

**Alternatives considered**:
- Inline checks in each endpoint (violates DRY; 73 validations across 8 endpoints)
- Decorator-based validation (opaque error handling; hard to test)
- Database constraints only (shifts responsibility to DB; slower error feedback to client)

**Rationale**:
- Testable in isolation (mock db, verify exception type and status code)
- Fail-fast semantics: check_patient raises 403 before any writes
- Reusable across POST/PATCH/GET operations
- Error messages are consistent and API-visible (not just logs)

---

### Decision: Decouple Diagnostic Creation from Program Creation

**Choice**: POST /diagnostics creates ONLY the diagnostic (no auto-created RehabProgram). Programs are created separately via POST /programs.

**Alternatives considered**:
- Auto-create program (old endpoint behavior: keeps backward compat)
- Allow optional program creation on diagnostic POST (mixed responsibility)

**Rationale**:
- **Single Responsibility**: diagnostic is a clinical assessment; program is a treatment plan
- **Flexible workflows**: doctor may assess multiple diagnostics before committing to a program
- **Backward compat**: old endpoint stays in place; new endpoint is opt-in
- **Specs require this**: Foundation-C-08 explicitly states "MUST NOT auto-create RehabProgram"

---

### Decision: RLS Context via Postgres set_config, Not ORM Filters

**Choice**: Each endpoint calls `get_db` (which injects context via `_apply_rls`). Queries use SQLAlchemy select() with explicit `.where()` clauses for authorization checks; RLS policy on the database enforces access control at the row level.

**Alternatives considered**:
- Filter in Python (ORM filters in every query)
- Trust RLS policy alone (no explicit checks in handlers)
- Custom query builder (increases complexity)

**Rationale**:
- RLS is the source of truth (enforced at DB layer)
- Explicit handler checks provide defense-in-depth and clear error messages
- SQLAlchemy select() with `.where()` is discoverable in code review
- get_db already handles set_config → handlers inherit the context for free

---

### Decision: N:1 Diagnostic-to-Program Relationship (No Unique Constraint)

**Choice**: Multiple programs per diagnostic allowed. No unique constraint on (diagnostic_id, program_id). Exercise assignment also allows duplicates (same exercise, same program).

**Alternatives considered**:
- Unique constraint on diagnostic_id (force 1:1)
- Unique constraint on (program_id, exercise_id) (prevent duplicate exercises)

**Rationale**:
- Specs (edge cases 614–617, 804–807) explicitly allow duplicates
- Clinical workflows may need parallel programs (e.g., acute + preventive)
- Exercise re-assignment with different pauta is valid (frequency changes)
- Database constraints can be added later if business rules tighten

---

### Decision: Pagination Implemented in Handlers (Not ORM Hooks)

**Choice**: Each list endpoint accepts `limit` and `offset` as query params, validates via ListQuery Pydantic model, then applies `.offset().limit()` in SQLAlchemy query.

**Alternatives considered**:
- Auto-paginate via middleware (opaque to handlers)
- Use `PaginatedResponse[T]` generic in all returns (already in design)

**Rationale**:
- Explicit: each list endpoint controls its own query shape and filters
- Testable: mock pagination edge cases without complex fixtures
- Composable: easy to add sorting, filtering per endpoint later

---

## Data Flow

### Diagnostic Creation Flow

```
POST  
  │
  ├─ Parse JSON → DiagnosticIn (Pydantic validates dolencia, descripcion)
  │
  ├─ Extract principal["sub"] from JWT (require_role("medical"))
  │
  ├─ check_patient_exists_and_assigned(db, patient_id, principal["sub"])
  │   ├─ Query Patient by id → 404 if missing
  │   └─ Query CareAssignment(patient_id, doctor_keycloak_id) → 403 if missing
  │
  ├─ Create Diagnostic(patient_id, doctor_id=principal["sub"], dolencia, descripcion)
  │
  ├─ db.add() → db.flush() → get id
  │
  └─ Return 201 DiagnosticOut
```

### Program Assignment Flow

```
POST /programs/{id}/exercises
  │
  ├─ Parse JSON → ProgramExerciseIn
  │
  ├─ check_program_belongs_to_diagnostic(..., program_id, diagnostic_id)
  │   └─ Query RehabProgram(id=program_id, diagnostic_id=diagnostic_id) → 404 if mismatch
  │
  ├─ Verify doctor owns diagnostic via check_diagnostic_authorized(...)
  │   └─ Query Diagnostic.doctor.keycloak_id == principal["sub"] → 403 if not author
  │
  ├─ check_exercise_exists(db, exercise_id)
  │   └─ Query catalog.rehab_exercise by id → 404 if missing
  │
  ├─ Create ProgramExercise(program_id, exercise_id, pauta, estado="asignado")
  │
  └─ Return 201 ProgramExerciseOut
```

### List Diagnostics with RLS

```
GET /diagnostics?patient_id=<uuid>&limit=20&offset=0
  │
  ├─ Parse & validate ListQuery (limit ≤ 100, offset ≥ 0)
  │
  ├─ If patient_id provided:
  │   └─ check_patient_exists_and_assigned(db, patient_id, principal["sub"])
  │
  ├─ Build query:
  │   SELECT diagnostic.* 
  │   FROM clinical.diagnostic
  │   WHERE diagnostic.patient_id = patient_id (or skip if not filtered)
  │   OFFSET 20 LIMIT 20
  │   (RLS policy also filters: only doctor's assigned patients)
  │
  ├─ Count total via SELECT COUNT(*)
  │
  └─ Return 200 PaginatedResponse[DiagnosticOut]
```

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/app/clinical/schemas.py` | Create | Pydantic models: DiagnosticIn/Out, ProgramIn/Out, ProgramExerciseIn/Out, ListQuery, PaginatedResponse[T], PatientOut, ErrorResponse |
| `api/app/clinical/validation.py` | Create | Pure functions: check_patient_exists_and_assigned, check_exercise_exists, check_diagnostic_authorized, check_program_belongs_to_diagnostic, parse_pagination |
| `api/app/clinical/diagnostic_router.py` | Create | POST/GET/GET/{id}/PATCH /diagnostics endpoints |
| `api/app/clinical/program_router.py` | Create | POST/GET/GET/{id}/POST/{id}/exercises endpoints |
| `api/app/clinical/router.py` | Modify | Remove old DiagnosticIn/AssignExerciseIn; refactor create_diagnostic (decouple program); keep /patients endpoints |
| `api/app/main.py` | Modify | Include diagnostic_router and program_router (already includes clinical_router) |

---

## Interfaces & Contracts

### Pydantic Request Models

```python
class DiagnosticIn(BaseModel):
    patient_id: UUID
    dolencia: str  # 1-500 chars, required
    descripcion: str | None = None  # 0-5000 chars, optional
    
    @field_validator("dolencia")
    def dolencia_length(cls, v):
        if not v or len(v) < 1 or len(v) > 500:
            raise ValueError("dolencia must be 1-500 characters")
        return v
    
    @field_validator("descripcion")
    def descripcion_length(cls, v):
        if v and len(v) > 5000:
            raise ValueError("descripcion must be ≤ 5000 characters")
        return v

class DiagnosticPatchIn(BaseModel):
    dolencia: str | None = None  # 1-500 chars if provided
    descripcion: str | None = None  # 0-5000 chars if provided
    # Validators same as DiagnosticIn

class ProgramIn(BaseModel):
    diagnostic_id: UUID

class ProgramExerciseIn(BaseModel):
    exercise_id: UUID
    pauta: str | None = None

class ListQuery(BaseModel):
    limit: int = 20
    offset: int = 0
    
    @field_validator("limit")
    def limit_max_100(cls, v):
        if v < 0 or v > 100:
            raise ValueError("limit must be 0-100")
        return v
    
    @field_validator("offset")
    def offset_non_negative(cls, v):
        if v < 0:
            raise ValueError("offset must be ≥ 0")
        return v
```

### Response Models

```python
class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    total: int
    limit: int
    offset: int

class DiagnosticOut(BaseModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    dolencia: str
    descripcion: str | None
    signature: str | None
    signed_at: datetime | None
    created_at: datetime
    
    class Config:
        from_attributes = True
```

### Validation Helper Signatures

```python
def check_patient_exists_and_assigned(db: Session, patient_id: UUID, doctor_keycloak_id: str) -> Patient:
    """Raises HTTPException(403) if not assigned; HTTPException(404) if patient missing."""

def check_exercise_exists(db: Session, exercise_id: UUID) -> UUID:
    """Raises HTTPException(404) if exercise doesn't exist in catalog."""

def check_diagnostic_authorized(db: Session, diagnostic_id: UUID, doctor_keycloak_id: str) -> Diagnostic:
    """Raises HTTPException(404) if diagnostic missing; HTTPException(403) if not author."""

def check_program_belongs_to_diagnostic(db: Session, program_id: UUID, diagnostic_id: UUID) -> RehabProgram:
    """Raises HTTPException(404) if program doesn't belong to diagnostic."""

def parse_pagination(limit: int, offset: int) -> tuple[int, int]:
    """Validates bounds; raises HTTPException(400) on invalid input."""
```

---

## Error Handling & HTTP Mapping

| Scenario | HTTP Status | Code | Message | Handler |
|----------|-------------|------|---------|---------|
| Patient not found | 404 | NOT_FOUND | "Patient not found" | check_patient_exists_and_assigned |
| Patient not assigned | 403 | UNAUTHORIZED | "Patient not assigned to you" | check_patient_exists_and_assigned |
| Diagnostic not found | 404 | NOT_FOUND | "Diagnostic not found" | check_diagnostic_authorized |
| Not diagnostic author | 403 | UNAUTHORIZED | "You are not the author of this diagnostic" | check_diagnostic_authorized |
| Exercise not found | 404 | NOT_FOUND | "Exercise not found in catalog" | check_exercise_exists |
| Program not found | 404 | NOT_FOUND | "Program not found" | get_program_by_id |
| Limit exceeds 100 | 400 | BAD_REQUEST | "limit must be 0-100" | ListQuery validator |
| Offset negative | 400 | BAD_REQUEST | "offset must be ≥ 0" | ListQuery validator |
| Pydantic validation error | 422 | VALIDATION_ERROR | Field-specific message | FastAPI auto-conversion |
| Malformed JSON | 400 | BAD_REQUEST | "Invalid request" | FastAPI JSON parser |

---

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| **Unit: Validators** | Pydantic field validators (dolencia length, limit bounds) | Construct models with valid/invalid data; assert ValueError raised |
| **Unit: Helpers** | check_patient_exists_and_assigned, check_diagnostic_authorized, etc. | Mock db queries; assert HTTPException(403/404) raised at correct points |
| **Integration: Handlers** | POST /diagnostics happy path + sad paths (403, 404, 422) | FastAPI TestClient; mock principal; verify status codes and response bodies |
| **Integration: Pagination** | ListQuery validation + OFFSET/LIMIT in query | Create 25 diagnostics; test limit/offset combos; verify total, data length |
| **Integration: RLS** | GET /diagnostics only returns owned diagnostics | Create diagnostics for different doctors; query as doctor-1; assert doctor-2's diagnostics absent |
| **E2E: Workflows** | Full diagnostic→program→exercise lifecycle | Create diagnostic, create program, assign exercise; verify IDs chain correctly |

### Test Fixtures (Pseudocode)

```python
@pytest.fixture
def mock_principal():
    """Simulates JWT principal from Keycloak."""
    return {"sub": "doc-001", "role": "medical"}

@pytest.fixture
def db_with_patient_and_assignment(db):
    """Pre-populated db with Patient + CareAssignment."""
    patient = Patient(id=uuid.uuid4(), nombre="Test")
    db.add(patient)
    db.flush()
    assignment = CareAssignment(patient_id=patient.id, doctor_keycloak_id="doc-001")
    db.add(assignment)
    db.commit()
    return db, patient.id

def test_create_diagnostic_happy_path(client, mock_principal, db_with_patient_and_assignment):
    db, patient_id = db_with_patient_and_assignment
    response = client.post("/diagnostics", 
        json={"patient_id": str(patient_id), "dolencia": "dolor"},
        headers={"Authorization": "Bearer <token>"}
    )
    assert response.status_code == 201
    assert response.json()["dolencia"] == "dolor"

def test_create_diagnostic_patient_not_assigned(client, mock_principal, db):
    unassigned_patient_id = uuid.uuid4()
    response = client.post("/diagnostics",
        json={"patient_id": str(unassigned_patient_id), "dolencia": "dolor"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Patient not assigned to you"
```

---

## RLS Context Injection

The existing `get_db()` dependency in `db.py` already handles RLS context:

```python
def get_db(principal: dict = Depends(current_principal)):
    session = SessionLocal()
    try:
        with session.begin():
            _apply_rls(session)  # Injects app.user, app.role
            yield session
    finally:
        session.close()
```

**No handler changes needed**: Just depend on `get_db`, which automatically sets PostgreSQL session variables. Database RLS policies then filter rows based on `current_setting('app.user')`.

---

## Transaction Management

- **Implicit**: FastAPI's `with session.begin()` auto-commits on successful return; rolls back on exception
- **Explicit writes**: Use `db.add()` + `db.flush()` to get generated IDs before return
- **No manual rollback needed**: HTTPException causes implicit rollback; response is built from ORM objects (expire_on_commit=False)

Example:
```python
@router.post("/diagnostics")
def create_diagnostic(body: DiagnosticIn, principal=Depends(...), db=Depends(get_db)):
    check_patient_exists_and_assigned(db, body.patient_id, principal["sub"])
    d = Diagnostic(patient_id=body.patient_id, doctor_id=principal["sub"], 
                   dolencia=body.dolencia, descripcion=body.descripcion)
    db.add(d)
    db.flush()  # Get id without committing
    return DiagnosticOut.from_orm(d)  # Serialize before implicit commit
```

---

## Modularity & Imports

### Router Organization

```
api/app/clinical/
├── __init__.py (empty or exports)
├── models.py (SQLAlchemy ORM)
├── schemas.py (Pydantic request/response)
├── validation.py (pure helper functions)
├── router.py (old endpoints: /patients, /patients/claim)
├── diagnostic_router.py (new: /diagnostics CRUD)
└── program_router.py (new: /programs CRUD + exercises)
```

### Import Graph

```
diagnostic_router.py
  ├─ from clinical.models import Diagnostic, Patient, CareAssignment
  ├─ from clinical.schemas import DiagnosticIn, DiagnosticOut, ListQuery, PaginatedResponse
  └─ from clinical.validation import check_patient_exists_and_assigned, check_diagnostic_authorized

program_router.py
  ├─ from clinical.models import RehabProgram, ProgramExercise, Diagnostic
  ├─ from clinical.schemas import ProgramIn, ProgramOut, ProgramExerciseIn, ProgramExerciseOut, ListQuery, PaginatedResponse
  └─ from clinical.validation import check_diagnostic_authorized, check_program_belongs_to_diagnostic, check_exercise_exists

validation.py
  ├─ from clinical.models import Patient, Diagnostic, RehabProgram
  └─ NO imports from routers (breaks circular dependency)

main.py
  ├─ from clinical.router import router as clinical_router
  ├─ from clinical.diagnostic_router import router as diagnostic_router
  └─ from clinical.program_router import router as program_router
```

**Key rule**: validation.py has NO router imports. Routers import validation, not vice versa.

---

## Rollback Plan

### PR #1 (Foundation)
- **Safe**: Creates new files (schemas.py, validation.py); no changes to existing routers
- **Rollback**: Delete created files; no schema migrations needed

### PR #2 (Diagnostic CRUD)
- **Changes**: diagnostic_router.py (new), router.py (old create_diagnostic refactored)
- **Rollback**: Delete diagnostic_router.py; revert router.py to old create_diagnostic + auto-program
- **Risk**: If old endpoint is live, keep it alongside new one for grace period

### PR #3 (Program CRUD)
- **Changes**: program_router.py (new), router.py (old assign_exercise refactored)
- **Rollback**: Delete program_router.py; revert router.py to old assign_exercise
- **Risk**: Clients must migrate to new endpoints before shutdown

---

## Open Questions

- [ ] Should old `/diagnostics` POST endpoint remain for backward compatibility, or is migration to new endpoint acceptable?
- [ ] Are duplicate exercise assignments (same program, same exercise, different pauta) a valid clinical workflow?
- [ ] Should pagination be cursor-based (stable across inserts) instead of offset/limit?
- [ ] Do we need soft-delete on Diagnostic/RehabProgram/ProgramExercise, or is hard-delete acceptable?

---

## Summary of PR Breakdown

| PR | Files | Scope | Deps | Reviewable Size |
|----|-------|-------|------|-----------------|
| #1 | schemas.py, validation.py | Types + validation | None | ~250 lines |
| #2 | diagnostic_router.py, router.py (refactor) | Diagnostic CRUD | #1 | ~300 lines |
| #3 | program_router.py, router.py (refactor) | Program + Exercise CRUD | #1, #2 | ~280 lines |

Each PR can be reviewed and tested independently. PRs #2 and #3 depend on #1 but are otherwise independent.
