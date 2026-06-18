# Design: API Setup Programa de Rehabilitación

## Technical Approach

Implement UC-02 as an incremental extension of the current program hexagonal slice. Routers keep HTTP concerns, `ProgramService` maps schemas, `ProgramRepository` defines the port, and `PostgresProgramRepository` owns SQLAlchemy queries and authorization joins.

## Architecture Decisions

### Decision: Keep one program slice

**Choice**: Extend existing `program_router`, `program_service`, repository port and PostgreSQL adapter.  
**Alternatives considered**: Create a second UC-02 router.  
**Rationale**: Existing code already models program create/list/get/assign; extending it avoids duplicate endpoints and keeps compatibility.

### Decision: Optional search filters

**Choice**: Make `diagnostic_id` optional on `GET /programs/`, add optional `patient_id`.  
**Alternatives considered**: Add separate `/programs/search`.  
**Rationale**: Existing REST shape remains stable while satisfying AC-06 doctor-wide search.

### Decision: Program metadata remains optional

**Choice**: Add optional `name`, `start_date`, `end_date`, `physiotherapist_id` to `ProgramIn` and `ProgramOut`.  
**Alternatives considered**: Require all plan metadata.  
**Rationale**: Existing callers currently send only `diagnostic_id`; optional fields avoid breaking compatibility.

## Data Flow

```text
POST /programs/
  -> ProgramIn validation
  -> ProgramService.create_program
  -> PostgresProgramRepository.check_diagnostic_authorized
  -> insert clinical.rehab_program
  -> ProgramOut

GET /programs/?diagnostic_id=&patient_id=&limit=&offset=
  -> ListQuery validation
  -> ProgramService.list_programs
  -> repository joins RehabProgram -> Diagnostic
  -> filter by doctor, optional diagnostic/patient
  -> PaginatedResponse[ProgramOut]

GET /programs/{id}/exercises
  -> authorize program through linked diagnostic
  -> select clinical.program_exercise rows
  -> PaginatedResponse[ProgramExerciseOut]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/app/clinical/schemas.py` | Modify | Add program metadata fields; add optional filter model if needed. |
| `api/app/clinical/program_domain.py` | Modify | Add metadata to `ProgramRecord`; add `created_at` to `ProgramExerciseRecord`. |
| `api/app/clinical/ports.py` | Modify | Update `create_program`, `list_programs`, add `list_program_exercises`. |
| `api/app/clinical/program_service.py` | Modify | Map metadata and exercise list response. |
| `api/app/clinical/program_router.py` | Modify | Optional search filters and `GET /{program_id}/exercises`. |
| `api/app/clinical/adapters/postgres_program_repository.py` | Modify | Persist metadata, doctor-scoped search, exercise list query. |
| `api/tests/test_program_service.py` | Modify | Unit coverage for metadata/search/list exercises. |
| `api/tests/integration/test_program_endpoints.py` | Modify | DB-backed AC-04/AC-05/AC-06 coverage. |

## Interfaces / Contracts

```python
class ProgramIn(BaseModel):
    diagnostic_id: UUID
    estado: str | None = "activo"
    name: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    physiotherapist_id: UUID | None = None

class ProgramOut(BaseModel):
    id: UUID
    diagnostic_id: UUID
    estado: str
    name: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    physiotherapist_id: UUID | None = None
    created_at: datetime | None = None
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | Service delegates metadata/search/list exercises | Fake repository tests. |
| Integration | Program create/search/exercise list auth | TestClient + PostgreSQL fixtures. |
| Regression | Existing deprecated assignment endpoint | Keep existing integration test. |

## Migration / Rollout

No database migration required; target columns already exist in `clinical.rehab_program` and `clinical.program_exercise`.

## Open Questions

- [ ] Should `physiotherapist_id` be required by product for UC-02, or remain optional as the SDD data model states?
