# Apply Progress: Remove Exercise Report (UC-17)

## Change
`ui-api-remove-report-uc8`

## Mode
Standard (no TDD — Strict TDD not active for this change)

## Status
4/4 tasks complete. Ready for verify.

## Completed Tasks

- [x] 1.1 `api/app/reporting/router.py` — Added `DELETE /reports/{report_id}` endpoint below `PATCH /reports/{report_id}`. Returns 204 on success, 404 if not found, 403 for non-medical roles. No new imports needed.
- [x] 2.1 `web/src/api/reports.ts` — Replaced `deleteReport` stub with real `http.request<void>(\`/reports/${reportId}\`, { method: "DELETE" })`.
- [x] 3.1 `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx` — Added `useQueryClient` import, `queryClient = useQueryClient()` inside component, updated `handleDelete` to confirm with correct message, call `api.deleteReport`, and invalidate `["reports", programId]` on success.
- [x] 4.1 `web/src/api/reports.test.ts` — Replaced stub test with real `deleteReport` test asserting `DELETE /reports/{id}`.
- [x] 4.2 `web/src/features/diagnostics/components/ExerciseReportsPanel.test.tsx` — Fixed `makeApi` stub (`deleteReport: vi.fn(async () => undefined)`). Added 2 tests: confirm → `deleteReport` called; cancel → NOT called.

## Files Changed

| File | Action | What |
|------|--------|------|
| `api/app/reporting/router.py` | Modified | Added `DELETE /reports/{report_id}` endpoint |
| `web/src/api/reports.ts` | Modified | Replaced stub with real HTTP DELETE call |
| `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx` | Modified | Wired delete flow with confirm dialog, query invalidation |
| `web/src/api/reports.test.ts` | Modified | Replaced stub test with real deleteReport test |
| `web/src/features/diagnostics/components/ExerciseReportsPanel.test.tsx` | Modified | Fixed makeApi + 2 new delete tests |

## Verification Results

- `npx tsc --noEmit` — clean (0 errors)
- `npm test -- --run` — 53/53 tests pass (10 test files)
  - `ExerciseReportsPanel.test.tsx`: 7 tests (was 5, +2 new)
  - `reports.test.ts`: 4 tests (stub test replaced, count unchanged)

## Deviations from Design
None — implementation matches spec and design exactly.

## Workload / PR Boundary
- Mode: single PR
- Estimated review budget impact: ~90 lines changed (within 80–120 forecast)
