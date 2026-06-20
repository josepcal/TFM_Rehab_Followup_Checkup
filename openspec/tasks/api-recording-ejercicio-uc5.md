# Tasks: API Recording Ejercicio (UC-05)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 280-520 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR acceptable; split storage adapter/tests if diff grows |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Upload/register contract | PR 1 | DTOs, content type validation, basic tests. |
| 2 | Authorization/read endpoints | PR 1 | Program-exercise ownership and list/detail. |
| 3 | Storage adapter/integration coverage | PR 1 | MinIO/S3 config and RLS tests. |

## Phase 1: Contract Foundation

- [x] 1.1 Add content-type-aware `UploadUrlIn` and `RecordingIn` contracts in `api/app/recording/router.py`, including capture metadata (`duration_seconds`, `sample_rate`, `size_bytes`, `sha256`); derive `recorded_by` from the authenticated principal.
- [x] 1.2 Return upload URL metadata including `key`, `url` and `content_type`.
- [x] 1.3 Generate media-key extensions from accepted audio/video content types.
- [x] 1.4 Confirm SQL-first schema supports Recording metadata needed for UC-05 (`program_exercise_id`, `recorded_by`, `storage_uri`, `content_type`, `duration_seconds`, `sample_rate`, `size_bytes`, `sha256`, timestamps).
  - Confirmed mapping: `storage_uri` is persisted as `media_uri`; timestamps are
    represented by `recording_date` and `created_at`; migration
    `0005_recording_content_type` adds exact MIME-type persistence.

## Phase 2: Authorization and Core Behavior

- [x] 2.1 Add reusable program-exercise authorization for patient and medical users.
- [x] 2.2 Apply authorization in `POST /recordings/upload-url`.
- [x] 2.3 Apply authorization in `POST /recordings/` before inserting metadata.
- [x] 2.4 Validate `storage_uri`/key belongs to the generated recording namespace for the requested exercise.
- [x] 2.5 Add `GET /program-exercises/{program_exercise_id}/recordings`.
- [x] 2.6 Add `GET /recordings/{recording_id}` if detail access is needed by UI/reporting.

## Phase 3: Storage Integration

- [x] 3.1 Add MinIO/S3-compatible storage adapter/config for upload URL generation.
- [x] 3.2 Keep local-dev fallback compatible with existing tests.
- [x] 3.3 Document required API env vars for local recording storage.

## Phase 4: Testing / Verification

- [x] 4.1 Add API tests for upload URL success and unsupported content type.
- [x] 4.2 Add API tests for registration success and malformed/unrelated storage URI.
- [x] 4.3 Add authorization tests for own vs unowned program exercise.
- [x] 4.4 Add list/detail recording tests.
- [x] 4.5 Add real PostgreSQL/RLS integration test for patient isolation when available.
- [x] 4.6 Run `api/.venv/bin/python -m pytest api/tests -q`.
- [x] 4.7 If PostgreSQL is available, run `RUN_INTEGRATION=1 ... pytest api/tests/integration -q`.
