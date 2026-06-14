# API Specification: Doctor Diagnostic & Program Management

**Change**: `api-medico-diagnostico-programa`  
**Date**: 2026-06-11  
**Status**: Draft Specification

---

## Overview

This specification defines the complete doctor-facing clinical API: diagnostic listing, creation, updates, and rehab program management with exercise assignment. The API enforces:
- **FK validation** (patient exists, authenticated medical principal resolves to `clinical.doctor`, exercise exists)
- **Doctor-scoped authorization** (fail-fast 403 if the principal cannot be resolved to a doctor or is not the diagnostic author)
- **Pagination** (offset/limit, max=100)
- **Pydantic schemas** (request/response type safety, OpenAPI integration)

---

## PR #1: Foundation — Schemas & Validation Helpers

### Scope: No Endpoint Changes

This PR establishes reusable Pydantic models and validation functions used by all CRUD endpoints in PR #2 and #3.

### New Files

#### `schemas.py` — Pydantic Request/Response Models

```python
# Base response envelope for list endpoints
class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    total: int
    limit: int
    offset: int

# Patient schema (minimal, used in diagnostic/program responses)
class PatientOut(BaseModel):
    id: UUID
    nombre: str
    apellidos: str
    
    class Config:
        from_attributes = True

# Diagnostic schemas
class DiagnosticIn(BaseModel):
    patient_id: UUID
    dolencia: str  # Required, 1-500 chars
    descripcion: str | None = None  # Optional, 0-5000 chars
    
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

# Program schemas
class ProgramIn(BaseModel):
    diagnostic_id: UUID
    estado: str = "activo"  # Default status

class ProgramOut(BaseModel):
    id: UUID
    diagnostic_id: UUID
    estado: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Exercise in program
class ProgramExerciseIn(BaseModel):
    exercise_id: UUID
    pauta: str | None = None  # Frequency/instructions

class ProgramExerciseOut(BaseModel):
    id: UUID
    program_id: UUID
    exercise_id: UUID
    pauta: str | None
    estado: str
    
    class Config:
        from_attributes = True

# Query model for pagination
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

# Error response envelope
class ErrorResponse(BaseModel):
    detail: str
    code: str  # e.g., "PATIENT_NOT_FOUND", "UNAUTHORIZED", "VALIDATION_ERROR"
```

### Validation Helpers (`validation.py`)

```python
def check_patient_exists_and_assigned(
    db: Session, 
    patient_id: UUID, 
    doctor_keycloak_id: str
) -> Patient:
    """
    Verify patient exists AND authenticated subject resolves to a doctor.

    Live SDD/ERD note: the PostgreSQL schema does not contain
    clinical.care_assignment. The API resolves the JWT subject through
    clinical.app_user.external_subject -> clinical.doctor.doctor_id.
    
    Raises:
        HTTPException(403) if doctor identity cannot be resolved
        HTTPException(404) if patient doesn't exist
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")
    
    doctor = db.query(Doctor).join(AppUser).filter(
        AppUser.external_subject == doctor_keycloak_id
    ).first()
    
    if not doctor:
        raise HTTPException(403, "Doctor not assigned to this patient")
    
    return patient

def check_exercise_exists(db: Session, exercise_id: UUID) -> dict:
    """
    Verify exercise exists in catalog.rehab_exercise.
    
    Raises:
        HTTPException(404) if exercise not found
    """
    exercise = db.execute(
        text("SELECT id FROM catalog.rehab_exercise WHERE id = :id"),
        {"id": str(exercise_id)}
    ).first()
    
    if not exercise:
        raise HTTPException(404, "Exercise not found in catalog")
    
    return {"id": exercise_id}

def check_program_belongs_to_diagnostic(
    db: Session,
    program_id: UUID,
    diagnostic_id: UUID
) -> RehabProgram:
    """
    Verify program exists and belongs to diagnostic.
    
    Raises:
        HTTPException(404) if program not found or mismatched diagnostic
    """
    program = db.query(RehabProgram).filter(
        RehabProgram.id == program_id,
        RehabProgram.diagnostic_id == diagnostic_id
    ).first()
    
    if not program:
        raise HTTPException(404, "Program not found or doesn't belong to diagnostic")
    
    return program

def check_diagnostic_authorized(
    db: Session,
    diagnostic_id: UUID,
    doctor_keycloak_id: str
) -> Diagnostic:
    """
    Verify diagnostic exists AND doctor is author.
    
    Raises:
        HTTPException(404) if diagnostic not found
        HTTPException(403) if not the author
    """
    diagnostic = db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
    
    if not diagnostic:
        raise HTTPException(404, "Diagnostic not found")
    
    # Must be the doctor who created it
    if diagnostic.doctor.keycloak_id != doctor_keycloak_id:
        raise HTTPException(403, "You are not the author of this diagnostic")
    
    return diagnostic
```

