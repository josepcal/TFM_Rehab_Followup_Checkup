<!-- engram-topic-key: sdd/consent-rgpd-uc5/tasks -->
# Tasks: RGPD Consent Gate (UC-05)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 380–460 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → migration + backend · PR 2 → frontend |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Migration + backend (model, service, router, guard, tests) | PR 1 | Base: `feature/UC9_followup_checkup`; self-contained; no frontend changes |
| 2 | Frontend (consent.ts, ConsentModal, PatientPortal refactor, tests) | PR 2 | Base: PR 1 merged; depends on consent endpoints being live |

---

## Phase 1: Migration

- [x] **1.1** Create `bbdd_dev_setup/alembic/migrations/versions/0012_consent_rls_policy.py`.
  - `revision = "0012_consent_rls_policy"`, `down_revision = "0011_seed_metric_norms"`
  - `upgrade()` — 5 `op.execute()` calls (idempotent):
    1. `ALTER TABLE clinical.patient_consent DROP CONSTRAINT IF EXISTS patient_consent_patient_id_rehab_program_id_key`
    2. `ALTER TABLE clinical.patient_consent ADD COLUMN IF NOT EXISTS consent_text TEXT`
    3. `DROP POLICY IF EXISTS consent_patient_insert ON clinical.patient_consent` + `CREATE POLICY consent_patient_insert FOR INSERT TO ftm_patient WITH CHECK (patient_id = clinical.current_patient_id())`
    4. `DROP POLICY IF EXISTS consent_patient_update ON clinical.patient_consent` + `CREATE POLICY consent_patient_update FOR UPDATE TO ftm_patient USING (patient_id = clinical.current_patient_id())`
    5. `GRANT INSERT, UPDATE ON clinical.patient_consent TO ftm_patient`
  - `downgrade()`: `REVOKE INSERT, UPDATE ON clinical.patient_consent FROM ftm_patient` + drop both policies + `ALTER TABLE clinical.patient_consent DROP COLUMN IF EXISTS consent_text` + re-add unique constraint
  - **Acceptance**: `alembic upgrade head` is idempotent; `alembic downgrade -1` leaves table intact with no consent rows lost.

---

## Phase 2: Backend — Model, Schemas, Service

- [x] **2.1** Add `PatientConsent` ORM class to `api/app/clinical/models.py`.
  - `__tablename__ = "patient_consent"`, `__table_args__ = {"schema": SCHEMA}` — no `UniqueConstraint`
  - Columns: `consent_id` (UUID PK `gen_random_uuid()`), `patient_id` (UUID FK `clinical.patient.patient_id`), `rehab_program_id` (UUID FK `clinical.rehab_program.rehab_program_id`), `granted` (Boolean not null default True), `granted_at` (DateTime tz `now()`), `withdrawn_at` (DateTime tz nullable), `consent_text` (Text nullable)
  - **Acceptance**: `from app.clinical.models import PatientConsent` resolves; no UniqueConstraint present.

- [x] **2.2** Create `api/app/clinical/consent_schemas.py`.
  - `ConsentIn(BaseModel)`: `consent_text: str` (required)
  - `ConsentOut(BaseModel)`: `consent_id: uuid.UUID | None`, `program_id: uuid.UUID`, `granted: bool`, `granted_at: datetime | None`, `withdrawn_at: datetime | None`, `consent_text: str | None`; `model_config = ConfigDict(from_attributes=True)`
  - `ConsentStatus(BaseModel)`: same as `ConsentOut` minus `consent_text`; used for GET and withdraw responses
  - **Acceptance**: `tsc`-equivalent — `from app.clinical.consent_schemas import ConsentIn, ConsentOut, ConsentStatus` resolves.

- [x] **2.3** Create `api/app/clinical/consent_service.py` with `ConsentService`.
  - `__init__(self, db: Session)`
  - `_resolve_patient_id() -> UUID`: `db.info["identity_id"]` → JOIN `clinical.app_user` → `clinical.patient`
  - `get_active(patient_id, program_id) -> PatientConsent | None`: `SELECT ... WHERE patient_id=... AND rehab_program_id=... AND withdrawn_at IS NULL ORDER BY granted_at DESC LIMIT 1`
  - `get_status(program_id) -> PatientConsent | None`: calls `_resolve_patient_id()`; queries most recent row regardless of `withdrawn_at`
  - `grant(program_id, consent_text) -> PatientConsent`: always `INSERT` new row (no upsert); `granted=True`, `granted_at=now()`, `withdrawn_at=None`
  - `withdraw(program_id) -> PatientConsent`: UPDATEs most recent row WHERE `withdrawn_at IS NULL`; raises `ConsentNotFoundError` if none found
  - `ConsentNotFoundError(HTTPException)` defined in same file with status 404
  - **Acceptance**: unit tests for `grant` (always inserts), `withdraw` (raises on no active row).

---

## Phase 3: Backend — Router, Guard, Registration

- [x] **3.1** Create `api/app/clinical/consent_router.py`.
  - `router = APIRouter(prefix="/programs/{program_id}", tags=["consent"])`
  - `GET /consent` → `get_status(program_id)` → `ConsentStatus`; 403 if not enrolled
  - `POST /consent/grant` body `ConsentIn` → `grant(program_id, body.consent_text)` → `ConsentOut` 200
  - `POST /consent/withdraw` → `withdraw(program_id)` → `ConsentStatus` 200; 404 if no active row
  - All endpoints: `Depends(require_role("patient"))`
  - **Acceptance**: `GET` returns `{"granted": false}` for no rows; `POST grant` creates row; `POST withdraw` sets `withdrawn_at`.

