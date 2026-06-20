# Tasks: UI Recording Ejercicio (UC-05)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 450-750 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR #1 API client/upload helper → PR #2 patient recording screen/dialog → PR #3 tests/style polish |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Typed recording API client | PR 1 | No visible UI; includes raw upload helper. |
| 2 | Patient recording screen/dialog | PR 2 | Visible UC-05 flow from rehab program. |
| 3 | Tests and v0 polish | PR 3 | Browser API mocks, styles and regressions. |

## Phase 1: API Client and Upload Helper

- [x] 1.1 Create `web/src/api/recordings.ts` with upload URL, raw blob upload and register calls.
- [x] 1.2 Extend `web/src/api/http.ts` with raw `upload(url, blob, contentType)` support.
- [x] 1.3 Avoid sending the app bearer token to absolute signed object-storage URLs.
- [x] 1.4 Extend shared feature API types in `web/src/features/diagnostics/api.ts`.
- [x] 1.5 Add recording API methods to the app-level API object in `web/src/App.tsx`.

## Phase 2: Patient Recording Flow

- [x] 2.1 Add CTA from patient rehab program detail: “View exercises and record progress”.
- [x] 2.2 Add dedicated exercise-recording screen with back navigation.
- [x] 2.3 Show assigned exercises with v0-aligned record actions.
- [x] 2.4 Add `RecordingDialog` using `MediaRecorder` and `getUserMedia`.
- [x] 2.5 Require consent before starting recording.
- [x] 2.6 Upload captured blob and register recording metadata after save.
- [x] 2.7 Handle unsupported browser, denied permission, upload failure and success states.
- [x] 2.8 Add the v0-style audio/video file picker with type/100 MB validation, preview, retry and the same upload/register flow.

## Phase 3: Styling and v0 Alignment

- [x] 3.1 Add recording CTA, exercise card and dialog styles in `web/src/styles.css`.
- [x] 3.2 Compare visually with v0 and adjust spacing, typography and dialog controls.
- [x] 3.3 Add previous-recordings list/status if required by latest v0.

## Phase 4: Testing / Verification

- [x] 4.1 Update existing app/workspace test doubles with recording API methods.
- [ ] 4.2 Add focused PatientPortal test for opening the recording screen from a rehab program.
- [ ] 4.3 Add focused test for consent gating and unsupported browser state.
- [ ] 4.4 Add focused test for successful record-save API sequence using mocked `MediaRecorder`.
- [x] 4.5 Run `npm --prefix web test -- --run`.
- [x] 4.6 Run `cd web && npm exec -- tsc -b`.
- [x] 4.7 Run `api/.venv/bin/python -m pytest api/tests -q` as regression safety.