### Requirements

| Requirement | Description |
|-------------|-------------|
| **Foundation-01: Pydantic Schema Serialization** | Request/response models serializable to/from JSON with type validation |
| **Foundation-02: Pagination Validation** | Limit ∈ [0, 100], offset ≥ 0; enforce bounds in validator |
| **Foundation-03: Doctor Identity Check** | Resolve `clinical.app_user.external_subject` to `clinical.doctor.doctor_id` before doctor-scoped clinical operations; fail fast with 403 |
| **Foundation-04: Exercise FK Validation** | Query catalog for exercise_id; return 404 if not found |
| **Foundation-05: Diagnostic Authorization** | Verify doctor_id matches authenticated principal; 403 if not author |

### Scenarios

#### Scenario: Validate patient exists and doctor identity resolves
- GIVEN: doctor_keycloak_id = "doc-001", patient_id = "pat-123"
- WHEN: call `check_patient_exists_and_assigned(db, patient_id, doctor_keycloak_id)`
- THEN: If `clinical.app_user.external_subject` maps to `clinical.doctor.doctor_id`, return Patient
- AND: If doctor identity cannot be resolved, raise HTTPException(403, "Doctor not assigned to this patient")

#### Scenario: Validate exercise exists in catalog
- GIVEN: exercise_id = "ex-999" (doesn't exist in catalog)
- WHEN: call `check_exercise_exists(db, exercise_id)`
- THEN: raise HTTPException(404, "Exercise not found in catalog")

#### Scenario: Pagination query with valid bounds
- GIVEN: limit=50, offset=100
- WHEN: ListQuery(limit=50, offset=100)
- THEN: Model validates; both fields pass
- AND: If limit=101, raise ValueError("limit must be 0-100")

#### Scenario: Pagination query with negative offset
- GIVEN: offset=-1
- WHEN: ListQuery(offset=-1)
- THEN: raise ValueError("offset must be ≥ 0")

---

## PR #2: Diagnostic CRUD

### Endpoints

#### **POST /diagnostics** — Create Diagnostic

**Request**:
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "dolencia": "Dolor de espalda baja",
  "descripcion": "Dolor persistente en región lumbar tras caída el 10/06/2026"
}
```

**Response (201)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "doctor_id": "550e8400-e29b-41d4-a716-446655440002",
  "dolencia": "Dolor de espalda baja",
  "descripcion": "Dolor persistente en región lumbar tras caída el 10/06/2026",
  "signature": null,
  "signed_at": null,
  "created_at": "2026-06-11T14:30:00Z"
}
```

**Errors**:
| Status | Code | Message |
|--------|------|---------|
| 400 | BAD_REQUEST | Malformed JSON or missing required fields |
| 403 | UNAUTHORIZED | Doctor not assigned to this patient |
| 404 | NOT_FOUND | Patient does not exist |
| 422 | VALIDATION_ERROR | dolencia length invalid (1-500 chars) |