- [x] **3.2** Register consent router in `api/app/main.py`.
  - `from app.clinical.consent_router import router as consent_router`
  - `app.include_router(consent_router, prefix="/api")`
  - **Acceptance**: `GET /api/programs/{id}/consent` resolves; existing routes unaffected.

- [x] **3.3** Add `require_active_consent` dependency to `api/app/recording/router.py`.
  - Dependency signature: `program_exercise_id` param (from body or path) + `db` + `principal`
  - Resolves `program_id` via DB join on `ProgramExercise`
  - Skips guard when `principal.role == "medical"`
  - Calls `ConsentService(db).get_active(patient_id, program_id)`; raises `HTTPException(403, {"detail": "CONSENT_REQUIRED", "program_id": str(program_id)})` if None
  - Inject into `upload_url`, `register_recording`, and `_local-upload` handlers ONLY — not GET or DELETE
  - **Acceptance**: `POST /api/recordings/upload-url` returns 403 `CONSENT_REQUIRED` without consent; 200 with consent.

---

## Phase 4: Backend Tests (TDD — write RED first)

- [x] **4.1** Write failing tests in `api/tests/test_consent.py` (RED phase — run before implementing 2.3 / 3.1).
  - `test_get_consent_status_no_rows`: `GET /api/programs/{id}/consent` → 200 `{"granted": false}`
  - `test_get_consent_status_active`: returns most recent row with `granted=true`
  - `test_grant_consent_first_time`: inserts new row, returns 200 with `consent_text`
  - `test_grant_consent_re_grant`: second grant inserts another row; old row preserved with `withdrawn_at` set
  - `test_withdraw_active_consent`: sets `withdrawn_at`; row not deleted; returns 200
  - `test_withdraw_no_active_consent`: returns 404
  - `test_recording_upload_url_no_consent`: `POST /api/recordings/upload-url` → 403 `CONSENT_REQUIRED`
  - `test_recording_upload_url_with_consent`: 200 after grant
  - `test_recording_read_unaffected_by_withdrawal`: `GET /api/recordings/...` returns 200 after withdrawal (EC-7)
  - `test_cross_patient_grant_blocked`: patient B cannot grant for patient A's program (RLS / 403)

---

## Phase 5: Frontend — API Client and Modal

- [x] **5.1** Create `web/src/api/consent.ts`.
  - Types: `ConsentStatus { consent_id: string | null; program_id: string; granted: boolean; granted_at: string | null; withdrawn_at: string | null }`
  - Type: `ConsentApi { getConsentStatus(programId: string): Promise<ConsentStatus>; grantConsent(programId: string, consentText: string): Promise<ConsentStatus>; withdrawConsent(programId: string): Promise<ConsentStatus> }`
  - Factory `createConsentApi(http: HttpClient): ConsentApi`
  - **Acceptance**: `tsc --noEmit` passes.

- [x] **5.2** Wire `ConsentApi` into `DiagnosticFeatureApi` (or `PatientFeatureApi` if it exists) and `App.tsx`.
  - Add `consentApi` to the feature API intersection type
  - `App.tsx`: pass `createConsentApi(http)` to the factory
  - `App.test.tsx`: add `getConsentStatus: async () => ({ granted: false, ... })`, `grantConsent: ...`, `withdrawConsent: ...` to mock
  - **Acceptance**: `tsc --noEmit` passes; existing tests pass.

- [x] **5.3** Create `web/src/features/patient/ConsentModal.tsx`.
  - Props: `{ programId: string; api: ConsentApi; onGranted(): void; onCancel(): void }`
  - RGPD text rendered (voice is biometric data, consent is voluntary, withdrawable anytime)
  - "Accept and record" button: calls `grantConsent(programId, consentText)`, disables both buttons while in-flight, fires `onGranted` on success
  - "Cancel" button: fires `onCancel`; no API call
  - **Acceptance**: unit test — clicking Accept calls `grantConsent` and fires `onGranted`; clicking Cancel fires `onCancel` with no API call.

- [x] **5.4** Refactor `RecordingDialog` in `web/src/features/patient/PatientPortal.tsx`.
  - On dialog open: `useEffect` → `api.consent.getConsentStatus(programId)`
  - If `!granted`: render `<ConsentModal>` as overlay; hide recording UI
  - If `granted`: render recording UI directly; no modal
  - Remove fake checkbox
  - **Acceptance**: with `granted=false` mock — modal shown, recording hidden; with `granted=true` mock — modal not shown, recording shown.

---

## Phase 6: Frontend Tests (TDD — write RED first)

- [x] **6.1** Write tests for `ConsentModal.tsx` (RED before 5.3).
  - `renders RGPD text and two buttons`
  - `calls grantConsent and fires onGranted on Accept`
  - `disables buttons while grantConsent is in-flight`
  - `fires onCancel without API call on Cancel`

- [x] **6.2** Write tests for updated `PatientPortal.tsx` / `RecordingDialog` (RED before 5.4).
  - `shows ConsentModal when consent status is granted=false`
  - `hides ConsentModal and shows recording UI when consent status is granted=true`
  - `dismisses modal and shows recording UI after successful grant`
