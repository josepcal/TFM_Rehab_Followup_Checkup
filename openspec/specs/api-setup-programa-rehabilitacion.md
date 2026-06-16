# API Specification: Setup Programa de Rehabilitación (UC-02)

## Purpose

Define the doctor-facing API behavior for creating rehab programs, assigning exercises, listing assigned exercises, and searching programs owned by the authenticated Medical Specialist.

## Requirements

### Requirement: Program creation from diagnostic

The system MUST allow a medical user to create a rehab program linked to an existing diagnostic they are authorized to access.

#### Scenario: Create program with minimum payload

- GIVEN an authenticated medical user and an owned diagnostic
- WHEN `POST /programs/` is sent with `diagnostic_id`
- THEN the API returns `201` with `ProgramOut`
- AND the program is linked to the diagnostic.

#### Scenario: Create program with metadata

- GIVEN an authenticated medical user and an owned diagnostic
- WHEN `POST /programs/` includes `name`, `start_date`, `end_date`, or `physiotherapist_id`
- THEN the API persists and returns those fields when valid.

#### Scenario: Reject unauthorized diagnostic

- GIVEN an authenticated medical user and a diagnostic authored by another doctor
- WHEN `POST /programs/` is requested for that diagnostic
- THEN the API returns `403`.

### Requirement: Program search for doctor

The system MUST allow a medical user to list rehab programs linked to diagnostics they own, with pagination and optional filters.

#### Scenario: Doctor-wide program search

- GIVEN an authenticated medical user with several rehab programs
- WHEN `GET /programs/?limit=20&offset=0` is requested
- THEN the API returns only that doctor's programs in a paginated envelope.

#### Scenario: Filter by diagnostic

- GIVEN an authenticated medical user with programs across diagnostics
- WHEN `GET /programs/?diagnostic_id=<owned-diagnostic>` is requested
- THEN only programs for that diagnostic are returned.

#### Scenario: Filter by patient

- GIVEN an authenticated medical user with programs across patients
- WHEN `GET /programs/?patient_id=<patient>` is requested
- THEN only programs linked to that patient's diagnostics and owned by the doctor are returned.

### Requirement: Program detail authorization

The system MUST allow a medical user to retrieve a rehab program only when the linked diagnostic is authorized for that user.

#### Scenario: Retrieve owned program

- GIVEN an authenticated medical user and an owned program
- WHEN `GET /programs/{program_id}` is requested
- THEN the API returns `200` with `ProgramOut`.

#### Scenario: Reject unowned program

- GIVEN an authenticated medical user and a program linked to another doctor's diagnostic
- WHEN `GET /programs/{program_id}` is requested
- THEN the API returns `403`.

### Requirement: Exercise table setup

The system MUST allow a medical user to assign catalog exercises to an owned rehab program and list the resulting exercise table.

#### Scenario: Assign exercise

- GIVEN an authenticated medical user, an owned program, and an existing rehab exercise
- WHEN `POST /programs/{program_id}/exercises` is sent with `exercise_id` and optional `pauta`
- THEN the API returns `201` with `ProgramExerciseOut`.

#### Scenario: List assigned exercises

- GIVEN an authenticated medical user and an owned program with assigned exercises
- WHEN `GET /programs/{program_id}/exercises` is requested
- THEN the API returns a paginated list of `ProgramExerciseOut` rows.

#### Scenario: Reject missing exercise

- GIVEN an authenticated medical user and an owned program
- WHEN exercise assignment references an unknown exercise
- THEN the API returns `404`.