**Requirements**:
| Req | Description |
|-----|-------------|
| **Diagnostic-C-01** | MUST authenticate doctor via JWT principal |
| **Diagnostic-C-02** | MUST verify patient exists |
| **Diagnostic-C-03** | MUST verify authenticated principal resolves to a doctor via `clinical.app_user.external_subject` + `clinical.doctor.doctor_id` (live SDD/ERD replacement for the earlier `CareAssignment` assumption) |
| **Diagnostic-C-04** | MUST accept `patient_id`, `dolencia` (required), `descripcion` (optional) |
| **Diagnostic-C-05** | MUST validate dolencia length 1-500 chars |
| **Diagnostic-C-06** | MUST validate descripcion length ≤ 5000 chars (if provided) |
| **Diagnostic-C-07** | MUST set `doctor_id` from authenticated principal (not user input) |
| **Diagnostic-C-08** | MUST NOT auto-create RehabProgram (decoupled in this PR; old endpoint keeps backward compat) |
| **Diagnostic-C-09** | MUST return 201 with complete DiagnosticOut schema |
| **Diagnostic-C-10** | MUST set `created_at` to current timestamp |

**Scenarios**:

##### Happy Path: Create diagnostic for patient as doctor
- GIVEN: doctor authenticated, JWT subject maps to `clinical.app_user` + `clinical.doctor`, patient exists, valid dolencia
- WHEN: POST /diagnostics with patient_id, dolencia, descripcion
- THEN: Return 201 with Diagnostic record
- AND: diagnostic.doctor_id = authenticated doctor
- AND: diagnostic.created_at is set

##### Sad Path: Doctor identity not resolved
- GIVEN: medical principal authenticated, but no `clinical.app_user` + `clinical.doctor` row maps to its subject
- WHEN: POST /diagnostics with that patient_id
- THEN: Return 403 "Doctor not assigned to this patient"

##### Sad Path: Patient doesn't exist
- GIVEN: doctor authenticated, patient_id doesn't exist
- WHEN: POST /diagnostics with non-existent patient_id
- THEN: Return 404 "Patient not found"

##### Sad Path: Dolencia exceeds length
- GIVEN: dolencia = "x" * 501
- WHEN: POST /diagnostics
- THEN: Return 422 "dolencia must be 1-500 characters"

##### Sad Path: Malformed JSON
- GIVEN: request body is not valid JSON
- WHEN: POST /diagnostics
- THEN: Return 400 "Bad request"

---

#### **GET /diagnostics** — List Diagnostics (Paginated)

**Request**:
```
GET /diagnostics?patient_id=550e8400-e29b-41d4-a716-446655440000&limit=20&offset=0
```

**Response (200)**:
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "patient_id": "550e8400-e29b-41d4-a716-446655440000",
      "doctor_id": "550e8400-e29b-41d4-a716-446655440002",
      "dolencia": "Dolor de espalda baja",
      "descripcion": "...",
      "signature": null,
      "signed_at": null,
      "created_at": "2026-06-11T14:30:00Z"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

**Errors**:
| Status | Code | Message |
|--------|------|---------|
| 400 | BAD_REQUEST | limit > 100 or offset < 0 |
| 403 | UNAUTHORIZED | Doctor identity cannot be resolved |
| 404 | NOT_FOUND | Patient not found (if patient_id provided) |

**Requirements**:
| Req | Description |
|-----|-------------|
| **Diagnostic-R-01** | MUST authenticate doctor |
| **Diagnostic-R-02** | MUST accept optional `patient_id` query param to filter by patient |
| **Diagnostic-R-03** | MUST accept `limit` (default 20, max 100) and `offset` (default 0) |
| **Diagnostic-R-04** | MUST validate limit ∈ [0, 100] |
| **Diagnostic-R-05** | MUST verify doctor identity via `clinical.app_user.external_subject` + `clinical.doctor.doctor_id` before returning doctor-scoped diagnostics |
| **Diagnostic-R-06** | MUST enforce doctor-scoped query: only return diagnostics authored by the authenticated doctor |
| **Diagnostic-R-07** | MUST return PaginatedResponse with data[], total, limit, offset |
| **Diagnostic-R-08** | MUST NOT return diagnostics authored by another doctor |

**Scenarios**:

##### Happy Path: List all diagnostics for doctor
- GIVEN: doctor authenticated, has 3 diagnostics across 2 patients
- WHEN: GET /diagnostics?limit=20&offset=0
- THEN: Return 200 with 3 items, total=3
- AND: All diagnostics were authored by the authenticated doctor

