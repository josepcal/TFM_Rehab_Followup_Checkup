# Spec: Play Recording (UC-08)

## Purpose

Allow medical users to stream/play a recording file directly from the Exercise Reports panel.
The feature adds a backend download-URL endpoint and a frontend player dialog.

A partial implementation exists (endpoints coded, dialog rendered with inline styles).
This spec captures the full correct behaviour and the gaps that need fixing.

## Scope

| Layer | File(s) |
|-------|---------|
| Backend storage | `api/app/storage.py` — `download_url()` on each adapter |
| Backend endpoint | `api/app/recording/router.py` — `GET /recordings/{id}/download-url`, `GET /recordings/_local-download/{key:path}` |
| Frontend API | `web/src/api/recordings.ts` — `getRecordingDownloadUrl` in `RecordingsApi` |
| Frontend component | `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx` — `RecordingPlayerDialog`, `ReportDetailSection` |
| Frontend types | `web/src/api/reports.ts` — `RecordingInsightEntry` must expose `content_type` or `media_kind` |
| Backend schema | `api/app/reporting/router.py` — `GET /reports/{id}` must return `content_type`/`media_kind` per recording |
| CSS | `web/src/styles.css` — player dialog must use project classes, not inline styles |
| Tests | Backend: `api/tests/test_storage.py`, `api/tests/test_recording.py`; Frontend: `web/src/features/diagnostics/components/ExerciseReportsPanel.test.tsx` |

## Conventions

- Plain-CSS classes only (`web/src/styles.css`). No inline styles for layout or color.
- All errors must be surfaced to the user via a visible `<p role="alert">` element.
- React Query is used for all async data; no raw `await` inside event handlers for data fetching.
- No new routes. Player opens as an in-page dialog (`role="dialog" aria-modal="true"`).

---

## Requirements

### REQ-1: Backend — storage adapters expose `download_url`

Each storage adapter (`LocalStorage`, `S3Storage`, `GcsStorage`) MUST implement
`download_url(key: str) -> str`.

| Adapter | Behaviour |
|---------|-----------|
| `LocalStorage` | Returns `/api/recordings/_local-download/{key}` — points to the authenticated dev endpoint |
| `S3Storage` | Returns a presigned `GetObject` URL with `ExpiresIn=900` (15 min) |
| `GcsStorage` | Returns a v4 signed GET URL with `expiration=timedelta(minutes=15)` |

#### Scenario: Download URL generated for each adapter

- GIVEN a valid storage key
- WHEN `download_url(key)` is called on each adapter
- THEN it returns a non-empty string URL specific to that adapter's backend.

---

### REQ-2: Backend — `GET /recordings/{id}/download-url`

The API MUST expose `GET /recordings/{recording_id}/download-url`.

- **Authorization**: roles `patient` and `medical` only (technicians denied at dependency level).
- **Authorization check**: `_require_authorized_recording` enforces `ProgramExerciseAccessService.require_access` — a patient can only access their own recordings.
- **404** if `recording.media_uri` is falsy ("recording has no media file").
- **Response**: `200 { "url": "<presigned or local URL>" }` (`DownloadUrlOut` schema).
- **TTL**: URLs are short-lived (≤15 min for cloud; no-TTL for local dev).

#### Scenario: Authorized user fetches download URL

- GIVEN a recording with a stored media file
- WHEN `GET /recordings/{id}/download-url` is called with a valid session
- THEN a `200` response is returned with a non-empty `url`.

#### Scenario: Recording has no media file

- GIVEN a recording row where `media_uri` is null
- WHEN the endpoint is called
- THEN a `404` "recording has no media file" response is returned.

#### Scenario: Unauthorized access

- GIVEN a patient session that does not own the recording
- WHEN the endpoint is called
- THEN a `403` or `404` is returned (RLS / access service).

---

### REQ-3: Backend — `GET /recordings/_local-download/{key:path}` (dev only)

The API MUST expose an authenticated file-serving endpoint for local development.

- Only active when `get_storage()` is a `LocalStorage` instance; otherwise `404`.
- Validates the key namespace via `recording_program_exercise_id(key)` → 400 if invalid.
- Enforces `ProgramExerciseAccessService.require_access` for the derived `program_exercise_id`.
- Returns `FileResponse(file_path)` with correct `media_type` derived from the file extension
  (must set `media_type` explicitly so the browser can pick the right player element).
- Returns `404` "recording file not found" if the file does not exist on disk.

#### Scenario: Local dev file served

- GIVEN a valid key pointing to an existing file on disk
- WHEN the endpoint is called in local-dev mode
- THEN the file is streamed as a `FileResponse` with the correct `Content-Type`.

---

### REQ-4: Backend — report detail exposes `content_type` and `media_kind` per recording

`GET /reports/{report_id}` currently returns `RecordingInsightEntry` which includes `media_status`
but NOT `content_type` or `media_kind`. The player dialog needs this to choose `<audio>` vs `<video>`.

The `RecordingInsightEntry` schema MUST be extended with:

```python
content_type: str | None
media_kind: str | None   # "audio" | "video"
```

The `GET /reports/{id}` SELECT statement in `reporting/router.py` must include
`ExerciseRecording.content_type` and `ExerciseRecording.media_kind` in the projection.

