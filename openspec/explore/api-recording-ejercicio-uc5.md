# Explore: API Recording Ejercicio (UC-05)

## User Need

UC-05 requires a patient to record an assigned exercise for a given date. The backend must not receive LLM-facing PII/raw media and should store raw audio/video outside PostgreSQL while registering a Recording entity in the medical database.

## Current State

- Rehab programs and assigned program exercises exist from UC-02.
- A local MinIO/S3-compatible environment exists under `bbdd_dev_setup/ftm-recording-database`.
- The recording API has a basic upload URL and metadata registration path, but UC-05 still needs complete authorization/read coverage and storage hardening.

## Constraints

- Voice/audio is biometric special-category data; require explicit consent at UI level and minimize persisted metadata.
- Raw media must remain in object storage, not in relational rows.
- Patient-data access must pass API authorization and DB RLS assumptions.
- The app DB runtime role must not bypass RLS.

## Options Considered

| Option | Summary | Pros | Cons |
|--------|---------|------|------|
| Direct API multipart upload | Browser sends blob to FastAPI | Simple auth and single request | API handles large/raw media; poor scaling. |
| Signed object-storage URL | API returns signed URL; browser uploads to storage | Keeps raw media out of API; production-like | Needs storage adapter and two-step flow. |
| Local-only fake upload endpoint | Store file through API in dev | Easy tests | Diverges from S3/MinIO production path. |

## Decision

Use signed/S3-compatible upload semantics with a local-dev compatibility path where needed. The API owns authorization and metadata registration; object storage owns raw media bytes.

## Open Questions

- Exact production storage provider and IAM policy remain outside UC-05 local flow.
- Retention/purge is deferred to a later privacy/operations change.
