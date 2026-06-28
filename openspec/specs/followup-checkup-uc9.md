# Specification: Follow-up Check-up (UC-09, FR-07, AC-14)

This document contains two specs:

1. `api-followup-checkup-uc9` — the Follow-up Check-up REST API.
2. `ui-followup-checkup-uc9` — the `FollowupCheckupPanel` doctor-facing UI.

UC-09 lets a Doctor summarize a patient's progress across a rehabilitation period by
aggregating Exercise Reports (UC-08) of a single Rehab Program into a period-bounded
Follow-up Check-up. This satisfies AC-14 and FR-07 and mirrors the UC-08 vertical slice.

---

# 1. API Specification: `api-followup-checkup-uc9`

## Purpose

Define the Follow-up Check-up API that aggregates Exercise Reports of a single Rehab
Program into a period-bounded, manually summarized check-up. Check-ups are persisted in
the canonical `clinical.followup_checkup` / `clinical.followup_checkup_report` tables,
governed by the existing RLS policies (`fchk_staff`, `fchk_self`, `fcr_staff`,
`fcr_self`). The API mirrors the UC-08 reporting slice (`api/app/reporting/`) in a new
`api/app/followup/` module.

## Conventions

- Roles: `medical` (doctor, full access), `patient` (own data only via RLS), `technician`
  (no access to follow-up endpoints).
- Authorization failures return `403`; missing resources return `404`; malformed bodies
  or business-rule violations return `422`. A patient accessing another patient's data
  MUST receive `404` (RLS hides existence), not `403`.
- All UUIDs are returned as strings; timestamps as ISO-8601 UTC; dates as `YYYY-MM-DD`.
- `period_end` MUST be greater than or equal to `period_start`.
- The selected `exercise_report_id` list MUST be non-empty.
- `patient_id` is NEVER caller-supplied; it is derived server-side.

## Requirements

### Requirement: Map the ORM to the canonical clinical schema

The system MUST map the follow-up ORM to `clinical.followup_checkup` and
`clinical.followup_checkup_report` (many-to-many via the link table), and MUST NOT
reference the obsolete `reporting.followup_checkup` table (denormalized
`report_ids uuid[]`, wrong `reporting` schema, no link table) present in
`api/migrations/versions/0001_init.py`. If the legacy `reporting.followup_checkup` table
is live in the target environment, a corrective Alembic migration MUST be added.

#### Scenario: ORM targets the canonical tables

- GIVEN the new follow-up ORM in `api/app/followup/models.py`
- WHEN check-up rows are created or read
- THEN persistence targets `clinical.followup_checkup` and linked reports live in
  `clinical.followup_checkup_report`
- AND no code references the `reporting.followup_checkup` schema.

### Requirement: Derive patient_id server-side

The system MUST derive `patient_id` for a new check-up via the
`RehabProgram → Diagnostic.patient_id` join, using the body's `rehab_program_id`.
`RehabProgram` has no direct `patient_id`; omitting this join would violate the
`NOT NULL` constraint on `clinical.followup_checkup.patient_id`. The API MUST ignore any
caller-supplied `patient_id`.

#### Scenario: patient_id resolved from the program's diagnostic

- GIVEN a valid `rehab_program_id` whose `Diagnostic` references patient P
- WHEN a `medical` user creates a check-up
- THEN the persisted `followup_checkup.patient_id` equals P
- AND any `patient_id` present in the request body is ignored.

#### Scenario: Program has no resolvable patient

- GIVEN a `rehab_program_id` that does not exist or has no associated `Diagnostic`
- WHEN a `medical` user POSTs `/followup-checkups`
- THEN the system responds `404` and creates nothing.

### Requirement: Create a follow-up check-up (POST /followup-checkups)

