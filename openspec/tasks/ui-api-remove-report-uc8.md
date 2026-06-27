# Tasks: Remove Exercise Report (UC-17)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 80–120 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |

---

## Phase 1: Backend — `DELETE /reports/{report_id}`

- [x] 1.1 **File**: `api/app/reporting/router.py`.
  Add endpoint below the existing `PATCH /reports/{report_id}`:

  ```python
  @router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
  def delete_report(
      report_id: uuid.UUID,
      principal: dict = Depends(require_role("medical")),
      db=Depends(get_db),
  ) -> None:
      """Hard-delete an exercise report (UC-17). Junction rows removed by DB cascade."""
      _require_medical(principal)
      report = db.scalar(
          select(ExerciseReport).where(ExerciseReport.exercise_report_id == report_id)
      )
      if report is None:
          raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
      db.delete(report)
  ```

  No new imports needed — `select`, `ExerciseReport`, `HTTPException`, `status`,
  `require_role`, `get_db`, and `_require_medical` are already in scope.
  **Acceptance**: `DELETE /reports/{id}` returns `204` for a valid report; `404` for
  unknown ID; `403` for non-medical roles.

---

## Phase 2: Frontend API — implement `deleteReport`

- [x] 2.1 **File**: `web/src/api/reports.ts`.
  Replace the stub in `createReportsApi`:

  ```ts
  // before
  deleteReport(_reportId) {
    return Promise.reject(new Error("Delete is not yet supported by the API."));
  },

  // after
  deleteReport(reportId) {
    return http.request<void>(`/reports/${reportId}`, { method: "DELETE" });
  },
  ```

  **Acceptance**: `deleteReport("x")` issues `DELETE /reports/x`; TypeScript compiles
  without errors.

---

## Phase 3: Frontend component — wire delete flow

- [x] 3.1 **File**: `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx`.
  Update the `onDelete` handler (currently called from `ReportCard`). Locate where
  `onDelete` is defined in `ExerciseReportsPanel` and replace the existing implementation:

  ```ts
  async function handleDelete(reportId: string) {
    if (!window.confirm("Delete this report? This cannot be undone.")) return;
    setDeleteError(null);
    try {
      await api.deleteReport(reportId);
      queryClient.invalidateQueries({ queryKey: ["reports", programId] });
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete report.");
    }
  }
  ```

  Import `useQueryClient` from `@tanstack/react-query` at the top of the file (check if
  already imported; add only if missing).

  Pass `queryClient` via `useQueryClient()` inside `ExerciseReportsPanel`.

  **Acceptance**: clicking "Delete Report", confirming, calls the API and removes the card
  from the list; cancelling does nothing; an API error shows `<p role="alert">`.

---

## Phase 4: Tests

- [x] 4.1 **File**: `web/src/api/reports.test.ts`.
  Add test: `deleteReport` calls `DELETE /reports/{id}`.
  Follow the existing pattern (mock `http.request`, assert path and method).
  **Acceptance**: 1 new test passes alongside existing ones.

- [x] 4.2 **File**: `web/src/features/diagnostics/components/ExerciseReportsPanel.test.tsx`.
  - Update `makeApi` factory: change `deleteReport` from the stub that throws to
    `vi.fn(async () => undefined)`.
  - Add test `"clicking Delete Report and confirming calls deleteReport"`:
    - mock `window.confirm` to return `true` (`vi.spyOn(window, "confirm").mockReturnValue(true)`).
    - render a panel with one report in the list.
    - click "Delete Report".
    - assert `deleteReport` was called with the correct `exercise_report_id`.
  - Add test `"clicking Delete Report and cancelling does not call deleteReport"`:
    - mock `window.confirm` to return `false`.
    - click "Delete Report".
    - assert `deleteReport` was NOT called.
  **Acceptance**: 2 new tests pass; total test count increases by 2.

---

## Dependency Map

```
1.1 → 4.1 (backend endpoint before API test)
2.1 → 3.1 (API method before component wiring)
3.1 → 4.2 (component wired before component tests)
```

Phases 1 and 2 are independent and can be worked in parallel.

---

## Notes

- `db.delete(report)` in SQLAlchemy ORM triggers a `DELETE FROM exercise_report WHERE ...`.
  The `exercise_report_recording` rows disappear automatically via the `ondelete="CASCADE"`
  FK already defined in `reporting/models.py:67`.
- `exercise_recording` rows are NOT deleted — by design (UC-13 governs recording deletion
  separately; recordings outlive the reports that reference them).
- The `deleteError` state variable already exists in `ExerciseReportsPanel` (introduced
  during UC-08 UI implementation). No new state is needed — just wire it correctly.
- `useQueryClient` may already be imported if `useCreateReport` uses it. Verify before adding
  a duplicate import.
