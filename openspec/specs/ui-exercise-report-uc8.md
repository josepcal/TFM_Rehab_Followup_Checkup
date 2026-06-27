# UI Specification: Exercise Reports Panel (UC-08)

## Purpose

Expose exercise report management to the doctor's view within the Rehabilitation Programs
screen. The panel replicates the `exercise-reports-panel` layout from `v0/` and wires it
to the real API defined in `openspec/specs/api-exercise-report-uc8.md`.

The doctor can: list reports for the selected program, create a new report (selecting
a program exercise + date range, auto-collecting recordings), edit a report's summary,
play any linked recording via the existing modal, and delete a report.

## Conventions

- Feature lives under `web/src/features/diagnostics/` following existing patterns.
- API layer: new `web/src/api/reports.ts` module with typed functions + a `ReportsApi` interface.
- Feature API: `DiagnosticFeatureApi` in `web/src/features/diagnostics/api.ts` extended with `ReportsApi`.
- Hooks: added to `web/src/features/diagnostics/hooks.ts` using `@tanstack/react-query`.
- Component: `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx`.
- Integration point: `RehabProgramPanel` shows a "Show Exercise Reports" toggle button that mounts the panel when a program is selected.
- Styling follows the plain-CSS class conventions in `web/src/styles.css` (no Tailwind, no shadcn).
- No new routes. The panel is rendered inline inside the existing program detail area.

## Requirements

### Requirement: API module for reports

The system MUST provide a typed API module `web/src/api/reports.ts` that exposes:

- `createReport(body: ReportIn): Promise<{ exercise_report_id: string }>`
  → `POST /reports`
- `listProgramReports(programId: string): Promise<ReportListItem[]>`
  → `GET /programs/{program_id}/reports`
- `getReportDetail(reportId: string): Promise<ReportDetailOut>`
  → `GET /reports/{report_id}`
- `deleteReport(reportId: string): Promise<void>`
  → `DELETE /reports/{report_id}` — NOTE: the API spec does not define a DELETE endpoint;
  the UI must guard deletion locally by calling a method that the API layer can stub as
  `not implemented` returning `501`, or omit DELETE from the API module entirely and disable
  the button if the API does not support it. **Decision**: implement `deleteReport` as a stub
  that throws `new Error("Delete not supported")` until the API spec adds the endpoint;
  the panel still shows the button but catches the error and shows a toast.
- `updateReportSummary(reportId: string, summary: string): Promise<void>`
  → No PATCH endpoint in the spec; store summary edit optimistically in local state only
  (no API call). The panel persists the edit in component state until the page is refreshed.

Types required:
```ts
export type ReportIn = {
  program_exercise_id: string;
  recording_ids: string[];
  period_start: string;   // ISO date "YYYY-MM-DD"
  period_end: string;
  summary?: string | null;
};

export type ReportListItem = {
  exercise_report_id: string;
  program_exercise_id: string;
  period_start: string;
  period_end: string;
  summary?: string | null;
  created_by: string;
  attested_at?: string | null;
  recording_count: number;
};

export type RecordingInsightEntry = {
  recording_id: string;
  recording_date?: string | null;
  duration_seconds?: number | null;
  media_status?: string | null;
  metrics_status?: string | null;
  raw_json?: Record<string, unknown> | null;
  insight_text?: string | null;
  model_used?: string | null;
};

export type ReportDetailOut = Omit<ReportListItem, "recording_count"> & {
  recordings: RecordingInsightEntry[];
};
```

#### Scenario: Report list is fetched on panel open

- GIVEN a doctor opens the Exercise Reports panel for a program
- WHEN `listProgramReports(programId)` is called
- THEN the panel renders a list of report cards or an empty state.

#### Scenario: Report detail is fetched on expand

- GIVEN a report card is expanded
- WHEN `getReportDetail(reportId)` is called
- THEN the recordings table shows the linked recordings with their metadata.

### Requirement: Create report form

The panel MUST show a "New Report" button. Clicking it opens an inline create form with:

- A `<select>` to pick the program exercise (populated from the existing
  `useProgramExercises` hook — already available in the feature).
- Date inputs `period_start` and `period_end`.
- A textarea for `summary` (optional).

On submit:

