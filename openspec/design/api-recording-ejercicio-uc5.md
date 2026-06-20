# Design: API Recording Ejercicio (UC-05)

## Technical Approach

Add UC-05 to the existing recording bounded context. The API creates an authorized upload target, the browser uploads raw media directly to object storage, and the API registers a metadata row once upload succeeds. Program-exercise ownership is the authorization boundary.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Upload flow | Two-step upload URL + register metadata | Multipart through FastAPI | Avoids large raw media through API and matches S3/MinIO. |
| Stored DB data | Metadata only | Store binary media in PostgreSQL | Voice/video are sensitive and large; object storage is the right boundary. |
| Media types | Accept `audio/*` and `video/*` | Force WAV only | Browser `MediaRecorder` commonly emits WebM/Opus. |
| Authorization | Check program exercise ownership before URL/registration/read | Trust storage key only | Prevents cross-patient registration or reads. |
| Storage adapter | S3-compatible adapter with local MinIO | Hard-code local endpoint | Keeps dev/prod behavior aligned. |

## Data Flow

```text
Patient UI
  -> POST /recordings/upload-url { program_exercise_id, content_type }
  -> API authorizes program exercise through DB/RLS-aware session
  -> API returns { key, url, content_type }
  -> Browser PUTs Blob to object storage URL
  -> POST /recordings/ { program_exercise_id, storage_uri/key, content_type }
  -> API authorizes again and creates Recording metadata row
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/app/recording/router.py` | Modify | Add/complete upload URL, register and read endpoints with content-type validation. |
| `api/app/recording/models.py` | Verify/Modify | Ensure Recording can store program exercise link, storage URI/key, content type and created timestamp. |
| `api/app/storage.py` | Modify | Provide MinIO/S3-compatible upload URL generation and local test behavior. |
| `api/app/clinical/program_service.py` | Modify | Expose reusable authorization helper if needed. |
| `api/tests/test_recording.py` | Create/Modify | Unit/API tests for upload URL, registration and read flows. |
| `api/tests/integration/` | Modify | Real PostgreSQL/RLS checks for patient isolation if DB is available. |

## Interfaces / Contracts

```py
class UploadUrlIn(BaseModel):
    program_exercise_id: UUID
    content_type: str = "audio/wav"

class UploadUrlOut(BaseModel):
    key: str
    url: str
    content_type: str

class RecordingIn(BaseModel):
    program_exercise_id: UUID
    storage_uri: str
    content_type: str
    duration_seconds: float | None
    sample_rate: int | None
    size_bytes: int | None
    sha256: str | None

class RecordingOut(BaseModel):
    recording_id: UUID
    program_exercise_id: UUID
    recorded_by: UUID
    storage_uri: str
    content_type: str
    duration_seconds: float | None
    sample_rate: int | None
    size_bytes: int | None
    sha256: str | None
    created_at: datetime
```

## Authorization Rules

| Principal | Allowed |
|-----------|---------|
| Patient | Own program exercises only. |
| Medical specialist | Program exercises linked to diagnostics/programs they are authorized to access. |
| Physiotherapist | Assigned programs only, when role support exists. |
| Other roles | No recording access unless explicitly added later. |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| API validation | Content type and malformed payloads | FastAPI test client. |
| API auth | Owned vs unowned program exercise | Seeded fixture identities. |
| Storage adapter | URL/key shape and content type propagation | Unit tests with fake storage config. |
| Integration | RLS-backed patient isolation | `RUN_INTEGRATION=1` PostgreSQL tests. |

## Migration / Rollout

If the current Recording table lacks UC-05 fields, add a SQL-first Alembic migration. Roll out endpoints behind existing API auth; UI can consume them once deployed.
