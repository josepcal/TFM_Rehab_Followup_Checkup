# Design: UI Recording Ejercicio (UC-05)

## Technical Approach

Extend the patient portal with a focused exercise-recording mode. The patient enters from rehab program detail, chooses an assigned exercise, records via `MediaRecorder`, uploads the blob to the backend-provided upload URL and registers metadata.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Placement | `features/patient/PatientPortal.tsx` initially | Separate route/feature | Keeps UC-05 close to patient rehab program state. |
| API client | `web/src/api/recordings.ts` | Inline fetch calls | Matches existing typed API client pattern. |
| Upload helper | `http.upload(url, blob, contentType)` | Reuse JSON `request` | Raw blob PUT must not JSON-encode payload. |
| Recording API | Browser `MediaRecorder` | External library | Native API is sufficient and avoids dependencies. |
| Consent | Checkbox in dialog before capture | Global one-time banner | UC-05 action has special-category voice/video data implications. |

## Data Flow

```text
PatientPortal program detail
  -> CTA: View exercises and record progress
  -> Exercise recording screen lists assigned exercises
  -> Record button opens RecordingDialog
  -> navigator.mediaDevices.getUserMedia(...)
  -> MediaRecorder collects Blob chunks
  -> createRecordingUploadUrl(program_exercise_id, content_type)
  -> uploadRecordingBlob(uploadUrl, blob, content_type)
  -> registerRecording(program_exercise_id, storage_uri/key, content_type)
  -> success state and close/back to exercise list
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `web/src/api/recordings.ts` | Create | `createRecordingUploadUrl`, `uploadRecordingBlob`, `registerRecording` and DTOs. |
| `web/src/api/http.ts` | Modify | Add raw upload method that avoids bearer token for external signed URLs. |
| `web/src/features/diagnostics/api.ts` | Modify | Export `RecordingsApi` for shared API aggregation. |
| `web/src/App.tsx` | Modify | Add recording API methods to application API object. |
| `web/src/features/patient/PatientPortal.tsx` | Modify | Add recording screen state, exercise list and `RecordingDialog`. |
| `web/src/styles.css` | Modify | Add v0-style recording CTA, exercise cards and dialog styles. |
| `web/src/App.test.tsx` | Modify | Add recording API fakes to app tests. |
| `web/src/features/patient/PatientPortal.test.tsx` | Create/Modify | Add focused navigation/dialog tests if test file exists. |

## Interfaces / Contracts

```ts
type RecordingUploadUrlIn = {
  program_exercise_id: string;
  content_type?: string;
};

type RecordingUploadUrlOut = {
  key: string;
  url: string;
  content_type?: string;
};

type RecordingIn = {
  program_exercise_id: string;
  storage_uri: string;
  content_type?: string;
  duration_seconds?: number;
  sample_rate?: number;
  size_bytes?: number;
  sha256?: string;
};

type RecordingOut = {
  recording_id: string;
};
```

## UI States

| State | Behavior |
|-------|----------|
| Idle | Record button available for each assigned exercise. |
| Consent missing | Start recording disabled/rejected with helper text. |
| Recording | Timer/pulse visible; Stop button available. |
| Preview ready | Playback shown when browser can render blob URL; Save enabled. |
| Saving | Buttons disabled; upload/register in progress. |
| Success | Confirmation message and dialog can close. |
| Error | Error message and retry path. |
| Unsupported | Recording action explains browser limitation. |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| API client | Upload URL payload, raw upload, registration payload | Vitest with mocked fetch/http. |
| Component | Navigate from program detail to recording screen | Testing Library. |
| Component | Consent gates recording | Mock `MediaRecorder`/`getUserMedia`. |
| Component | Save flow calls upload URL, blob upload and register | Mock APIs and assert order/payload. |
| Regression | Existing patient/doctor modes still render | Existing `App.test.tsx`/workspace tests. |

## Migration / Rollout

No database migration in UI. The feature can be rolled out once the UC-05 API is deployed. If the backend is unavailable, hide or disable the recording CTA through feature gating if required.