1. Validate that `period_end >= period_start`; show inline error if not.
2. Validate that a program exercise is selected.
3. Call `listExerciseRecordings(programExerciseId)` (already in `RecordingsApi`) to get
   recording IDs for that exercise.
4. If no recordings exist, show error "No recordings found for this exercise".
5. Otherwise call `createReport({ program_exercise_id, recording_ids, period_start, period_end, summary })`.
6. On success, invalidate `["reports", programId]` query and close the form.

#### Scenario: Doctor creates a report successfully

- GIVEN a program with at least one exercise that has recordings
- WHEN the doctor fills the form and submits
- THEN `createReport` is called with all recording IDs for that exercise
- AND the report list refreshes.

#### Scenario: No recordings for chosen exercise

- GIVEN the doctor selects an exercise with no recordings
- WHEN they submit the form
- THEN an error message "No recordings found for this exercise" is shown.

#### Scenario: Invalid date range

- GIVEN `period_end` is earlier than `period_start`
- WHEN the doctor submits
- THEN an inline error is shown and no API call is made.

### Requirement: Edit summary

Each report card MUST show an "Edit Summary" button. Clicking it replaces the summary
text with a `<textarea>` + Save / Cancel buttons. Save persists the edit in local state
(optimistic only — no PATCH endpoint). The updated text is displayed immediately.

#### Scenario: Doctor edits a summary

- GIVEN a report card in view mode
- WHEN the doctor clicks "Edit Summary", changes the text, and clicks Save
- THEN the panel shows the updated summary text.

### Requirement: Play recording

Each recording row in the expanded detail table MUST have a "Play" button that opens the
existing `ExerciseAnalysisModal` (already in `web/src/features/patient/ExerciseAnalysisModal.tsx`)
or a minimal inline audio element. Because the existing modal is scoped to the patient
portal, the panel MAY instead render a plain `<audio controls src="...">` element inline,
resolving the `storage_uri` from the recording detail. If `storage_uri` is not available
from the report detail endpoint, the button is disabled.

**Decision**: Since `ReportDetailOut.recordings` does not include `storage_uri`, the "Play"
button triggers `GET /recordings/{id}` via the existing `listExerciseRecordings` lookup
or a direct fetch. For simplicity, the button opens the `ExerciseAnalysisModal` passing
the `recording_id`; the modal already handles fetching its own data.

Actually, the `ExerciseAnalysisModal` is coupled to the patient portal API. Instead:
render a simple inline `<details>` block that shows the insight text and raw metrics JSON
when the row is expanded (no audio playback in this iteration). Mark the "Play" icon as
a toggle to expand/collapse the inline metrics view.

#### Scenario: Doctor expands a recording row

- GIVEN a report is open and the recordings table is visible
- WHEN the doctor clicks "View" on a recording row
- THEN the row expands to show `insight_text` and `raw_json` metrics inline.

### Requirement: Delete report

Each report card MUST show a "Delete Report" button. Clicking it shows a browser
`confirm()` dialog. On confirmation:

1. Optimistically remove the report from local list state.
2. Call `deleteReport(reportId)`.
3. On error, restore the report and show a toast error.

Because no DELETE endpoint exists in the API spec, `deleteReport` is a stub. The button
is visible but on click shows: "Delete is not yet supported by the API."

#### Scenario: Doctor attempts to delete

- GIVEN a report card
- WHEN the doctor clicks Delete and confirms
- THEN a message "Delete is not yet supported by the API." is shown.

### Requirement: Integration into RehabProgramPanel

`RehabProgramPanel` (`web/src/features/diagnostics/components/RehabProgramPanel.tsx`)
MUST render a "Show Exercise Reports" / "Hide Exercise Reports" toggle button below the
exercise table when a program is selected and the detail view is active.

The toggle mounts/unmounts `<ExerciseReportsPanel programId={selectedProgramId} api={api} />`.

#### Scenario: Toggle opens panel

- GIVEN a program is selected in the detail view
- WHEN the doctor clicks "Show Exercise Reports"
- THEN `ExerciseReportsPanel` is mounted and fetches the report list.

#### Scenario: Toggle hides panel

- GIVEN the reports panel is open
- WHEN the doctor clicks "Hide Exercise Reports"
- THEN the panel is unmounted.