- Method/path: `POST /followup-checkups`
- Roles: `medical` only.
- Request body:
  ```json
  {
    "rehab_program_id": "uuid",
    "exercise_report_ids": ["uuid", "..."],
    "period_start": "YYYY-MM-DD",
    "period_end": "YYYY-MM-DD",
    "summary": "string | null (optional)"
  }
  ```
- Behavior: insert one `followup_checkup` row (with `created_by` = the resolving doctor
  from `db.info["identity_id"] → Doctor.identity_id`, `patient_id` derived per the rule
  above), `db.flush()` to materialize the PK, then bulk-insert one
  `followup_checkup_report` link row per `exercise_report_id`.
- Response: `201` with `{ "followup_checkup_id": "uuid" }`.
- Status codes: `201` created; `403` non-medical; `404` unknown program or report;
  `422` invalid period, empty report list, or cross-program report.

#### Scenario: Doctor creates a check-up

- GIVEN an authenticated `medical` user and a valid body with one or more
  `exercise_report_ids` that all belong to `rehab_program_id`
- WHEN they POST `/followup-checkups`
- THEN the system inserts a `followup_checkup` (with `created_by` = the doctor and
  derived `patient_id`) and one link row per report id
- AND responds `201` with `{ "followup_checkup_id" }`.

#### Scenario: Non-medical role rejected

- GIVEN an authenticated `patient` or `technician` user
- WHEN they POST `/followup-checkups`
- THEN the system responds `403` and creates nothing.

#### Scenario: Empty report list

- GIVEN a body where `exercise_report_ids` is empty or missing
- WHEN a `medical` user POSTs `/followup-checkups`
- THEN the system responds `422` and creates nothing.

#### Scenario: Invalid period

- GIVEN a body where `period_end` is earlier than `period_start`
- WHEN a `medical` user POSTs `/followup-checkups`
- THEN the system responds `422` and creates nothing.

#### Scenario: Cross-program report rejected

- GIVEN a body where at least one `exercise_report_id` belongs to a Rehab Program other
  than the body's `rehab_program_id`
- WHEN a `medical` user POSTs `/followup-checkups`
- THEN the system responds `422` with a message identifying the offending report(s)
  (e.g. `"exercise_report {id} does not belong to rehab_program {program_id}"`)
- AND creates nothing (atomic).

#### Scenario: Unknown program or report

- GIVEN a body referencing a non-existent `rehab_program_id` or `exercise_report_id`
- WHEN a `medical` user POSTs `/followup-checkups`
- THEN the system responds `404` and creates nothing (atomic).

### Requirement: List check-ups for a program (GET /programs/{program_id}/followup-checkups)

The system MUST return all follow-up check-ups for a program to `medical` or `patient`
users, each item containing `followup_checkup_id`, `rehab_program_id`, `patient_id`,
`period_start`, `period_end`, `summary`, `created_by`, `created_at`, and `report_count`.
RLS filters rows transparently per the active DB role.

#### Scenario: Doctor lists program check-ups

- GIVEN a `medical` user and a program with two check-ups
- WHEN they GET `/programs/{program_id}/followup-checkups`
- THEN the system responds `200` with both items, each including `report_count`.

#### Scenario: Patient lists own program check-ups

- GIVEN a `patient` user whose program matches `program_id`
- WHEN they GET `/programs/{program_id}/followup-checkups`
- THEN the system responds `200` with only the check-ups they are entitled to see via
  the `fchk_self` RLS policy.

#### Scenario: Patient requests another patient's program

- GIVEN a `patient` user and a `program_id` belonging to another patient
- WHEN they GET `/programs/{program_id}/followup-checkups`
- THEN the system responds `200` with an empty list (RLS hides rows) and leaks no data.

#### Scenario: Technician denied

- GIVEN a `technician` user
- WHEN they GET `/programs/{program_id}/followup-checkups`
- THEN the system responds `403`.

### Requirement: Return full check-up detail (GET /followup-checkups/{id})