##### Happy Path: List with patient filter
- GIVEN: doctor authenticated, patient exists, doctor authored 5 diagnostics for that patient
- WHEN: GET /diagnostics?patient_id=<uuid>&limit=10&offset=0
- THEN: Return 200 with 5 items, total=5

##### Happy Path: Pagination with offset
- GIVEN: doctor has 25 diagnostics
- WHEN: GET /diagnostics?limit=10&offset=10
- THEN: Return items 11-20, total=25, offset=10

##### Sad Path: Limit exceeds 100
- GIVEN: limit=150
- WHEN: GET /diagnostics?limit=150
- THEN: Return 400 "limit must be 0-100"

##### Sad Path: Different doctor owns diagnostic data
- GIVEN: another doctor owns diagnostic data
- WHEN: GET /diagnostics?patient_id=<uuid>
- THEN: Do not return the other doctor's diagnostics

##### Sad Path: Offset is negative
- GIVEN: offset=-1
- WHEN: GET /diagnostics?offset=-1
- THEN: Return 400 "offset must be ≥ 0"

##### Edge Case: Empty result set
- GIVEN: doctor authenticated, patient exists, but the doctor has no diagnostics for that patient
- WHEN: GET /diagnostics?patient_id=<uuid>
- THEN: Return 200 with data=[], total=0

---

#### **GET /diagnostics/{id}** — Retrieve Single Diagnostic

**Request**:
```
GET /diagnostics/550e8400-e29b-41d4-a716-446655440001
```

**Response (200)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "doctor_id": "550e8400-e29b-41d4-a716-446655440002",
  "dolencia": "Dolor de espalda baja",
  "descripcion": "...",
  "signature": null,
  "signed_at": null,
  "created_at": "2026-06-11T14:30:00Z"
}
```

**Errors**:
| Status | Code | Message |
|--------|------|---------|
| 403 | UNAUTHORIZED | You are not the author of this diagnostic |
| 404 | NOT_FOUND | Diagnostic not found |

**Requirements**:
| Req | Description |
|-----|-------------|
| **Diagnostic-G-01** | MUST authenticate doctor |
| **Diagnostic-G-02** | MUST verify diagnostic exists; return 404 if not |
| **Diagnostic-G-03** | MUST verify authenticated doctor authored diagnostic; return 403 if not |
| **Diagnostic-G-04** | MUST return DiagnosticOut schema |

**Scenarios**:

##### Happy Path: Retrieve owned diagnostic
- GIVEN: doctor authenticated, owns diagnostic with id
- WHEN: GET /diagnostics/{id}
- THEN: Return 200 with full DiagnosticOut

##### Sad Path: Not the author
- GIVEN: doctor authenticated, but did not author this diagnostic
- WHEN: GET /diagnostics/{id}
- THEN: Return 403 "You are not the author of this diagnostic"

##### Sad Path: Diagnostic doesn't exist
- GIVEN: id doesn't exist in database
- WHEN: GET /diagnostics/{id}
- THEN: Return 404 "Diagnostic not found"

---

#### **PATCH /diagnostics/{id}** — Update Diagnostic

**Request**:
```json
{
  "descripcion": "Updated description with new findings",
  "dolencia": "Dolor de espalda baja - crónico"
}
```

**Response (200)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "doctor_id": "550e8400-e29b-41d4-a716-446655440002",
  "dolencia": "Dolor de espalda baja - crónico",
  "descripcion": "Updated description with new findings",
  "signature": null,
  "signed_at": null,
  "created_at": "2026-06-11T14:30:00Z"
}
```

**Errors**:
| Status | Code | Message |
|--------|------|---------|
| 403 | UNAUTHORIZED | You are not the author of this diagnostic |
| 404 | NOT_FOUND | Diagnostic not found |
| 422 | VALIDATION_ERROR | Field validation failed (length, etc.) |

