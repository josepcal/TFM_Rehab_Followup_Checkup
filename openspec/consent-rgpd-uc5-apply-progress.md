# Apply Progress: consent-rgpd-uc5 — PR 1 (Backend)

**Mode**: Strict TDD
**Batch**: PR 1 — Phases 1–4 (backend only, no frontend)
**Status**: All 7 tasks complete

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 Migration | N/A — pure DDL | N/A | N/A (new file) | N/A (DDL) | N/A (DDL) | N/A (DDL) | ✅ idempotent ops |
| 2.1 PatientConsent ORM | `test_consent.py` | Unit | N/A (new model) | ✅ Written | ✅ Passed | ➖ Structural | ➖ None needed |
| 2.2 consent_schemas.py | `test_consent.py` | Unit | N/A (new file) | ✅ Written | ✅ Passed | ➖ Structural | ➖ None needed |
| 2.3 ConsentService | `test_consent.py` | Unit | N/A (new file) | ✅ Written | ✅ Passed | ✅ 2+ cases each method | ✅ Clean |
| 3.1 consent_router | `test_consent.py` | Unit | N/A (new file) | ✅ Written | ✅ Passed | ✅ 2–3 cases | ✅ Clean |
| 3.2 main.py registration | N/A — structural | N/A | N/A | N/A | N/A | N/A | N/A |
| 3.3 recording guard | `test_consent.py` + `test_recording.py` | Unit | ✅ 164/170 passing before | ✅ Written | ✅ Passed | ✅ 3 cases (no consent, active, medical) | ✅ Clean |
| 4.1 test_consent.py | Self | Unit | N/A (new file) | ✅ 19 tests RED | ✅ 19 GREEN | ✅ Multiple scenarios | ✅ Clean |

### Test Summary
- **Total tests written**: 19 in `test_consent.py`
- **Total tests passing**: 170 (full suite, 0 failures, 6 skipped)
- **Layers used**: Unit (19)
- **Approval tests**: Updated `test_recording.py` (6 tests updated to add consent context)
- **Pure functions created**: 0 (DB service class pattern matches codebase conventions)

## Completed Tasks

- [x] **1.1** `bbdd_dev_setup/alembic/migrations/versions/0012_consent_rls_policy.py` — DROP UNIQUE constraint, ADD consent_text, INSERT/UPDATE RLS policies, GRANT to ftm_patient. Full downgrade reverses all.
- [x] **2.1** `PatientConsent` ORM model added to `api/app/clinical/models.py` — no UniqueConstraint, append-only.
- [x] **2.2** `api/app/clinical/consent_schemas.py` — `ConsentIn`, `ConsentOut`, `ConsentStatus`.
- [x] **2.3** `api/app/clinical/consent_service.py` — `ConsentService` (get_active, get_status, grant, withdraw) + `require_active_consent` guard function + `ConsentNotFoundError`.
- [x] **3.1** `api/app/clinical/consent_router.py` — 3 endpoints under `/programs/{program_id}/consent`.
- [x] **3.2** `api/app/main.py` — consent_router registered.
- [x] **3.3** `api/app/recording/router.py` — `require_active_consent` called inline in `upload_url`, `register_recording`, `local_upload`. Medical role bypasses guard. GET/DELETE paths untouched (EC-7).

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `bbdd_dev_setup/alembic/migrations/versions/0012_consent_rls_policy.py` | Created | RLS policies + consent_text column migration |
| `api/app/clinical/models.py` | Modified | Added `PatientConsent` ORM model + `Boolean` import |
| `api/app/clinical/consent_schemas.py` | Created | `ConsentIn`, `ConsentOut`, `ConsentStatus` schemas |
| `api/app/clinical/consent_service.py` | Created | `ConsentService`, `ConsentNotFoundError`, `require_active_consent` guard |
| `api/app/clinical/consent_router.py` | Created | 3 consent endpoints |
| `api/app/main.py` | Modified | Registered `consent_router` |
| `api/app/recording/router.py` | Modified | Added `require_active_consent` inline calls to 3 write handlers |
| `api/tests/test_consent.py` | Created | 19 unit tests for consent service + router + guard |
| `api/tests/test_recording.py` | Modified | Updated 6 patient write-path tests to provide consent context |
| `openspec/tasks/consent-rgpd-uc5.md` | Modified | Marked phases 1–4 tasks as `[x]` complete |

## Deviations from Design

1. **`require_active_consent` signature**: Changed from a FastAPI `Depends`-style function (with `Depends(get_db)` and `Depends(require_role(...))` defaults) to a plain function with explicit parameters. Rationale: the recording router calls it inline (not via FastAPI's DI), so `Depends` defaults would never be resolved by the framework. Explicit params are cleaner and simpler. The function still fulfills the design contract: skips medical, checks consent, raises 403.

2. **consent_schemas.py**: Design mentioned both `ConsentOut` and `ConsentStatus` as separate classes; tasks mentioned `ConsentStatusOut` as the name. Implemented as `ConsentOut` (full, with consent_text) and `ConsentStatus` (no consent_text) matching the design doc.

## Remaining Tasks (Phases 5–6, PR 2)

- [ ] **5.1** `web/src/api/consent.ts`
- [ ] **5.2** Wire `ConsentApi` into feature API + App.tsx
- [ ] **5.3** `ConsentModal.tsx`
- [ ] **5.4** Refactor `RecordingDialog` in `PatientPortal.tsx`
- [ ] **6.1** `ConsentModal` frontend tests
- [ ] **6.2** `PatientPortal` / `RecordingDialog` frontend tests

## PR Boundary

- **Mode**: chained PR slice (stacked-to-main)
- **Current work unit**: Unit 1 — migration + backend
- **Branch**: `feature/UC9_followup_checkup` (base)
- **Scope**: All backend files only. Zero frontend files touched.
- **Estimated lines changed**: ~350 (within budget for PR 1)
