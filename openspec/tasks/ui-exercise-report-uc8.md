# Tasks: Exercise Reports UI (UC-08)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 280–380 |
| 400-line budget risk | Low-Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |

---

## Phase 1: API module — `web/src/api/reports.ts`

- [ ] 1.1 **File**: `web/src/api/reports.ts` (new). Define types `ReportIn`, `ReportListItem`,
  `RecordingInsightEntry`, `ReportDetailOut`. Define `ReportsApi` interface with methods:
  `createReport`, `listProgramReports`, `getReportDetail`, `deleteReport` (stub).
  Implement `createReportsApi(http: HttpClient): ReportsApi`. Map to:
  - `POST /reports` → `createReport`
  - `GET /programs/{program_id}/reports` → `listProgramReports`
  - `GET /reports/{report_id}` → `getReportDetail`
  - `deleteReport` throws `new Error("Delete is not yet supported by the API.")`.
  **Acceptance**: file imports cleanly; `ReportsApi` exports all four methods.

- [ ] 1.2 **File**: `web/src/features/diagnostics/api.ts`. Add `ReportsApi` to the
  `DiagnosticFeatureApi` intersection type. Import from `../../api/reports`.
  **Acceptance**: `DiagnosticFeatureApi` includes `createReport`, `listProgramReports`,
  `getReportDetail`, `deleteReport`.

- [ ] 1.3 **File**: `web/src/App.tsx`. Wire `createReportsApi(http)` into the `api` object
  passed to `DiagnosticWorkspace`. Follow the same pattern used for `createRecordingsApi`.
  **Acceptance**: the app builds without type errors; `api.listProgramReports` is callable.

---

## Phase 2: React Query hooks — `web/src/features/diagnostics/hooks.ts`

- [ ] 2.1 Add `useProgramReports(api, programId?: string)` hook. Uses `useQuery` with
  key `["reports", programId]`, calls `api.listProgramReports(programId)`, enabled when
  `Boolean(programId)`. **Acceptance**: returns `{ data, isLoading, error }`.

- [ ] 2.2 Add `useReportDetail(api, reportId?: string)` hook. Uses `useQuery` with
  key `["reports", "detail", reportId]`, calls `api.getReportDetail(reportId)`, enabled
  when `Boolean(reportId)`. **Acceptance**: returns query object.

- [ ] 2.3 Add `useCreateReport(api)` mutation hook. Uses `useMutation`, calls
  `api.createReport(body)`, on success invalidates `["reports", body.program_exercise_id]`
  — NOTE: we invalidate by `programId`, not `program_exercise_id`. Pass `programId` as
  context via `mutationFn` closure or as a second argument.
  Signature: `useCreateReport(api, programId: string)`. On success:
  `queryClient.invalidateQueries({ queryKey: ["reports", programId] })`.
  **Acceptance**: mutation callable; success invalidates the list query.

---

## Phase 3: ExerciseReportsPanel component

- [ ] 3.1 **File**: `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx` (new).
  Props: `{ api: DiagnosticFeatureApi; programId: string }`.
  Internal state:
  - `showCreateForm: boolean`
  - `selectedProgramExerciseId: string`
  - `periodStart: string`, `periodEnd: string`, `summary: string`
  - `editingReportId: string | null`, `editingSummary: string`
  - `expandedReportId: string | null` (for detail fetch trigger)
  - `localSummaries: Record<string, string>` (optimistic summary edits)

  Render sections (follow v0 `exercise-reports-panel.tsx` structure):
  1. Header row: "Exercise Reports" h3 + "New Report" button (hidden when form open).
  2. Inline create form (when `showCreateForm`): exercise select (from `useProgramExercises`
     already passed via `api`), date inputs, summary textarea, Create / Cancel buttons.
  3. Empty state card when `reports.length === 0`.
  4. Report cards list.

  Use CSS classes from `styles.css` following the existing panel patterns
  (`section-heading`, `state-card`, `detail-card`, `card-header`, etc.).
  **Acceptance**: component renders without errors in Vitest + jsdom; shows loading state.

