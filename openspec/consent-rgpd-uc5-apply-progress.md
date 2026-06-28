# Apply Progress: consent-rgpd-uc5 — Full (PR1 Backend + PR2 Frontend)

**Mode**: Strict TDD
**Status**: All 12 tasks complete across phases 1–6

---

## PR 1 — Backend (Phases 1–4)

See original PR1 progress below. All tasks completed and verified.

### Completed Tasks (PR1)

- [x] **1.1** `bbdd_dev_setup/alembic/migrations/versions/0012_consent_rls_policy.py`
- [x] **2.1** `PatientConsent` ORM model in `api/app/clinical/models.py`
- [x] **2.2** `api/app/clinical/consent_schemas.py`
- [x] **2.3** `api/app/clinical/consent_service.py`
- [x] **3.1** `api/app/clinical/consent_router.py`
- [x] **3.2** `api/app/main.py` — consent_router registered
- [x] **3.3** `api/app/recording/router.py` — require_active_consent guard on 3 write handlers

---

## PR 2 — Frontend (Phases 5–6)

**Mode**: Strict TDD
**Batch**: PR 2 — Phases 5–6 (frontend only, no backend files touched)
**Status**: All 6 tasks complete

### TDD Cycle Evidence

| Task | Test File | RED | GREEN | Notes |
|------|-----------|-----|-------|-------|
| 5.1 consent.ts | N/A — types/factory | N/A | tsc clean | Pure API client |
| 5.2 Wire ConsentApi | App.test.tsx | tsc error (missing methods) | factory + mock complete | DiagnosticFeatureApi extended |
| 5.3 ConsentModal.tsx | ConsentModal.test.tsx | 4 tests RED (import error) | 4 tests GREEN | Strict TDD followed |
| 5.4 RecordingDialog refactor | PatientPortal.test.tsx | 3 tests RED (no getConsentStatus) | 13 tests GREEN | Checkbox removed; consent gate via API |
| 6.1 ConsentModal.test.tsx | Self | Written first (RED) | All pass | 4 tests |
| 6.2 PatientPortal.test.tsx | Self | Written (consent gate tests) | All pass | 3 new consent tests added |

### Test Summary
- **Total tests (full suite)**: 83 passing (0 failures)
- **New tests added**: 7 (4 ConsentModal + 3 RecordingDialog consent gate)
- **Updated tests**: 3 (removed checkbox interaction, updated to consent-aware flow)
- **TypeScript**: `tsc --noEmit` clean

### Completed Tasks (PR2)

- [x] **5.1** `web/src/api/consent.ts` — `ConsentStatus` type, `ConsentApi` type, `createConsentApi(http)` factory
- [x] **5.2** `web/src/features/diagnostics/api.ts` + `web/src/App.tsx` + `web/src/App.test.tsx` — ConsentApi wired throughout
- [x] **5.3** `web/src/features/patient/ConsentModal.tsx` — RGPD modal with loading/error states
- [x] **5.4** `web/src/features/patient/PatientPortal.tsx` — checkbox removed, consent API gate added
- [x] **6.1** `web/src/features/patient/ConsentModal.test.tsx` — 4 unit tests
- [x] **6.2** `web/src/features/patient/PatientPortal.test.tsx` — 3 consent gate tests + updated existing tests

### Files Changed (PR2)

| File | Action | Description |
|------|--------|-------------|
| `web/src/api/consent.ts` | Created | ConsentStatus type, ConsentApi type, createConsentApi factory |
| `web/src/features/diagnostics/api.ts` | Modified | Added ConsentApi to DiagnosticFeatureApi intersection |
| `web/src/App.tsx` | Modified | Import createConsentApi; spread into factory |
| `web/src/App.test.tsx` | Modified | Added getConsentStatus/grantConsent/withdrawConsent mocks |
| `web/src/features/patient/ConsentModal.tsx` | Created | RGPD consent modal component |
| `web/src/features/patient/PatientPortal.tsx` | Modified | RecordingDialog refactored: checkbox removed, consent API gate added |
| `web/src/features/patient/ConsentModal.test.tsx` | Created | 4 unit tests for ConsentModal |
| `web/src/features/patient/PatientPortal.test.tsx` | Modified | Updated 3 tests, added 3 consent gate tests, consent mocks in all api objects |
| `openspec/tasks/consent-rgpd-uc5.md` | Modified | All phases 5–6 tasks marked [x] |

### Deviations from Design

1. **ConsentModal placement**: Absolute overlay inside `<section className="recording-dialog">`. Avoids z-index conflicts. `RecordingDialog` backdrop still shows behind both.

2. **Loading state**: While `consentLoading=true`, shows "Checking consent…" status instead of the modal — avoids flash of modal for users with active consent.

3. **Button disabled state**: Record/Upload buttons no longer disabled pre-consent. Gate is at API level (403 CONSENT_REQUIRED). Matches backend-first spec design.

4. **PortalApi test fixtures**: All 4 inline `PortalApi` objects in navigation tests updated to include consent methods (TypeScript requirement after `PatientPortalFeatureApi` now includes `ConsentApi`).