**Requirements**:
| Req | Description |
|-----|-------------|
| **Diagnostic-U-01** | MUST authenticate doctor |
| **Diagnostic-U-02** | MUST verify diagnostic exists; return 404 if not |
| **Diagnostic-U-03** | MUST verify authenticated doctor authored diagnostic; return 403 if not |
| **Diagnostic-U-04** | MUST accept optional patches to: dolencia, descripcion |
| **Diagnostic-U-05** | MUST validate field lengths (dolencia 1-500, descripcion ≤ 5000) |
| **Diagnostic-U-06** | MUST NOT allow updates to patient_id, doctor_id, created_at |
| **Diagnostic-U-07** | MUST return 200 with updated DiagnosticOut |
| **Diagnostic-U-08** | SHOULD update updated_at field (if model adds it) |

**Scenarios**:

##### Happy Path: Update description only
- GIVEN: doctor owns diagnostic, description is valid
- WHEN: PATCH /diagnostics/{id} with new descripcion
- THEN: Return 200 with updated record
- AND: dolencia unchanged
- AND: created_at unchanged

##### Happy Path: Update both fields
- GIVEN: doctor owns diagnostic, both fields valid
- WHEN: PATCH /diagnostics/{id} with new dolencia + descripcion
- THEN: Return 200 with both fields updated

##### Sad Path: Update fails auth
- GIVEN: doctor didn't author diagnostic
- WHEN: PATCH /diagnostics/{id}
- THEN: Return 403 "You are not the author of this diagnostic"

##### Sad Path: Malformed input
- GIVEN: dolencia = "x" * 501
- WHEN: PATCH /diagnostics/{id}
- THEN: Return 422 "dolencia must be 1-500 characters"

##### Edge Case: Empty PATCH body
- GIVEN: PATCH body is {} (no fields to update)
- WHEN: PATCH /diagnostics/{id}
- THEN: Return 200 with unchanged record

---

## PR #3: Program CRUD & Exercise Assignment

### Endpoints

#### **POST /programs** — Create Rehab Program

**Request**:
```json
{
  "diagnostic_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

**Response (201)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "diagnostic_id": "550e8400-e29b-41d4-a716-446655440001",
  "estado": "activo",
  "created_at": "2026-06-11T14:35:00Z"
}
```

**Errors**:
| Status | Code | Message |
|--------|------|---------|
| 400 | BAD_REQUEST | Malformed JSON |
| 403 | UNAUTHORIZED | You are not the author of this diagnostic |
| 404 | NOT_FOUND | Diagnostic not found |

**Requirements**:
| Req | Description |
|-----|-------------|
| **Program-C-01** | MUST authenticate doctor |
| **Program-C-02** | MUST accept diagnostic_id (required) |
| **Program-C-03** | MUST verify diagnostic exists; return 404 if not |
| **Program-C-04** | MUST verify doctor authored the diagnostic; return 403 if not |
| **Program-C-05** | MUST set estado to "activo" by default |
| **Program-C-06** | MUST return 201 with ProgramOut schema |
| **Program-C-07** | MUST set created_at to current timestamp |

**Scenarios**:

##### Happy Path: Create program for owned diagnostic
- GIVEN: doctor authenticated, owns diagnostic
- WHEN: POST /programs with diagnostic_id
- THEN: Return 201 with RehabProgram
- AND: program.estado = "activo"
- AND: program.diagnostic_id = provided diagnostic_id

##### Sad Path: Diagnostic not found
- GIVEN: diagnostic_id doesn't exist
- WHEN: POST /programs
- THEN: Return 404 "Diagnostic not found"

##### Sad Path: Not diagnostic author
- GIVEN: doctor authenticated, but didn't author diagnostic
- WHEN: POST /programs with that diagnostic_id
- THEN: Return 403 "You are not the author of this diagnostic"

##### Edge Case: Multiple programs per diagnostic
- GIVEN: diagnostic already has 1 program
- WHEN: POST /programs with same diagnostic_id
- THEN: Return 201 with new RehabProgram (N:1 relationship allowed)

---

#### **GET /programs** — List Programs (Paginated)