The system MUST return, to `medical` or `patient` users, the full detail of a check-up:
all list fields PLUS a `reports` array. Each entry MUST carry the linked report's
`exercise_report_id`, `program_exercise_id`, `period_start`, `period_end`, `summary`,
and `recording_count`.

#### Scenario: Doctor reads full detail

- GIVEN a `medical` user and an existing check-up with two linked reports
- WHEN they GET `/followup-checkups/{id}`
- THEN the system responds `200` with the check-up fields and a `reports` array of two
  entries, each carrying its report metadata and `recording_count`.

#### Scenario: Patient reads own check-up

- GIVEN a `patient` user entitled via the `fchk_self` RLS policy
- WHEN they GET `/followup-checkups/{id}`
- THEN the system responds `200` with the same shape.

#### Scenario: Check-up not found or not owned

- GIVEN an `id` that does not exist, or a check-up belonging to another patient
- WHEN a user GETs `/followup-checkups/{id}`
- THEN the system responds `404`.

#### Scenario: Technician denied

- GIVEN a `technician` user
- WHEN they GET `/followup-checkups/{id}`
- THEN the system responds `403`.

### Requirement: Update check-up summary (PATCH /followup-checkups/{id})

The system MUST allow a `medical` user to update the `summary` field of an existing
check-up via `PATCH /followup-checkups/{id}` with body `{ "summary": "string | null" }`,
responding `204` on success. Other fields (period, reports, program, patient) are
immutable via PATCH. This is full parity with UC-08.

#### Scenario: Doctor updates the summary

- GIVEN a `medical` user and an existing check-up
- WHEN they PATCH `/followup-checkups/{id}` with a new `summary`
- THEN the system updates only the `summary` and responds `204`.

#### Scenario: Non-medical role rejected

- GIVEN a `patient` or `technician` user
- WHEN they PATCH `/followup-checkups/{id}`
- THEN the system responds `403` and changes nothing.

#### Scenario: Check-up not found

- GIVEN an `id` that does not exist or is not visible via RLS
- WHEN a `medical` user PATCHes `/followup-checkups/{id}`
- THEN the system responds `404`.

### Requirement: Delete a check-up (DELETE /followup-checkups/{id})

The system MUST allow a `medical` user to delete a check-up via
`DELETE /followup-checkups/{id}`, responding `204`. Deletion MUST cascade to the
`clinical.followup_checkup_report` link rows (via `ON DELETE CASCADE`); linked
`clinical.exercise_report` rows MUST NOT be affected. This is full parity with UC-08.

#### Scenario: Doctor deletes a check-up

- GIVEN a `medical` user and an existing check-up with linked reports
- WHEN they DELETE `/followup-checkups/{id}`
- THEN the system removes the check-up and its `followup_checkup_report` link rows
- AND the underlying `exercise_report` rows remain intact
- AND responds `204`.

#### Scenario: Non-medical role rejected

- GIVEN a `patient` or `technician` user
- WHEN they DELETE `/followup-checkups/{id}`
- THEN the system responds `403` and deletes nothing.

#### Scenario: Check-up not found

- GIVEN an `id` that does not exist or is not visible via RLS
- WHEN a `medical` user DELETEs `/followup-checkups/{id}`
- THEN the system responds `404`.

---

# 2. UI Specification: `ui-followup-checkup-uc9`

## Purpose

Expose follow-up check-up management to the doctor's view within the Rehabilitation
Programs screen. The `FollowupCheckupPanel` mirrors the `ExerciseReportsPanel` (UC-08)
layout and wires to the API defined above. The doctor can: list check-ups for the
selected program, create a check-up by choosing a period and selecting reports
(auto-selected by period, deselectable), edit a check-up summary, view a check-up's
linked reports, and delete a check-up.

## Conventions

- Feature lives under `web/src/features/diagnostics/` following existing patterns.
- API layer: new `web/src/api/followupCheckups.ts` module with typed functions + a
  `FollowupCheckupApi` interface.