- [ ] 3.2 **File**: same. Implement create form submit handler:
  1. Validate `periodEnd >= periodStart` → set `formError`.
  2. Validate `selectedProgramExerciseId` is set.
  3. Call `api.listExerciseRecordings(selectedProgramExerciseId)` to get recordings.
  4. If empty, set `formError = "No recordings found for this exercise"`.
  5. Call `createReport.mutate(...)` on success: reset form, close.
  **Acceptance**: validation errors shown inline; successful submit closes form.

- [ ] 3.3 **File**: same. Report cards section:
  Each card shows: period range (formatted dates), recording count badge, created_by,
  summary text or `—`, "Edit Summary" / "Show Details" / "Delete Report" buttons.

  Edit summary flow: clicking "Edit Summary" sets `editingReportId` and prefills
  `editingSummary` from `localSummaries[id] ?? report.summary`. Save stores to
  `localSummaries`. Cancel resets.

  Delete flow: `window.confirm()` → catch error → show inline error message (no toast
  library needed; use a `<p role="alert">` inside the card).

- [ ] 3.4 **File**: same. Expanded detail section (toggled by "Show Details" button):
  When `expandedReportId === report.id`, show `useReportDetail(api, report.exercise_report_id)`.
  Render a `<table>` with columns: Recording date, Duration, Media status, Insight.
  Each row has a "▶ View" toggle that expands an inline `<details>` block showing
  `insight_text` and `raw_json` as a `<pre>`.
  Show loading / error states inline (pattern: `<p className="state-card compact">`).
  **Acceptance**: clicking "Show Details" fetches and renders the recordings table.

---

## Phase 4: Integration into RehabProgramPanel

- [ ] 4.1 **File**: `web/src/features/diagnostics/components/RehabProgramPanel.tsx`.
  In `ProgramDetailState`, import `ExerciseReportsPanel`. Add local state
  `showReports: boolean` (initially `false`). Below the `AssignedExerciseTable`, add:
  ```tsx
  <div className="section-heading section-heading-row">
    <button
      type="button"
      className="secondary-button"
      onClick={() => setShowReports((v) => !v)}
    >
      {showReports ? "Hide Exercise Reports" : "Show Exercise Reports"}
    </button>
  </div>
  {showReports ? (
    <ExerciseReportsPanel programId={program.id} api={api} />
  ) : null}
  ```
  Pass `api` down into `ProgramDetailState` (it already has `onAssignExercise` etc —
  add `api: DiagnosticFeatureApi` to `ProgramDetailState` props and thread it through
  from `RehabProgramPanel`).
  **Acceptance**: toggle button visible; clicking shows/hides the panel.

---

## Phase 5: Tests

- [ ] 5.1 **File**: `web/src/api/reports.test.ts` (new). Test `createReportsApi`:
  - `listProgramReports` calls `GET /programs/{id}/reports`.
  - `createReport` calls `POST /reports` with correct body.
  - `getReportDetail` calls `GET /reports/{id}`.
  - `deleteReport` throws `Error`.
  Use the same mock `http` pattern as `web/src/api/programs.test.ts`.
  **Acceptance**: 4 tests pass.

- [ ] 5.2 **File**: `web/src/features/diagnostics/components/ExerciseReportsPanel.test.tsx` (new).
  Use Vitest + React Testing Library (same setup as `DiagnosticWorkspace.test.tsx`).
  Cases:
  - Shows loading state when `listProgramReports` is pending.
  - Shows empty state when list returns `[]`.
  - Shows report cards when list returns data.
  - "New Report" button shows form.
  - Form validates date range → shows error.
  Mock `api` with `vi.fn()` stubs.
  **Acceptance**: 5 tests pass without hitting real HTTP.

---

## Dependency Map

```
1.1 → 1.2 → 1.3
1.1 → 2.1, 2.2, 2.3
1.2 + 2.x → 3.1 → 3.2 → 3.3 → 3.4
3.x → 4.1
1.1 → 5.1
3.x → 5.2
```

Tasks 1.1, write-order: types first, then factory. Phase 2 parallel after 1.1.
Phase 3 sequential (each task builds on prior). Phase 4 after 3.x complete.
Tests in Phase 5 can run after their respective phases.
