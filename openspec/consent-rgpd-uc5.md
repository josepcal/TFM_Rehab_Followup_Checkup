# Proposal: RGPD Consent Gate — UC5

## Intent

RGPD (EU 2016/679) requires explicit, informed consent before collecting health-related biometric recordings. Currently the `RecordingDialog` shows a local checkbox that resets on close and is never persisted. Any recording written to storage today lacks a valid consent record, exposing the platform to regulatory liability.

This change introduces a real per-program consent lifecycle backed by the existing `clinical.patient_consent` table, enforced at the API write boundary before any audio recording is accepted.

## Scope

### In Scope
- RLS INSERT/UPDATE policy for `ftm_patient` on `clinical.patient_consent`
- `PatientConsent` SQLAlchemy model in `api/app/clinical/models.py`
- Consent service: active-consent query, grant (upsert), withdraw (set `withdrawn_at`)
- REST endpoints: `GET /programs/{program_id}/consent`, `POST /programs/{program_id}/consent/grant`, `POST /programs/{program_id}/consent/withdraw`
- Consent guard on recording WRITE paths only (`register_recording`, `upload_url`, `_local-upload`)
- Frontend: replace fake checkbox with API-driven consent check → modal → grant flow in `RecordingDialog`
- Alembic migration `0012_consent_rls_policy` adding the missing RLS write policy

### Out of Scope
- eIDAS / qualified electronic signatures
- Consent for non-recording data (exercise metrics, diagnostics)
- Read or delete paths (EC-7: history survives withdrawal)
- Email / notification on consent events
- Admin consent override flows
- Legacy `iam.Consent` model — not touched

## Capabilities

### New Capabilities
- `consent-rgpd-uc5`: Per-program patient consent lifecycle (grant, withdraw, active-check) with API enforcement on recording write paths and frontend consent modal

### Modified Capabilities
- `api-recording-ejercicio-uc5`: Recording write paths gain a consent pre-check; existing read/delete behavior unchanged

## Approach

Add a thin `ConsentService` in the `clinical` domain (not inside `ProgramExerciseAccessService` which is also used by read/delete paths). The service performs a single `SELECT` for active consent before the recording write is accepted; no consent → `403 CONSENT_REQUIRED`. Grant is an upsert: if a prior withdrawn record exists, clear `withdrawn_at` and update `granted_at`. Withdraw sets `withdrawn_at=now()` without touching recording rows.

Frontend `RecordingDialog` calls `GET /programs/{program_id}/consent` on open; if no active consent, renders a modal with the RGPD text; on Accept, calls `POST grant`, then proceeds to upload.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `bbdd_dev_setup/alembic/versions/0012_consent_rls_policy.py` | New | RLS write policy for `ftm_patient` on `clinical.patient_consent` |
| `api/app/clinical/models.py` | Modified | Add `PatientConsent` SQLAlchemy model |
| `api/app/clinical/consent_service.py` | New | `get_active`, `grant`, `withdraw` methods |
| `api/app/clinical/consent_router.py` | New | 3 endpoints under `/programs/{program_id}/consent` |
| `api/app/clinical/exercise_recording_router.py` | Modified | Inject consent guard on `register_recording`, `upload_url`, `_local-upload` |
| `web/src/features/patient/PatientPortal.tsx` | Modified | Replace fake checkbox with consent API call + modal |
| `web/src/features/patient/ConsentModal.tsx` | New | RGPD consent modal component |
| `web/src/api/consent.ts` | New | API client for consent endpoints |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Existing recordings have no consent record — guard would retroactively block patients from new recordings | Med | Migration adds no backfill; existing programs need one grant action from the patient (documented in release notes) |
| `ProgramExerciseAccessService` accidentally used on write paths — guard applied in wrong layer | Low | Attach guard directly to recording router dependencies, not in the access service |
| RLS policy gap allows patient to grant/withdraw on programs they are not enrolled in | Low | Policy WHERE clause filters by `patient_id = auth.uid()` AND enrolled program; covered in migration |
| Frontend modal skipped if JS error — guard bypassed at UI level | Low | Guard is at API level; UI bypass only affects UX, not enforcement |

## Rollback Plan

1. Revert Alembic migration (`alembic downgrade -1`) — drops the write RLS policy; `clinical.patient_consent` rows remain intact
2. Revert API router changes — recording write paths lose the consent guard
3. Revert frontend to prior fake-checkbox state
4. No data loss: `clinical.patient_consent` table and existing rows survive a rollback

## Dependencies

- `clinical.patient_consent` table must exist (already present via `ftm_schema.sql`)
- Keycloak JWT must carry `sub` claim as patient identity (already in use across the codebase)
- `0011_seed_metric_norms` must be the current head before applying `0012`

## Success Criteria

- [ ] `POST /programs/{program_id}/consent/grant` returns 200 and creates/updates a consent row
- [ ] `POST /programs/{program_id}/consent/withdraw` sets `withdrawn_at`; does not delete rows
- [ ] `POST /programs/{program_id}/consent/grant` after withdraw clears `withdrawn_at` and updates `granted_at` (re-grant)
- [ ] Recording write endpoints return `403 CONSENT_REQUIRED` when no active consent exists
- [ ] Recording read and delete endpoints are unaffected by consent state (EC-7)
- [ ] `RecordingDialog` shows consent modal when no active consent; recording upload only proceeds after grant
- [ ] Patient cannot grant/withdraw consent for programs they are not enrolled in (RLS enforced)
- [ ] All new endpoints covered by integration tests with both consented and non-consented scenarios
