# Proposal: UI Recording Ejercicio (UC-05)

**Change Name**: `ui-recording-ejercicio-uc5`  
**Status**: Proposed

## Intent

Add the patient-facing UI for UC-05 so a patient can open a rehab program, view its assigned exercises, record exercise progress through a dialog, upload the media and register the Recording entity.

## Scope

### In Scope

- Add patient navigation from rehab program detail to a dedicated “View exercises and record progress” screen.
- Show assigned exercises for the selected rehab program.
- Add a v0-aligned Record button and recording dialog.
- Use browser `MediaRecorder` to capture audio/video where supported.
- Require explicit consent before starting a recording.
- Upload the captured blob through the backend upload URL contract.
- Register recording metadata after upload succeeds.
- Show loading, recording, preview, success and error states.
- Add frontend tests for the patient recording flow.

### Out of Scope

- Backend storage implementation and RLS tests.
- Metric extraction, reports and follow-up check-up views.
- Advanced video editing, trimming or waveform visualization.
- Offline recording queue.

## Capabilities

### New Capabilities

- `patient-exercise-recording-ui`: Patient can record progress for a program exercise.
- `patient-recording-upload-ui`: Patient UI uploads captured media and registers metadata.

### Modified Capabilities

- `patient-rehab-program-ui`: Rehab program detail gains a transition to exercise recording.

## Approach

Extend `PatientPortal` with a dedicated exercise-recording mode. Keep typed API calls in `web/src/api/recordings.ts`, add raw blob upload support to `web/src/api/http.ts`, and style the exercise screen/dialog to match the v0 reference.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `web/src/api/recordings.ts` | New | Upload URL, blob upload and register API calls. |
| `web/src/api/http.ts` | Modified | Raw object-storage upload helper. |
| `web/src/features/diagnostics/api.ts` | Modified | Shared feature API type includes recordings API. |
| `web/src/App.tsx` | Modified | Aggregate recordings API into the app API object. |
| `web/src/features/patient/PatientPortal.tsx` | Modified | Program exercise recording screen and dialog. |
| `web/src/styles.css` | Modified | v0-aligned recording screen/dialog styles. |
| `web/src/App.test.tsx` | Modified | API test doubles include recording calls. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Browser lacks `MediaRecorder` | Medium | Show unsupported-browser state and disable record action. |
| Upload to signed URL accidentally sends app bearer token | Medium | Only attach auth for local API URLs, not absolute object-storage URLs. |
| Raw media privacy | Medium | Explicit consent copy; no LLM calls; upload only to authorized storage URL. |
| v0 parity unclear | Medium | Use existing v0-like CSS tokens and keep structure isolated for polish. |

## Rollback Plan

Remove recordings API client, HTTP upload helper, patient recording screen/dialog wiring and related styles/tests. Patient rehab program detail remains available.

## Dependencies

- API change `api-recording-ejercicio-uc5`.
- UC-02 patient rehab program access and exercise listing.
- Browser support for `MediaRecorder` and `getUserMedia`.

## Success Criteria

- [ ] Patient can open “View exercises and record progress” from a rehab program.
- [ ] Patient can start/stop a recording only after consent.
- [ ] UI uploads the captured media and registers Recording metadata.
- [ ] UI handles unsupported browser, denied permissions and upload/API failures.
- [ ] Tests cover navigation, consent gating and upload/register success.
