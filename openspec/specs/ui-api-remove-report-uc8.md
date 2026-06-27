# Spec: Remove Exercise Report (UC-17)

## Purpose

Allow a medical user to permanently delete an Exercise Report from a rehabilitation program.
The feature replaces the current stub (`deleteReport` throws unconditionally) with a real
`DELETE /reports/{id}` endpoint and wires the UI button to it.

## Scope

| Layer | File(s) |
|-------|---------|
| Backend endpoint | `api/app/reporting/router.py` — new `DELETE /reports/{id}` |
| Frontend API | `web/src/api/reports.ts` — `deleteReport` implementation |
| Frontend component | `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx` — delete flow |
| Tests | Backend: `api/app/reporting/router.py` test file; Frontend: `ExerciseReportsPanel.test.tsx` |

## Constraints

- **Hard delete only.** `ExerciseReport` has no `is_deleted` / soft-delete column. The
  deletion is permanent and immediate.
- **Cascade is already in place.** `exercise_report_recording` has
  `ForeignKey(..., ondelete="CASCADE")` — junction rows are removed automatically by
  PostgreSQL when the parent report is deleted. No manual cleanup needed.
- **Recordings are NOT affected.** `exercise_recording` rows and their associated
  `metric_result` / `ai_insight` records are not touched. The report is a view over
  recordings, not their owner.
- **Authorization:** only the `medical` role can delete reports. RLS ensures a doctor can
  only delete reports belonging to programs they have access to.

## Conventions

- Follow the pattern of `DELETE /recordings/{id}` in `recording/router.py`.
- Frontend error handling: inline `<p role="alert">` inside the card (same pattern as
  `saveError` and `deleteError` already in `ExerciseReportsPanel`).
- No toast library. No optimistic remove — remove from UI only after the server confirms.

---

## Requirements

### REQ-1: Backend — `DELETE /reports/{report_id}`

The API MUST expose `DELETE /reports/{report_id}`.

- **Method / path:** `DELETE /reports/{report_id}`
- **Status on success:** `204 No Content`
- **Authorization:** role `medical` only (`_require_medical` guard, same as `POST /reports`
  and `PATCH /reports/{id}`).
- **404** if the report does not exist (or RLS hides it from the authenticated doctor).
- **Deletion:** `db.delete(report)` — SQLAlchemy issues a `DELETE FROM exercise_report WHERE
  exercise_report_id = ?`. PostgreSQL CASCADE removes the junction rows automatically.
- No response body on success.

#### Scenario: Medical user deletes an existing report

- GIVEN a valid `exercise_report_id` the doctor has access to
- WHEN `DELETE /reports/{report_id}` is called with a `medical` session
- THEN the response is `204 No Content` and the report no longer appears in
  `GET /programs/{program_id}/reports`.

#### Scenario: Report not found

- GIVEN a `report_id` that does not exist or belongs to another program the doctor cannot access
- WHEN `DELETE /reports/{report_id}` is called
- THEN a `404 Not Found` response is returned.

#### Scenario: Non-medical role is rejected

- GIVEN a session with role `patient` or `technician`
- WHEN `DELETE /reports/{report_id}` is called
- THEN a `403 Forbidden` response is returned.

---

### REQ-2: Frontend — `deleteReport` in `ReportsApi`

`deleteReport` in `web/src/api/reports.ts` MUST be implemented as a real HTTP call:

```ts
deleteReport(reportId) {
  return http.request<void>(`/reports/${reportId}`, { method: "DELETE" });
}
```

The current stub (`Promise.reject(new Error("Delete is not yet supported by the API."))`)
MUST be replaced.

#### Scenario: `deleteReport` sends DELETE request

- GIVEN a valid `reportId`
- WHEN `deleteReport(reportId)` is called
- THEN it issues `DELETE /reports/{reportId}` and resolves on `204`.

---

### REQ-3: Frontend — Delete flow in `ExerciseReportsPanel`

The "Delete Report" button in each report card MUST:

1. Show a browser `confirm()` dialog: `"Delete this report? This cannot be undone."`.
2. If the user cancels, do nothing.
3. If the user confirms:
   a. Call `api.deleteReport(reportId)`.
   b. On success: invalidate the `["reports", programId]` React Query cache so the list
      refreshes and the deleted card disappears.
   c. On error: show an inline `<p role="alert">` with the error message inside the card.
      The `deleteError` state already exists in the component — wire it to this flow.

The button MUST be disabled while the delete is in flight (use a `isDeletingId` state or the
existing `deleteError` pattern).

#### Scenario: Doctor confirms deletion

- GIVEN a report card is visible
- WHEN the doctor clicks "Delete Report" and confirms the browser dialog
- THEN `deleteReport` is called, the query is invalidated, and the card disappears from the list.

#### Scenario: Doctor cancels deletion

- GIVEN the confirm dialog is shown
- WHEN the doctor clicks "Cancel"
- THEN no API call is made and the card remains.

#### Scenario: Delete fails

- GIVEN the server returns an error for `DELETE /reports/{id}`
- WHEN the doctor confirms deletion
- THEN an inline error message appears inside the card.

---

### REQ-4: Tests

#### Backend

Add tests covering:
- `DELETE /reports/{id}` with a valid medical session returns `204`.
- `DELETE /reports/{id}` with a non-existent ID returns `404`.
- `DELETE /reports/{id}` with a `patient` session returns `403`.

#### Frontend

Update `ExerciseReportsPanel.test.tsx`:
- `"clicking Delete Report and confirming calls deleteReport and refreshes the list"`:
  mock `window.confirm` to return `true`; assert `deleteReport` was called.
- `"clicking Delete Report and cancelling does not call deleteReport"`:
  mock `window.confirm` to return `false`; assert `deleteReport` was NOT called.
- Update existing `makeApi` to implement `deleteReport` as `vi.fn(async () => undefined)`
  (replacing the current stub that throws).

Update `web/src/api/reports.test.ts`:
- Add test: `deleteReport` calls `DELETE /reports/{id}`.

---

## Out of scope

- Soft delete / audit trail for reports (the recording layer has `is_deleted`; reports do not).
- Bulk delete.
- Undo / restore after deletion.
- Cascade-deleting the linked recordings (recordings outlive reports by design).
