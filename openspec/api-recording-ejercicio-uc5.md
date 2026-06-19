# Proposal: API Recording Ejercicio (UC-05)

**Change Name**: `api-recording-ejercicio-uc5`  
**Status**: Proposed

## Intent

Complete the backend API for UC-05 so a patient can upload an exercise recording for an assigned rehab-program exercise and the system registers the corresponding Recording entity in the medical database.

## Scope

### In Scope

- Create upload URLs for audio/video exercise recordings linked to an assigned program exercise.
- Validate recording media content types before upload URL creation and metadata registration.
- Register recording metadata after media upload, including storage URI/key and content type.
- Enforce patient/medical authorization over the referenced program exercise before creating or reading recordings.
- Add list/detail endpoints for recordings attached to a program exercise.
- Support local MinIO/S3-compatible object storage configuration for development.
- Add API tests and PostgreSQL-backed authorization/RLS integration coverage.

### Out of Scope

- Browser recording UI and upload progress UX.
- Metric extraction worker, analysis jobs and reports.
- LLM insights or pseudonymized metric payloads.
- Recording deletion/retention purge policies.
- Production bucket provisioning and cloud IAM.

## Capabilities

### New Capabilities

- `api-exercise-recording-upload`: patient/authorized clinician can request an upload target for a program exercise recording.
- `api-exercise-recording-register`: patient/authorized clinician can register Recording metadata after media upload.
- `api-exercise-recording-read`: authorized users can list/read recordings for a program exercise.

### Modified Capabilities

- `patient-rehab-program-access`: patient program exercise access becomes the authorization base for UC-05 recordings.

## Approach

Extend the existing `api/app/recording` slice with content-type-aware upload URL creation, metadata registration and read endpoints. Keep raw media in object storage and persist only references/metadata in PostgreSQL. Authorization must be applied at API/service level and remain compatible with DB RLS by using the JWT-derived identity and role in the DB session.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/app/recording/router.py` | Modified | Upload URL, registration and read endpoints. |
| `api/app/recording/models.py` | Modified | Recording metadata fields if schema support is missing. |
| `api/app/storage.py` | Modified | S3/MinIO signed URL or local-dev upload behavior. |
| `api/app/clinical/` | Modified | Program-exercise ownership checks or service helpers. |
| `bbdd_dev_setup/ftm-recording-database/` | Dependency | Local MinIO/S3-compatible storage for development. |
| `api/tests/` | Modified | API and integration tests for UC-05. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Exposing another patient's recordings | Medium | Authorize by program exercise ownership and keep DB RLS active. |
| Storing raw media in PostgreSQL | Low | Persist storage URI/key only; object storage contains raw audio/video. |
| Browser emits WebM while API expects WAV | Medium | Accept validated `audio/*` and `video/*` content types. |
| MinIO/local upload differs from production S3 | Medium | Hide implementation behind storage adapter and keep tests contract-based. |

## Rollback Plan

Remove UC-05 recording endpoints and tests. Existing rehab program and exercise assignment APIs remain unaffected.

## Dependencies

- UC-02 program exercise assignment exists.
- Local object storage can be started from `bbdd_dev_setup/ftm-recording-database`.
- RLS context is applied through `get_db` before recording queries.

## Success Criteria

- [ ] Patient can request an upload URL only for an exercise inside one of their rehab programs.
- [ ] API rejects unsupported content types and unowned program exercises.
- [ ] API registers a Recording row with storage reference and content type after upload.
- [ ] Authorized users can list/read recordings for a program exercise.
- [ ] Tests cover success, unsupported media, wrong patient and wrong role paths.