The corresponding TypeScript type `RecordingInsightEntry` in `web/src/api/reports.ts` must be
extended with:

```ts
content_type?: string | null;
media_kind?: string | null;
```

#### Scenario: Report detail includes media kind

- GIVEN a report linked to recordings
- WHEN `GET /reports/{id}` is called
- THEN each recording entry includes `media_kind` ("audio" or "video") and `content_type`.

---

### REQ-5: Frontend — `getRecordingDownloadUrl` in `RecordingsApi`

`RecordingsApi` (in `web/src/api/recordings.ts`) MUST include:

```ts
getRecordingDownloadUrl: (recordingId: string) => Promise<string>;
```

Implementation calls `GET /recordings/{recordingId}/download-url` and returns `result.url`.
This method is already implemented; no change needed beyond REQ-4.

---

### REQ-6: Frontend — `RecordingPlayerDialog` uses project CSS classes

The `RecordingPlayerDialog` component MUST be rewritten to use project CSS classes instead
of inline styles.

Mapping (existing classes in `web/src/styles.css`):

| Element | Class |
|---------|-------|
| Backdrop `<div>` | `recording-dialog-backdrop` |
| Dialog container | `recording-dialog` |
| Header row | `recording-dialog-header` |
| Close button | `dialog-close-button ghost-button` |
| Body area | `recording-dialog-body` |

The `<audio>` / `<video>` element is rendered inside the body area with `controls autoPlay`.
Audio/video selection is determined by `media_kind === "video"` (from REQ-4), NOT by parsing
`media_status`.

The dialog MUST be keyboard-accessible: `Escape` key closes it.

#### Scenario: Audio recording plays in audio element

- GIVEN a recording with `media_kind = "audio"`
- WHEN the dialog opens
- THEN an `<audio controls>` element is rendered with the download URL as `src`.

#### Scenario: Video recording plays in video element

- GIVEN a recording with `media_kind = "video"`
- WHEN the dialog opens
- THEN a `<video controls>` element is rendered with the download URL as `src`.

#### Scenario: Keyboard dismissal

- GIVEN the player dialog is open
- WHEN the user presses `Escape`
- THEN the dialog closes.

---

### REQ-7: Frontend — Play button flow uses React Query and surfaces errors

The Play button in `ReportDetailSection` MUST:

1. Be disabled while fetching the URL (`loadingPlayId === rec.recording_id`).
2. Call `api.getRecordingDownloadUrl(rec.recording_id)` on click.
3. On success: open `RecordingPlayerDialog` with the URL and `rec.media_kind`.
4. On error: show an inline `<p role="alert">` error message inside the detail section.
   Currently errors are silently swallowed in the `finally` block — this MUST be fixed.
5. Pass `rec.media_kind` (not `rec.media_status`) as the content hint to the dialog.

#### Scenario: Play button shows loading state

- GIVEN the user clicks Play
- WHEN the URL request is in flight
- THEN the button is disabled and shows a loading label.

#### Scenario: Error fetching download URL

- GIVEN the backend returns an error for `download-url`
- WHEN the user clicks Play
- THEN an inline error message is shown inside the recordings table section.

---

### REQ-8: Tests

#### Backend

- `api/tests/test_storage.py`: add tests for `download_url()` on `LocalStorage` and `S3Storage`
  (mock the boto3 client for S3).
- `api/tests/test_recording.py`: add integration-style tests for
  `GET /recordings/{id}/download-url` — authorized access returns 200, missing `media_uri`
  returns 404, unauthorized returns 403/404.

#### Frontend

- `web/src/features/diagnostics/components/ExerciseReportsPanel.test.tsx`: add tests:
  - Clicking Play calls `getRecordingDownloadUrl` and renders the dialog.
  - Error from `getRecordingDownloadUrl` shows an alert.
  - Dialog closes when the close button is clicked.
- Fix the existing `<>` fragment-without-key React warning in the recording row map.

---

## Known bugs (must fix during implementation)

| # | Location | Bug | Fix |
|---|----------|-----|-----|
| B1 | `ExerciseReportsPanel.tsx` Play handler | `rec.media_status` passed as content hint — always `false` for `startsWith("video/")` | Pass `rec.media_kind` after REQ-4 exposes it |
| B2 | `ExerciseReportsPanel.tsx` Play handler | Errors from `getRecordingDownloadUrl` are silently swallowed | Add `catch` block → set `playError` state → render `<p role="alert">` |
| B3 | `recording/router.py` `local_download` | `FileResponse` does not set explicit `media_type` | Derive from extension via `CONTENT_TYPE_EXTENSIONS` or `mimetypes.guess_type` |
| B4 | `ExerciseReportsPanel.tsx` row map | Bare `<>` fragment in `.map()` causes React key warning | Use `<Fragment key={rec.recording_id}>` |
| B5 | `RecordingPlayerDialog` | All layout via inline styles — inconsistent with project design system | Rewrite with project CSS classes |

## Out of scope

- Seek controls beyond native browser `controls`.
- Transcript or waveform visualisation.
- Download button (separate feature).
- Playback for the patient portal (covered separately by `PatientPortal.tsx`).
