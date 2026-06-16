# Proposal: API Setup Programa de Rehabilitación

**Change Name**: `api-setup-programa-rehabilitacion`  
**Status**: Proposed

## Intent

Complete the doctor-facing UC-02 API so a Medical Specialist can create a rehab plan from an existing diagnostic, assign base exercises, list the exercise table, and search all rehab programs they own.

## Scope

### In Scope

- Extend `POST /programs/` to accept optional plan metadata: `name`, `start_date`, `end_date`, `physiotherapist_id`.
- Extend `ProgramOut` with the same readable metadata.
- Make `GET /programs/` support doctor-wide search with optional `diagnostic_id` and `patient_id` filters.
- Add `GET /programs/{program_id}/exercises` to return assigned exercises.
- Add unit/integration tests for AC-04, AC-05 and AC-06.

### Out of Scope

- Patient-facing AC-07 program search.
- Patient consent enforcement and recording permissions.
- Catalog exercise creation/edition.
- UI for rehab program setup.

## Capabilities

### New Capabilities

- `api-setup-programa-rehabilitacion`: Doctor can setup and search rehab programs and their exercise table for UC-02.

### Modified Capabilities

- `api-medico-diagnostico-programa`: Program CRUD behavior is narrowed/refined so UC-02 endpoints are complete and searchable without requiring a diagnostic filter.

## Approach

Reuse the existing `program_router -> ProgramService -> ProgramRepository -> PostgresProgramRepository` slice. Extend schemas/domain records first, then add repository methods for flexible search and exercise listing. Preserve backward compatibility by keeping new request fields optional and keeping `POST /programs/exercises` as deprecated compatibility.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/app/clinical/schemas.py` | Modified | Program input/output contracts. |
| `api/app/clinical/program_domain.py` | Modified | Program and exercise domain records. |
| `api/app/clinical/ports.py` | Modified | Repository interface for search/list exercises. |
| `api/app/clinical/program_service.py` | Modified | Orchestrate new list contracts. |
| `api/app/clinical/program_router.py` | Modified | Optional filters and exercise list endpoint. |
| `api/app/clinical/adapters/postgres_program_repository.py` | Modified | SQLAlchemy persistence/search. |
| `api/tests/` | Modified | Unit and integration coverage. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Breaking existing callers of `GET /programs/` | Medium | Keep `diagnostic_id` as optional filter rather than removing it. |
| Exposing programs across doctors | Medium | Keep `check_diagnostic_authorized`/doctor joins in every query. |
| Over-expanding UC-02 | Low | Exclude patient consent and patient search. |

## Rollback Plan

Revert the program API changes and tests; existing `POST /programs/`, `GET /programs/?diagnostic_id=...`, `GET /programs/{id}`, and assignment endpoint can remain as the fallback contract.

## Success Criteria

- [ ] `POST /programs/` creates a plan linked to an owned diagnostic with optional metadata.
- [ ] `GET /programs/` lists only programs owned by the authenticated doctor.
- [ ] `GET /programs/{id}/exercises` returns assigned exercises.
- [ ] Unauthorized doctor access returns 403 and missing resources return 404.
- [ ] Unit and integration tests cover AC-04, AC-05 and AC-06.