**Request**:
```
GET /programs?diagnostic_id=550e8400-e29b-41d4-a716-446655440001&limit=20&offset=0
```

**Response (200)**:
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440003",
      "diagnostic_id": "550e8400-e29b-41d4-a716-446655440001",
      "estado": "activo",
      "created_at": "2026-06-11T14:35:00Z"
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

**Errors**:
| Status | Code | Message |
|--------|------|---------|
| 400 | BAD_REQUEST | limit > 100 or offset < 0 |
| 403 | UNAUTHORIZED | Not the author of this diagnostic |
| 404 | NOT_FOUND | Diagnostic not found |

**Requirements**:
| Req | Description |
|-----|-------------|
| **Program-R-01** | MUST authenticate doctor |
| **Program-R-02** | MUST accept optional `diagnostic_id` filter |
| **Program-R-03** | MUST accept `limit` (default 20, max 100) and `offset` |
| **Program-R-04** | MUST verify diagnostic ownership if filter provided |
| **Program-R-05** | MUST enforce RLS: only return programs for owned diagnostics |
| **Program-R-06** | MUST return PaginatedResponse with data[], total, limit, offset |

**Scenarios**:

##### Happy Path: List all programs
- GIVEN: doctor authenticated, has 3 programs
- WHEN: GET /programs?limit=20&offset=0
- THEN: Return 200 with 3 items, total=3

##### Happy Path: Filter by diagnostic
- GIVEN: doctor owns diagnostic with 2 programs
- WHEN: GET /programs?diagnostic_id=<uuid>&limit=20
- THEN: Return 200 with 2 items

##### Happy Path: Pagination
- GIVEN: doctor has 50 programs
- WHEN: GET /programs?limit=10&offset=20
- THEN: Return items 21-30, total=50

##### Sad Path: Limit exceeds 100
- GIVEN: limit=150
- WHEN: GET /programs?limit=150
- THEN: Return 400 "limit must be 0-100"

##### Edge Case: No programs
- GIVEN: doctor authenticated, has no programs
- WHEN: GET /programs
- THEN: Return 200 with data=[], total=0

---

#### **GET /programs/{id}** — Retrieve Program Detail

**Request**:
```
GET /programs/550e8400-e29b-41d4-a716-446655440003
```

**Response (200)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "diagnostic_id": "550e8400-e29b-41d4-a716-446655440001",
  "estado": "activo",
  "created_at": "2026-06-11T14:35:00Z"
}
```

**Errors**:
| Status | Code | Message |
|--------|------|---------|
| 403 | UNAUTHORIZED | You don't have access to this program |
| 404 | NOT_FOUND | Program not found |

**Requirements**:
| Req | Description |
|-----|-------------|
| **Program-G-01** | MUST authenticate doctor |
| **Program-G-02** | MUST verify program exists; return 404 if not |
| **Program-G-03** | MUST verify doctor authored the linked diagnostic; return 403 if not |
| **Program-G-04** | MUST return ProgramOut schema |

**Scenarios**:

##### Happy Path: Retrieve owned program
- GIVEN: doctor authenticated, owns diagnostic linked to program
- WHEN: GET /programs/{id}
- THEN: Return 200 with ProgramOut

##### Sad Path: Program doesn't exist
- GIVEN: id doesn't exist
- WHEN: GET /programs/{id}
- THEN: Return 404 "Program not found"

##### Sad Path: Unauthorized
- GIVEN: program exists but linked to diagnostic doctor didn't author
- WHEN: GET /programs/{id}
- THEN: Return 403 "You don't have access to this program"

---

#### **POST /programs/{id}/exercises** — Assign Exercise to Program

**Request**:
```json
{
  "exercise_id": "550e8400-e29b-41d4-a716-446655440099",
  "pauta": "3 sets x 10 reps, 2x per week"
}
```

**Response (201)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440010",
  "program_id": "550e8400-e29b-41d4-a716-446655440003",
  "exercise_id": "550e8400-e29b-41d4-a716-446655440099",
  "pauta": "3 sets x 10 reps, 2x per week",
  "estado": "asignado"
}
```