- Feature API: `DiagnosticFeatureApi` in `web/src/features/diagnostics/api.ts` extended
  with `FollowupCheckupApi`.
- Hooks: added to `web/src/features/diagnostics/hooks.ts` using `@tanstack/react-query`;
  query key `["followup-checkups", programId]`; invalidate on every mutation.
- Component: `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx`.
- Integration point: `RehabProgramPanel` shows a "Show Follow-up Check-ups" /
  "Hide Follow-up Check-ups" toggle button that mounts the panel when a program is
  selected and the detail view is active.
- Styling follows the plain-CSS class conventions in `web/src/styles.css` (no Tailwind,
  no shadcn). No new routes; the panel renders inline.

## Requirements

### Requirement: API module for follow-up check-ups

The system MUST provide a typed API module `web/src/api/followupCheckups.ts` exposing:

- `createCheckup(body: CheckupIn): Promise<{ followup_checkup_id: string }>`
  → `POST /followup-checkups`
- `listProgramCheckups(programId: string): Promise<CheckupListItem[]>`
  → `GET /programs/{program_id}/followup-checkups`
- `getCheckupDetail(id: string): Promise<CheckupDetailOut>`
  → `GET /followup-checkups/{id}`
- `updateCheckupSummary(id: string, summary: string | null): Promise<void>`
  → `PATCH /followup-checkups/{id}`
- `deleteCheckup(id: string): Promise<void>`
  → `DELETE /followup-checkups/{id}`

Types required:
```ts
export type CheckupIn = {
  rehab_program_id: string;
  exercise_report_ids: string[];
  period_start: string;   // "YYYY-MM-DD"
  period_end: string;
  summary?: string | null;
};

export type CheckupListItem = {
  followup_checkup_id: string;
  rehab_program_id: string;
  patient_id: string;
  period_start: string;
  period_end: string;
  summary?: string | null;
  created_by: string;
  created_at: string;
  report_count: number;
};

export type CheckupReportEntry = {
  exercise_report_id: string;
  program_exercise_id: string;
  period_start: string;
  period_end: string;
  summary?: string | null;
  recording_count: number;
};

export type CheckupDetailOut = Omit<CheckupListItem, "report_count"> & {
  reports: CheckupReportEntry[];
};
```

#### Scenario: Check-up list is fetched on panel open

- GIVEN a doctor opens the Follow-up Check-ups panel for a program
- WHEN `listProgramCheckups(programId)` is called
- THEN the panel renders a list of check-up cards or an empty state.

#### Scenario: Check-up detail is fetched on expand

- GIVEN a check-up card is expanded
- WHEN `getCheckupDetail(id)` is called
- THEN the linked-reports table shows each report with its period and `recording_count`.

### Requirement: Create check-up form with period-driven auto-selection

The panel MUST show a "New Check-up" button. Clicking it opens an inline create form with:

- Date inputs `period_start` and `period_end`.
- A multi-select list of the program's available Exercise Reports (fetched via
  `listProgramReports(programId)` from the UC-08 reports API).
- An optional `summary` textarea.

Auto-selection behavior:

- When both `period_start` and `period_end` are set, the form MUST auto-select every
  available report whose period falls within `[period_start, period_end]`.
- The doctor MAY deselect any auto-selected report and MAY select reports outside the
  range. The final submitted set is whatever is checked at submit time.

On submit:

1. Validate `period_end >= period_start`; show inline error if not.
2. Validate at least one report is selected; show error "Select at least one report" if not.
3. Call `createCheckup({ rehab_program_id: programId, exercise_report_ids, period_start, period_end, summary })`.
4. On success, invalidate `["followup-checkups", programId]` and close the form.
5. On `422` cross-program error, show the API message inline.

#### Scenario: Period auto-selects matching reports

