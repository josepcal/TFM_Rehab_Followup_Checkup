# Exploration: API Setup Programa de Rehabilitación (UC-02)

**Change Name**: `api-setup-programa-rehabilitacion`  
**Scope**: UC-02, AC-04, AC-05, AC-06 doctor-facing API  
**Mode**: openspec  
**Status**: Exploration complete

## SDD anchor

UC-02 says the Medical Specialist creates a rehabilitation program from base exercises after a patient has a diagnostic. Postcondition: program exercises are registered for the patient with an assigned physiotherapist context. Relevant SDD entities: `Rehab Program`, `Program Exercise`, `Rehab Exercise` catalog, and `Patient Consent` for later consent flows.

## Current implementation

Already present in code:

- `api/app/clinical/program_router.py`
  - `POST /programs/`
  - `GET /programs/?diagnostic_id=...`
  - `GET /programs/{program_id}`
  - `POST /programs/{program_id}/exercises`
- `api/app/clinical/program_service.py` orchestrates the program use cases.
- `api/app/clinical/adapters/postgres_program_repository.py` authorizes through diagnostic ownership and persists `RehabProgram` / `ProgramExercise`.
- `api/app/clinical/schemas.py` has `ProgramIn`, `ProgramOut`, `ProgramExerciseIn`, `ProgramExerciseOut`.
- Integration coverage exists for program detail and exercise assignment; service unit coverage exists for create/list/get/assign.
- Deprecated compatibility endpoint `POST /programs/exercises` delegates to `ProgramService`.

## Gaps for UC-02 completion

| Area | Gap | Impact |
|------|-----|--------|
| Program creation | `ProgramIn` only accepts `diagnostic_id` and `estado`; it does not accept `name`, `start_date`, `end_date`, `physiotherapist_id`. | Rehab plan setup is clinically thin. |
| Program search | `GET /programs/` requires `diagnostic_id`; no broader doctor search across all owned programs or patient filter. | AC-06 is only partially satisfied. |
| Exercise listing | No `GET /programs/{program_id}/exercises` endpoint despite existing assignment endpoint. | Doctor cannot verify the exercise table after setup. |
| Response contract | `ProgramExerciseOut` omits `created_at`; `ProgramOut` omits `name`, dates and physiotherapist. | UI cannot render complete plan metadata. |
| Tests | Missing integration tests for `POST /programs/`, `GET /programs/` search, and exercise list. | Current behavior may regress unnoticed. |
| Patient consent | UC-02 touches rehab programs, but FR-14 consent enforcement is a later patient/recording concern. | Keep out of this API slice unless required later. |

## Recommended approach

Implement an incremental hardening of the existing hexagonal program slice:

1. Extend program schemas/domain records for plan metadata.
2. Extend repository queries for doctor-wide program search with optional `diagnostic_id` and `patient_id` filters.
3. Add exercise listing through the existing service/repository boundary.
4. Add DB-backed integration tests for AC-04, AC-05 and AC-06.
5. Keep patient-facing AC-07 and consent flows out of this change.

## Risks

- Backward compatibility: existing callers pass only `diagnostic_id`; new fields must remain optional.
- API route shape: current `GET /programs/` requires `diagnostic_id`; making it optional changes validation behavior but enables AC-06.
- Date serialization: use Pydantic/datetime consistently with existing API schemas.