**Errors**:
| Status | Code | Message |
|--------|------|---------|
| 400 | BAD_REQUEST | Malformed JSON |
| 403 | UNAUTHORIZED | You don't have access to this program |
| 404 | NOT_FOUND | Program not found OR Exercise not found |
| 422 | VALIDATION_ERROR | Program doesn't match the requested {id} |

**Requirements**:
| Req | Description |
|-----|-------------|
| **Exercise-A-01** | MUST authenticate doctor |
| **Exercise-A-02** | MUST verify program exists and is owned by doctor; return 403/404 |
| **Exercise-A-03** | MUST accept exercise_id (required) and pauta (optional) |
| **Exercise-A-04** | MUST verify exercise exists in catalog; return 404 if not |
| **Exercise-A-05** | MUST set estado to "asignado" by default |
| **Exercise-A-06** | MUST return 201 with ProgramExerciseOut |
| **Exercise-A-07** | MUST allow duplicate exercise assignments (same exercise, same program) |

**Scenarios**:

##### Happy Path: Assign exercise to program
- GIVEN: doctor authenticated, owns program, exercise exists in catalog
- WHEN: POST /programs/{id}/exercises with exercise_id, pauta
- THEN: Return 201 with ProgramExerciseOut
- AND: program_exercise.estado = "asignado"

##### Sad Path: Program not found
- GIVEN: program_id doesn't exist
- WHEN: POST /programs/{id}/exercises
- THEN: Return 404 "Program not found"

##### Sad Path: Exercise not found
- GIVEN: exercise_id doesn't exist in catalog
- WHEN: POST /programs/{id}/exercises
- THEN: Return 404 "Exercise not found in catalog"

##### Sad Path: Unauthorized
- GIVEN: doctor doesn't own linked diagnostic
- WHEN: POST /programs/{id}/exercises
- THEN: Return 403 "You don't have access to this program"

##### Edge Case: Assign same exercise twice
- GIVEN: exercise already assigned to program
- WHEN: POST /programs/{id}/exercises with same exercise_id
- THEN: Return 201 with NEW ProgramExercise (allow duplicates)

##### Edge Case: Pauta is null
- GIVEN: pauta not provided in request
- WHEN: POST /programs/{id}/exercises
- THEN: Return 201 with pauta=null

---

## Summary of Changes

| PR | Files | Endpoints | Lines | Status |
|----|-------|-----------|-------|--------|
| #1 | `schemas.py`, `validation.py` | — | 200–250 | Foundation |
| #2 | `diagnostic_router.py`, refactored `patient_router.py` | POST/GET/PATCH /diagnostics | 280–320 | CRUD |
| #3 | `program_router.py` | POST/GET /programs, POST /programs/{id}/exercises | 300–340 | CRUD + Exercise |

## Error Response Format

All errors return JSON envelope:
```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE"
}
```

Standard HTTP status codes:
- **400**: Malformed request (bad JSON, invalid query params)
- **403**: Authorization denied (RLS, ownership check)
- **404**: Resource not found (patient, diagnostic, program, exercise)
- **422**: Validation error (field constraints, FK violations)
- **500**: Internal server error (unexpected exception)

## Validation Rules Summary

| Entity | Field | Rule | Enforced |
|--------|-------|------|----------|
| Diagnostic | dolencia | 1–500 chars, required | Pydantic validator |
| Diagnostic | descripcion | 0–5000 chars, optional | Pydantic validator |
| Diagnostic | patient_id | FK: patient must exist; doctor subject must resolve to `clinical.doctor` | `check_patient_exists_and_assigned()` |
| Diagnostic | doctor_id | Set from principal, not user input | Backend code |
| Program | diagnostic_id | FK: must exist, must be authored by doctor | `check_diagnostic_authorized()` |
| Exercise | exercise_id | FK: must exist in catalog | `check_exercise_exists()` |
| List Query | limit | 0–100, default 20 | Pydantic validator |
| List Query | offset | ≥ 0, default 0 | Pydantic validator |

---

**Next Steps**: Design phase to finalize request/response shapes and error codes.
