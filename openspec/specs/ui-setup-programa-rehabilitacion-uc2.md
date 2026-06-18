# UI Specification: Setup Programa de Rehabilitación (UC-02)

## Purpose

Define doctor-facing UI behavior for UC-02: create rehab programs from diagnostics, assign exercises, and search/view rehab programs owned by the authenticated doctor.

## Requirements

### Requirement: Rehab program creation (AC-04)

The UI MUST let a medical user create a rehab program linked to a selected diagnostic they can access.

#### Scenario: Create program from diagnostic detail

- GIVEN a medical user is viewing a diagnostic detail
- WHEN the user chooses setup rehab program and submits valid program metadata
- THEN the UI sends `POST /programs/` with the diagnostic id
- AND the created program appears in the program list/detail UI.

#### Scenario: Create program with minimum fields

- GIVEN a medical user is creating a rehab program
- WHEN only the diagnostic context is required and optional fields are blank
- THEN the UI can submit a valid request without `physiotherapist_id`.

#### Scenario: Program creation forbidden

- GIVEN a medical user opens a diagnostic they cannot use for program setup
- WHEN the API returns `403` during program creation
- THEN the UI displays an authorization error and does not show a false success.

### Requirement: Rehab program search/detail (AC-06)

The UI MUST let a medical user find and inspect rehab programs visible to that user from both the patient/diagnostic workflow and a top-level Rehab programs navigation entry.

#### Scenario: List programs for selected diagnostic

- GIVEN a medical user has selected a patient and diagnostic
- WHEN the program list loads
- THEN the UI requests `GET /programs/?diagnostic_id=<diagnostic_id>`
- AND displays loading, empty, and error states.

#### Scenario: Doctor-wide program search from top-level navigation

- GIVEN a medical user uses the top-level Rehab programs navigation entry
- WHEN the program list loads
- THEN the UI requests `GET /programs/?limit=&offset=` without requiring a diagnostic id
- AND displays owned programs with loading, empty and error states.

#### Scenario: Open program detail

- GIVEN the UI displays a rehab program list
- WHEN the user opens a program
- THEN the UI shows program status, dates, name, diagnostic id, and exercise table entry point.

### Requirement: Exercise table setup (AC-05)

The UI MUST let a medical user assign catalog exercises to a selected rehab program and view the assigned exercise table.

#### Scenario: Assign exercise to program

- GIVEN a medical user is viewing a rehab program and catalog exercises are loaded
- WHEN the user selects an exercise and submits optional `pauta`
- THEN the UI sends `POST /programs/{program_id}/exercises`
- AND refreshes the assigned exercise list.

#### Scenario: Program has no exercises

- GIVEN a medical user opens a rehab program without assigned exercises
- WHEN the exercise list request succeeds
- THEN the UI shows an empty state and an assign exercise action.

#### Scenario: Exercise assignment fails

- GIVEN a medical user submits an exercise assignment
- WHEN the API returns `404` or `403`
- THEN the UI displays the error and keeps the form recoverable.

### Requirement: Traceable UI tests

The implementation MUST include frontend tests traceable to UC-02 AC-04, AC-05 and AC-06.

#### Scenario: AC-linked tests exist

- GIVEN the UI implementation is complete
- WHEN `npm --prefix web test -- --run` is executed
- THEN tests cover program creation, program search/detail, and exercise assignment states.
