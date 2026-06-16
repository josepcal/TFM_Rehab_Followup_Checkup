# Tasks: API Setup Programa de Rehabilitación

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 250-380 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR acceptable; split tests if diff grows |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Program contract + metadata persistence | PR 1 | Schemas/domain/repository/service. |
| 2 | Search + exercise list endpoints | PR 1 | Router/repository + tests. |

## Phase 1: Contract Foundation

- [x] 1.1 Extend `ProgramIn`/`ProgramOut` in `api/app/clinical/schemas.py` with optional `name`, `start_date`, `end_date`, `physiotherapist_id`.
- [x] 1.2 Add `created_at` to `ProgramExerciseOut` if model support is available.
- [x] 1.3 Extend `ProgramRecord` and `ProgramExerciseRecord` in `api/app/clinical/program_domain.py`.
- [x] 1.4 Update `ProgramRepository` in `api/app/clinical/ports.py` for metadata, optional list filters, and exercise listing.

## Phase 2: Core Implementation

- [x] 2.1 Update `ProgramService.create_program` and `_program_out` to map metadata.
- [x] 2.2 Update `ProgramService.list_programs` to accept optional `diagnostic_id` and `patient_id` filters.
- [x] 2.3 Add `ProgramService.list_program_exercises(program_id, query, doctor_subject)`.
- [x] 2.4 Update `PostgresProgramRepository.create_program` to persist metadata.
- [x] 2.5 Update `PostgresProgramRepository.list_programs` to join `Diagnostic` and filter by authenticated doctor plus optional filters.
- [x] 2.6 Add `PostgresProgramRepository.list_program_exercises` with program authorization and pagination.

## Phase 3: Router Integration

- [x] 3.1 Make `diagnostic_id` optional in `GET /programs/` and add optional `patient_id` in `api/app/clinical/program_router.py`.
- [x] 3.2 Add `GET /programs/{program_id}/exercises` returning `PaginatedResponse[ProgramExerciseOut]`.
- [x] 3.3 Preserve existing `POST /programs/`, `GET /programs/{program_id}`, and deprecated `POST /programs/exercises` compatibility behavior.

## Phase 4: Testing / Verification

- [x] 4.1 Extend `api/tests/test_program_service.py` for metadata create/list mapping and exercise list delegation.
- [x] 4.2 Add integration test: `POST /programs/` creates program for owned diagnostic and rejects unowned diagnostic.
- [x] 4.3 Add integration test: `GET /programs/` returns only authenticated doctor's programs and supports `diagnostic_id`/`patient_id` filters.
- [x] 4.4 Add integration test: `GET /programs/{program_id}/exercises` lists assigned exercises and rejects unowned program.
- [x] 4.5 Run `api/.venv/bin/python -m pytest api/tests -q`.
- [x] 4.6 If PostgreSQL is available, run `RUN_INTEGRATION=1 ... pytest api/tests/integration -q`.
