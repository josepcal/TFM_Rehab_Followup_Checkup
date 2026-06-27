# Tasks: Play Recording (UC-08)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 150–230 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |

---

## Phase 1: Backend — expose `content_type` and `media_kind` in report detail

- [ ] 1.1 **File**: `api/app/reporting/schemas.py`.
  Add `content_type: str | None` and `media_kind: str | None` to `RecordingInsightOut`.
  **Acceptance**: Pydantic schema includes both fields without breaking existing fields.

- [ ] 1.2 **File**: `api/app/reporting/router.py`, function `get_report_detail`.
  Extend the SELECT projection with `ExerciseRecording.content_type` and
  `ExerciseRecording.media_kind`. Pass both to `RecordingInsightOut(...)` constructor.
  **Acceptance**: `GET /reports/{id}` response includes `content_type` and `media_kind` per
  recording entry.

---

## Phase 2: Backend — fix `local_download` Content-Type

- [ ] 2.1 **File**: `api/app/recording/router.py`, function `local_download`.
  Determine `media_type` from the file extension using `CONTENT_TYPE_EXTENSIONS` (imported
  from `app.storage`) or `mimetypes.guess_type(key)` as fallback.
  Pass `media_type=<resolved>` to `FileResponse(file_path, media_type=media_type)`.
  **Acceptance**: `GET /recordings/_local-download/recordings/x/y.webm` returns
  `Content-Type: audio/webm` (or the appropriate MIME for the extension).

---

## Phase 3: Backend — tests

- [ ] 3.1 **File**: `api/tests/test_storage.py`.
  Add tests:
  - `LocalStorage.download_url(key)` returns the expected path string
    (`/api/recordings/_local-download/{key}`).
  - `S3Storage.download_url(key)` calls `generate_presigned_url("get_object", ...)` on the
    boto3 client mock and returns the result.
  Use the existing mock-client pattern from the upload-url tests in the same file.
  **Acceptance**: 2 new tests pass.

- [ ] 3.2 **File**: `api/tests/test_recording.py` (or a new `test_download_url.py`).
  Add integration tests using the existing test client / fixture pattern:
  - Authorized `GET /recordings/{id}/download-url` returns `200` with `{ "url": "..." }`.
  - Recording with no `media_uri` returns `404`.
  - Unauthenticated request returns `401`/`403`.
  **Acceptance**: 3 new tests pass.

---

## Phase 4: Frontend — extend types with `content_type` and `media_kind`

- [ ] 4.1 **File**: `web/src/api/reports.ts`.
  Add `content_type?: string | null` and `media_kind?: string | null` to
  `RecordingInsightEntry`.
  **Acceptance**: TypeScript compiles without errors; fields accessible downstream.

---

## Phase 5: Frontend — fix `RecordingPlayerDialog`

- [ ] 5.1 **File**: `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx`,
  component `RecordingPlayerDialog`.
  - Replace all inline styles with project CSS classes:
    - Backdrop `<div>`: `className="recording-dialog-backdrop"` (remove `style` prop entirely).
    - Inner container: `className="recording-dialog"`.
    - Header row: `className="recording-dialog-header"`.
    - Close button: `className="dialog-close-button ghost-button"`.
    - Body area: `className="recording-dialog-body"`.
  - Change prop from `contentHint?: string | null` to `mediaKind?: string | null`.
  - Change detection from `contentHint?.startsWith("video/")` to `mediaKind === "video"`.
  - Add `Escape` key listener (`useEffect` + `keydown`) that calls `onClose()`.
  **Acceptance**: Dialog renders using project classes; video recordings show `<video>`;
  pressing Escape closes the dialog.

---

## Phase 6: Frontend — fix Play button handler in `ReportDetailSection`

- [ ] 6.1 **File**: `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx`,
  component `ReportDetailSection`.
  - Add `playError: string | null` state (initially `null`); reset to `null` on each Play click.
  - In the Play `onClick` handler, add a `catch` block:
    ```ts
    } catch (err) {
      setPlayError(err instanceof Error ? err.message : "Failed to load recording.");
    }
    ```
  - Change `setPlayerContentHint(rec.media_status ?? null)` to
    `setPlayerContentHint(rec.media_kind ?? null)` (fixes bug B1).
  - Rename state from `playerContentHint` to `playerMediaKind` for clarity (optional but
    recommended for consistency with REQ-6 prop rename).
  - Render `{playError ? <p role="alert" className="form-help">{playError}</p> : null}` below
    the recordings table header (or above the table).
  - Fix the `<>` fragment key warning: replace bare `<>...</>` in the recording row map with
    `<React.Fragment key={rec.recording_id}>...</React.Fragment>`. Import `Fragment` from React
    or use the `React.Fragment` form.
  **Acceptance**: Errors are shown to the user; video recordings display correctly; no React
  key warning in the console.

---

## Phase 7: Frontend — tests

- [ ] 7.1 **File**: `web/src/features/diagnostics/components/ExerciseReportsPanel.test.tsx`.
  Add tests (mock `getReportDetail` to return a recording with `media_kind: "audio"`):
  - `"clicking Play calls getRecordingDownloadUrl and renders the player dialog"`:
    - expand a report (`"Show Details"` button), then click `"Play"` on a recording row.
    - assert `getRecordingDownloadUrl` was called with the correct `recording_id`.
    - assert the player dialog is in the document (`role="dialog"`).
  - `"error from getRecordingDownloadUrl shows an alert"`:
    - mock `getRecordingDownloadUrl` to reject.
    - click Play; assert `role="alert"` contains an error message.
  - `"clicking close button dismisses the player dialog"`:
    - open the dialog, click the close button (`aria-label="Close player"`), assert dialog gone.
  Update `makeApi` to include a `getReportDetail` stub that returns a minimal `ReportDetailOut`
  with one recording entry including `media_kind: "audio"`.
  **Acceptance**: 3 new tests pass alongside existing 5.

---

## Dependency Map

```
1.1 → 1.2           (schema before router)
1.2 → 4.1           (backend type before frontend type)
4.1 → 5.1, 6.1      (frontend type before component fixes)
5.1 + 6.1 → 7.1     (component fixed before tests)
2.1 → 3.2           (local_download fix before integration test)
1.1 → 3.1           (storage tests are independent; can run in parallel with 1.x)
```

---

## Notes

- The `recording-dialog-backdrop`, `recording-dialog`, `recording-dialog-header`,
  `dialog-close-button`, and `recording-dialog-body` classes already exist in
  `web/src/styles.css`. No new CSS is required.
- `ExerciseRecording.media_kind` is already populated at recording registration time by
  `_media_kind_for_content_type` in `recording/router.py`. No migration needed.
- `CONTENT_TYPE_EXTENSIONS` in `storage.py` maps MIME → extension (the reverse of what task 2.1
  needs). Use `mimetypes.guess_type(key)` which maps extension → MIME, or build a small
  reverse-lookup dict inline in `local_download`.
