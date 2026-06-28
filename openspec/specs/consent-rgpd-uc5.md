<!-- engram-topic-key: sdd/consent-rgpd-uc5/spec -->
# Specification: RGPD Consent Gate (UC-05)

## Purpose

Define per-program patient consent lifecycle (grant, withdraw, active-check) required by RGPD (EU 2016/679) before biometric voice recordings are accepted, plus the consent pre-check applied to recording write paths and the consent modal flow in the patient UI.

Consent state model (append-only rows in `clinical.patient_consent`):

| Field | Meaning |
|-------|---------|
| `consent_id` | UUID, primary key |
| `patient_id` | UUID of the patient |
| `program_id` | UUID of the rehab program |
| `granted` | boolean |
| `granted_at` | timestamp of this grant, set at INSERT |
| `withdrawn_at` | timestamp of withdrawal, null when active |
| `consent_text` | text snapshot of the RGPD text accepted at grant time |

**Append-only invariant**: rows are NEVER updated at grant time. Each `grant` call inserts a new row. The `UNIQUE (patient_id, rehab_program_id)` constraint MUST NOT exist on this table.

**Active consent** = the most recent row (ORDER BY `granted_at DESC LIMIT 1`) WHERE `withdrawn_at IS NULL`.

**Migration `0012`** MUST execute the following DDL statements (in order) before adding any RLS write policies:

```sql
ALTER TABLE clinical.patient_consent DROP CONSTRAINT IF EXISTS patient_consent_patient_id_rehab_program_id_key;
ALTER TABLE clinical.patient_consent ADD COLUMN IF NOT EXISTS consent_text TEXT;
```

The `consent_text` column is nullable at the DB layer (no `NOT NULL` constraint) to avoid breaking existing rows. NOT NULL is enforced at the application layer for new inserts only.

## Requirements

### Requirement: Read consent status

The system MUST let an enrolled patient read the current consent status for one of their programs. The response reflects the most recent row (ORDER BY `granted_at DESC LIMIT 1`); the response shape is unchanged.

#### Scenario: Patient reads existing consent

- GIVEN an authenticated patient enrolled in a program with at least one consent row
- WHEN `GET /api/programs/{program_id}/consent` is sent
- THEN the API returns `200` with the following fields of the most recent row:
  ```json
  {
    "consent_id": "<uuid>",
    "program_id": "<uuid>",
    "granted": true,
    "granted_at": "2026-06-28T10:00:00Z",
    "withdrawn_at": null,
    "consent_text": "Autorizo la grabación de mi voz..."
  }
  ```

#### Scenario: No consent row yet

- GIVEN an authenticated patient enrolled in a program with no consent rows
- WHEN `GET /api/programs/{program_id}/consent` is sent
- THEN the API returns `200` with:
  ```json
  {
    "consent_id": null,
    "program_id": "<uuid>",
    "granted": false,
    "granted_at": null,
    "withdrawn_at": null,
    "consent_text": null
  }
  ```

#### Scenario: Patient not enrolled

- GIVEN an authenticated patient not enrolled in the program
- WHEN `GET /api/programs/{program_id}/consent` is sent
- THEN the API returns `403`.

### Requirement: Grant consent

The system MUST allow an enrolled patient to grant consent by always inserting a new row, recording the accepted RGPD text for audit. Re-granting is allowed and creates an audit trail — no upsert, no 409 for duplicate grants.

#### Scenario: First grant

- GIVEN an enrolled patient with no rows in `clinical.patient_consent` for this program
- WHEN `POST /api/programs/{program_id}/consent/grant` is sent with body:
  ```json
  { "consent_text": "Autorizo la grabación de mi voz..." }
  ```
- THEN a NEW row is inserted with `granted=true`, `granted_at=now()`, `withdrawn_at=NULL`, `consent_text` stored
- AND the API returns `200` with the consent status (including `consent_text`).

#### Scenario: Re-grant after withdrawal

- GIVEN an enrolled patient who previously withdrew consent (a row with `withdrawn_at` set exists)
- WHEN `POST /api/programs/{program_id}/consent/grant` is sent with body `{ "consent_text": "..." }`
- THEN a NEW consent row is inserted with `granted=true`, `granted_at=now()`, `withdrawn_at=NULL`, `consent_text` stored
- AND the previous withdrawn row is preserved (audit trail)
- AND the API returns `200`.

#### Scenario: Patient not enrolled

- GIVEN an authenticated patient not enrolled in the program
- WHEN `POST /api/programs/{program_id}/consent/grant` is sent
- THEN the API returns `403`.

### Requirement: Withdraw consent

The system MUST allow an enrolled patient to withdraw active consent without deleting the consent row or any recordings. Withdrawal UPDATEs the most recent active row (WHERE `withdrawn_at IS NULL`). If no active row exists the endpoint returns `404` — this covers both "never granted" and "already withdrawn" cases.

#### Scenario: Withdraw active consent

- GIVEN an enrolled patient with at least one row WHERE `withdrawn_at IS NULL` (active consent)
- WHEN `POST /api/programs/{program_id}/consent/withdraw` is sent
- THEN the most recent active row is UPDATEd: `withdrawn_at = now()`
- AND the row is preserved (not deleted)
- AND the API returns `200` with the consent status.

#### Scenario: No active consent row