- GIVEN the create form is open and the program has reports inside and outside a range
- WHEN the doctor sets `period_start` and `period_end`
- THEN every report whose period is within the range is checked by default
- AND reports outside the range are left unchecked.

#### Scenario: Doctor deselects an auto-selected report

- GIVEN auto-selection has checked three reports
- WHEN the doctor unchecks one and submits
- THEN `createCheckup` is called with only the two still-checked `exercise_report_ids`.

#### Scenario: Doctor creates a check-up successfully

- GIVEN a valid period and at least one selected report
- WHEN the doctor submits the form
- THEN `createCheckup` is called and the check-up list refreshes.

#### Scenario: No report selected

- GIVEN the doctor has deselected every report
- WHEN they submit the form
- THEN an inline error "Select at least one report" is shown and no API call is made.

#### Scenario: Invalid date range

- GIVEN `period_end` is earlier than `period_start`
- WHEN the doctor submits
- THEN an inline error is shown and no API call is made.

### Requirement: List view of check-ups

The panel MUST render existing check-ups as cards. Each card MUST show the period
(`period_start – period_end`), the linked report count, and a summary excerpt
(truncated). An empty state MUST be shown when the program has no check-ups.

#### Scenario: Empty list

- GIVEN a program with no check-ups
- WHEN the panel loads
- THEN an empty-state message (e.g. "No follow-up check-ups yet") is shown.

#### Scenario: List with items

- GIVEN a program with two check-ups
- WHEN the panel loads
- THEN two cards are shown, each with its period, report count, and summary excerpt.

### Requirement: Detail and edit summary

Each check-up card MUST be expandable to show its linked reports (via
`getCheckupDetail`) and an "Edit Summary" action. Clicking "Edit Summary" replaces the
summary text with a `<textarea>` + Save / Cancel buttons. Save calls
`updateCheckupSummary(id, summary)` and, on success, invalidates the list query and
shows the updated text. A "Delete" action MUST also be available on the card.

#### Scenario: Doctor expands a check-up

- GIVEN a check-up card in collapsed view
- WHEN the doctor expands it
- THEN the linked-reports table is shown with each report's period and `recording_count`.

#### Scenario: Doctor edits a summary

- GIVEN an expanded check-up card
- WHEN the doctor clicks "Edit Summary", changes the text, and clicks Save
- THEN `updateCheckupSummary` is called, the list query is invalidated, and the panel
  shows the updated summary.

### Requirement: Delete check-up

Each check-up card MUST show a "Delete" button. Clicking it shows a browser `confirm()`
dialog. On confirmation, the panel calls `deleteCheckup(id)`, invalidates the
`["followup-checkups", programId]` query on success, and shows a toast error on failure.

#### Scenario: Doctor deletes a check-up

- GIVEN a check-up card
- WHEN the doctor clicks Delete and confirms
- THEN `deleteCheckup(id)` is called and the check-up is removed from the list on success.

#### Scenario: Doctor cancels deletion

- GIVEN a check-up card
- WHEN the doctor clicks Delete and dismisses the confirm dialog
- THEN no API call is made and the check-up remains.

### Requirement: Integration into RehabProgramPanel

`RehabProgramPanel` (`web/src/features/diagnostics/components/RehabProgramPanel.tsx`)
MUST render a "Show Follow-up Check-ups" / "Hide Follow-up Check-ups" toggle button when
a program is selected and the detail view is active, alongside the existing Exercise
Reports toggle. The toggle mounts/unmounts
`<FollowupCheckupPanel programId={selectedProgramId} api={api} />`.

#### Scenario: Toggle opens panel

- GIVEN a program is selected in the detail view
- WHEN the doctor clicks "Show Follow-up Check-ups"
- THEN `FollowupCheckupPanel` is mounted and fetches the check-up list.

#### Scenario: Toggle hides panel

- GIVEN the follow-up panel is open
- WHEN the doctor clicks "Hide Follow-up Check-ups"
- THEN the panel is unmounted.
