# API Specification: Exercise Report for Doctor View (UC-07 / UC-08, D14)

## Purpose

Define the reporting API that combines recordings, metrics, and AI insights into
exercise reports for the doctor's view, and exposes the per-recording AI insight.
Reports are persisted in the canonical `clinical.exercise_report` /
`clinical.exercise_report_recording` tables, governed by the existing RLS policies
(`report_staff`, `report_self`). This spec covers REQ-1..REQ-5 only; the working
recording/metrics/exercise-list endpoints are out of scope.

## Conventions

- Roles: `medical` (doctor, full access), `patient` (own data only), `technician`
  (no access to reporting endpoints).
- Authorization failures return `403`; missing resources return `404`;
  malformed bodies return `422`. A patient accessing another patient's data MUST
  receive `404` (RLS hides existence), not `403`.
- All UUIDs are returned as strings; timestamps as ISO-8601 UTC.

## Requirements

### Requirement: Map the ORM to the canonical clinical schema

The system MUST map the report ORM to `clinical.exercise_report` and
`clinical.exercise_report_recording` (many-to-many via the link table), replacing
the previous incorrect `reporting.exercise_report` model that carried a single
`recording_id`, `metrics_id`, and `insight_id`.

#### Scenario: ORM targets the canonical tables

- GIVEN the corrected reporting ORM
- WHEN report rows are created or read
- THEN persistence targets `clinical.exercise_report` and linked recordings live in
  `clinical.exercise_report_recording`
- AND no code references the non-existent `reporting.exercise_report` schema.

### Requirement: Create an exercise report (POST /reports)

The system MUST allow a `medical` user to create an exercise report from a body of
`{ program_exercise_id, recording_ids[], period_start, period_end, summary? }`,
inserting one `exercise_report` row plus one `exercise_report_recording` row per
recording id, and returning `{ exercise_report_id }`.

#### Scenario: Doctor creates a report

- GIVEN an authenticated `medical` user and a valid body with one or more `recording_ids`
- WHEN they POST `/reports`
- THEN the system inserts an `exercise_report` (with `created_by` = the doctor,
  `rehab_program_id` derived from `program_exercise_id`) and one link row per recording
- AND responds `201` with `{ exercise_report_id }`.

#### Scenario: Non-medical role rejected

- GIVEN an authenticated `patient` or `technician` user
- WHEN they POST `/reports`
- THEN the system responds `403` and creates nothing.

#### Scenario: Invalid period

- GIVEN a body where `period_end` is earlier than `period_start`
- WHEN a `medical` user POSTs `/reports`
- THEN the system responds `422` and creates nothing.

#### Scenario: Unknown program_exercise or recording

- GIVEN a body referencing a non-existent `program_exercise_id` or `recording_id`
- WHEN a `medical` user POSTs `/reports`
- THEN the system responds `404` and creates nothing (atomic).

### Requirement: List reports for a program (GET /programs/{program_id}/reports)

The system MUST return all exercise reports for a program to `medical` or `patient`
users, each item containing `exercise_report_id`, `program_exercise_id`,
`period_start`, `period_end`, `summary`, `created_by`, `attested_at`, and
`recording_count`.

#### Scenario: Doctor lists program reports

- GIVEN a `medical` user and a program with two reports
- WHEN they GET `/programs/{program_id}/reports`
- THEN the system responds `200` with both items, each including `recording_count`.

#### Scenario: Patient lists own program reports

- GIVEN a `patient` user whose `rehab_program` matches `program_id`
- WHEN they GET `/programs/{program_id}/reports`
- THEN the system responds `200` with only the reports they are entitled to see via RLS.

#### Scenario: Patient requests another patient's program

- GIVEN a `patient` user and a `program_id` belonging to another patient
- WHEN they GET `/programs/{program_id}/reports`
- THEN the system responds `404` (or an empty list, per RLS) and leaks no data.

#### Scenario: Technician denied

- GIVEN a `technician` user
- WHEN they GET `/programs/{program_id}/reports`
- THEN the system responds `403`.

### Requirement: Return full report detail (GET /reports/{report_id})

The system MUST return, to `medical` or `patient` users, the full detail of a report:
all list fields from the prior requirement PLUS, for each linked recording,
`recording_id`, `recording_date`, `duration_seconds`, `media_status`, the metrics
`status` and `raw_json`, and the insight `insight_text` and `model_used`.

#### Scenario: Doctor reads full detail

- GIVEN a `medical` user and an existing report with two linked recordings
- WHEN they GET `/reports/{report_id}`
- THEN the system responds `200` with the report fields and a `recordings` array of two
  entries, each carrying recording metadata, metrics `status`/`raw_json`, and insight
  `insight_text`/`model_used`.

#### Scenario: Recording without metrics or insight

- GIVEN a linked recording that has no `metric_result` or no `ai_insight` yet
- WHEN a `medical` user GETs `/reports/{report_id}`
- THEN the entry still appears with its recording metadata and `null` for the missing
  metrics/insight fields.

#### Scenario: Patient reads own report

- GIVEN a `patient` user entitled via `report_self` RLS
- WHEN they GET `/reports/{report_id}`
- THEN the system responds `200` with the same shape.

#### Scenario: Report not found or not owned

- GIVEN a `report_id` that does not exist, or belongs to another patient
- WHEN a user GETs `/reports/{report_id}`
- THEN the system responds `404`.

#### Scenario: Technician denied

- GIVEN a `technician` user
- WHEN they GET `/reports/{report_id}`
- THEN the system responds `403`.

### Requirement: Expose the AI insight for a recording (GET /recordings/{id}/insight)

The system MUST expose the `metrics.ai_insight` for a recording to `medical` or
`patient` users, returning `{ insight_id, recording_id, insight_text, model_used,
generated_at }`, resolved via the recording's `metric_result`.

#### Scenario: Insight exists

- GIVEN a recording whose `metric_result` has an associated `ai_insight`
- WHEN a `medical` or entitled `patient` user GETs `/recordings/{id}/insight`
- THEN the system responds `200` with `insight_id`, `recording_id`, `insight_text`,
  `model_used`, and `generated_at`.

#### Scenario: No insight yet

- GIVEN a recording with no `ai_insight` generated
- WHEN an authorized user GETs `/recordings/{id}/insight`
- THEN the system responds `404`.

#### Scenario: Patient requests another patient's insight

- GIVEN a `patient` user and a recording belonging to another patient
- WHEN they GET `/recordings/{id}/insight`
- THEN the system responds `404` and leaks no data.

#### Scenario: Technician denied

- GIVEN a `technician` user
- WHEN they GET `/recordings/{id}/insight`
- THEN the system responds `403`.