- GIVEN an enrolled patient with no row WHERE `withdrawn_at IS NULL` (either no rows exist or all are withdrawn)
- WHEN `POST /api/programs/{program_id}/consent/withdraw` is sent
- THEN the API returns `404`.

### Requirement: RLS enforcement of consent ownership

The system MUST prevent a patient from granting or withdrawing consent on a program they do not own, enforced at the database row level.

#### Scenario: Insert restricted to own patient id

- GIVEN the `ftm_patient` role and migration `0012_consent_rls_policy` applied
- WHEN an INSERT is attempted on `clinical.patient_consent`
- THEN the row is accepted only when `patient_id = clinical.current_patient_id()`.

#### Scenario: Update (withdraw) restricted to own patient id

- GIVEN the `ftm_patient` role and migration `0012_consent_rls_policy` applied
- WHEN an UPDATE is attempted on `clinical.patient_consent`
- THEN the row is accepted only under `USING (patient_id = clinical.current_patient_id())`
- AND the UPDATE may only set `withdrawn_at` on the most recent active row.

### Requirement: Consent modal flow in recording UI

The system MUST gate recording capture in the UI behind an active-consent check, presenting an RGPD modal when consent is absent.

#### Scenario: Consent required on open

- GIVEN a patient with no active consent for the program
- WHEN `RecordingDialog` opens and calls `GET /api/programs/{program_id}/consent`
- THEN `ConsentModal` is rendered as an overlay with the RGPD text (voice is biometric data, consent is voluntary, withdrawable anytime)
- AND the recording UI is hidden.

#### Scenario: Accept and record

- GIVEN `ConsentModal` is shown
- WHEN the patient clicks "Accept and record"
- THEN `POST /api/programs/{program_id}/consent/grant` is called with `consent_text`
- AND while in-flight both buttons are disabled with a loading state
- AND on success the modal is dismissed and the recording UI is shown.

#### Scenario: Cancel without recording

- GIVEN `ConsentModal` is shown
- WHEN the patient clicks "Cancel"
- THEN the dialog closes and no recording is started.

#### Scenario: Consent already active

- GIVEN a patient with active consent for the program
- WHEN `RecordingDialog` opens
- THEN `ConsentModal` is NOT shown and the recording UI is displayed directly.

---

# Delta for api-recording-ejercicio-uc5

## MODIFIED Requirements

### Requirement: Create recording upload target

The system MUST allow an authenticated patient to request an upload target for an assigned exercise in one of their rehab programs, and MUST require active consent before issuing the target.
(Previously: no consent pre-check on the write path.)

#### Scenario: Patient requests upload URL for owned exercise

- GIVEN an authenticated patient with active consent and an owned program exercise
- WHEN `POST /api/recordings/upload-url` is sent with `program_exercise_id` and `content_type`
- THEN the API returns an upload key/URI and URL for a supported content type.

#### Scenario: Reject unowned exercise

- GIVEN an authenticated patient and a program exercise belonging to another patient
- WHEN `POST /api/recordings/upload-url` is requested
- THEN the API returns `403` or `404` without exposing the other patient's data.

#### Scenario: Reject unsupported media

- GIVEN an authenticated patient and an owned program exercise
- WHEN `POST /api/recordings/upload-url` is sent with a non-audio/video `content_type`
- THEN the API returns `422` or `400` and no upload target is created.

#### Scenario: Reject when no active consent

- GIVEN an authenticated patient with no active consent for the exercise's program
- WHEN `POST /api/recordings/upload-url` is requested
- THEN the API returns `403` with body `{ "detail": "CONSENT_REQUIRED", "program_id": "<uuid>" }`.

### Requirement: Register recording metadata

The system MUST register a Recording entity after media upload without storing raw media in PostgreSQL, and MUST require active consent before registration.
(Previously: no consent pre-check on the write path.)

#### Scenario: Register uploaded recording

- GIVEN an authenticated patient with active consent, an owned program exercise and a successful upload
- WHEN `POST /api/recordings/` is sent with `program_exercise_id`, `storage_uri` and `content_type`
- THEN the API returns `201` with `recording_id`
- AND the Recording row references the program exercise and storage URI
- AND `recorded_by` is derived from the authenticated subject
- AND available capture metadata (`duration_seconds`, `sample_rate`, `size_bytes`, `sha256`) is persisted.

#### Scenario: Reject storage URI not associated with requested exercise

- GIVEN an authenticated patient and an owned program exercise
- WHEN `POST /api/recordings/` references a malformed or unrelated `storage_uri`
- THEN the API rejects the request.

#### Scenario: Reject when no active consent

- GIVEN an authenticated patient with no active consent for the exercise's program
- WHEN `POST /api/recordings/` is sent
- THEN the API returns `403` with body `{ "detail": "CONSENT_REQUIRED", "program_id": "<uuid>" }`.

## ADDED Requirements

### Requirement: Read and delete paths unaffected by consent state

The system MUST NOT apply the consent guard to recording read or delete paths, so history survives withdrawal (EC-7).

#### Scenario: History survives withdrawal

- GIVEN a patient with existing recordings whose consent has just been withdrawn
- WHEN `GET /api/recordings/...` is requested for those recordings
- THEN the API returns the recordings normally
- AND `DELETE /api/recordings/{id}` remains available
- AND `POST /api/recordings/` for new recordings returns `403 CONSENT_REQUIRED`.
