# UI Specification: Doctor Diagnostic UI (UC-01)

**Change**: `ui-medico-diagnostico-uc1`  
**Date**: 2026-06-14  
**Status**: Draft Specification  
**Scope**: Frontend/UI only for UC-01 Diagnostic Assessment

---

## Purpose

This specification defines the doctor-facing UI behavior for UC-01. It covers AC-01 and AC-03 only: a medical user can find/select a patient, view diagnostic history, create a diagnostic, inspect diagnostic detail, and update diagnostic fields.

Out of scope: UC-02 programs/exercises, recordings, metrics, reports, follow-up, patient UI, and LLM insight.

---

## Requirements

### Requirement: Medical user access

The UI MUST restrict the UC-01 diagnostic screens to authenticated users with the `medical` role. The SPA MUST use the auth shell defined for Keycloak-compatible authentication and MUST NOT rely on UI-only role checks as security.

#### Scenario: Medical user opens diagnostic UI

- GIVEN an authenticated user with role `medical`
- WHEN the user opens the diagnostic UI
- THEN the UI shows the UC-01 diagnostic workspace
- AND the UI can request patient and diagnostic data from the API

#### Scenario: Non-medical user is blocked

- GIVEN an authenticated user without role `medical`
- WHEN the user opens the diagnostic UI
- THEN the UI shows an access denied state
- AND no diagnostic mutation form is usable

---

### Requirement: Patient search and diagnostic history (AC-01)

The UI MUST provide a patient search or selection flow that lets a medical user choose a patient and view that patient's diagnostic history using the available patient and diagnostic API contracts.

#### Scenario: Doctor views diagnostic history

- GIVEN a medical user is on the diagnostic workspace
- WHEN the user selects a patient
- THEN the UI requests the patient's diagnostic history
- AND the UI displays the returned diagnostics with loading, empty, and error states

#### Scenario: Patient has no diagnostics

- GIVEN a medical user selects a patient with no diagnostic history
- WHEN the diagnostic history request succeeds
- THEN the UI displays an empty state explaining that no diagnostics exist yet
- AND the UI offers the create diagnostic action

#### Scenario: Diagnostic history request is forbidden

- GIVEN a medical user selects a patient or diagnostic they cannot access
- WHEN the API returns 403
- THEN the UI displays an authorization error
- AND the UI MUST NOT show stale diagnostic records for that patient

---

### Requirement: Create diagnostic (AC-03)

The UI MUST provide a create diagnostic form linked to the selected patient. The form MUST collect `dolencia` and optional `descripcion`; it MUST NOT ask the user to provide `doctor_id`.

#### Scenario: Doctor creates diagnostic

- GIVEN a medical user has selected a patient
- WHEN the user submits valid `dolencia` and optional `descripcion`
- THEN the UI sends `POST /diagnostics/` with the selected `patient_id`
- AND the UI displays the created diagnostic or refreshes the diagnostic history

#### Scenario: Create form validation fails

- GIVEN a medical user is filling the create diagnostic form
- WHEN `dolencia` is empty or exceeds 500 characters
- THEN the UI prevents submission or displays the API validation error
- AND no `doctor_id` field is shown or sent by the UI

#### Scenario: Patient no longer exists

- GIVEN a medical user selected a patient that no longer exists
- WHEN create diagnostic returns 404
- THEN the UI displays a patient-not-found error
- AND the form remains recoverable without losing typed data unnecessarily

---

### Requirement: Diagnostic detail and edit

The UI MUST let a medical user open a diagnostic detail view and update editable diagnostic fields. The UI SHOULD display MVP attestation metadata when the API returns it.

#### Scenario: Doctor views diagnostic detail

- GIVEN a medical user sees diagnostic history
- WHEN the user opens a diagnostic
- THEN the UI requests `GET /diagnostics/{diagnostic_id}`
- AND displays `dolencia`, `descripcion`, timestamps, and any returned attestation metadata

#### Scenario: Doctor updates diagnostic fields

- GIVEN a medical user is viewing a diagnostic they can edit
- WHEN the user submits changes to `dolencia` or `descripcion`
- THEN the UI sends `PATCH /diagnostics/{diagnostic_id}`
- AND the UI displays the updated diagnostic after success

#### Scenario: Update is forbidden

- GIVEN a medical user opens or edits a diagnostic they cannot access
- WHEN the API returns 403
- THEN the UI displays an authorization error
- AND the UI MUST NOT show the edit form as successfully saved

---

### Requirement: UI testability and traceability

The UI implementation MUST include tests or test cases traceable to UC-01, AC-01, and AC-03. Tests SHOULD use Given/When/Then naming or docstrings where practical.

#### Scenario: AC-linked tests exist

- GIVEN the UI implementation is complete
- WHEN the frontend test suite runs
- THEN tests cover patient selection/history, create diagnostic, detail display, edit success, and error states
- AND test names or metadata reference AC-01 or AC-03
