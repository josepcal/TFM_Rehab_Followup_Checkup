<!-- engram-topic-key: sdd/audit-log-uc15/spec -->
# Specification: Audit Log (UC-15)

## Purpose

Provide a tamper-resistant audit trail of every mutating HTTP request against the clinical API, satisfying RGPD (EU 2016/679) accountability and traceability obligations over biometric/health data. The system MUST automatically record who did what, on which resource, from which IP, and when — without the application endpoints having to opt in — and MUST expose that trail to administrators for review.

Audit entries are append-only rows in `audit.event_log` (created in `ftm_schema.sql` / migration `0001_baseline`):

| Field | Meaning |
|-------|---------|
| `event_id` | UUID, primary key, server-generated |
| `entity_type` | Dotted schema.table name of the affected entity, e.g. `"recording.exercise_recording"` |
| `entity_id` | UUID of the specific entity row affected |
| `action` | Enum `audit.action`: `create`, `update`, or `delete` |
| `actor_id` | UUID FK to `clinical.app_user.identity_id` of the authenticated principal; `null` if unauthenticated |
| `payload` | JSONB diff or entity state snapshot at the time of the event (nullable) |
| `occurred_at` | UTC timestamp of the event, set at write time |

**Append-only invariant**: audit rows are NEVER updated or deleted by the application. They are written once, read many.

**Privilege model**: the `audit` schema has no grants to any application RLS role in `ftm_schema.sql`. Writes are performed exclusively through a raw `SessionLocal()` connection (the pool's login user owns the `audit` schema and has full INSERT access without `SET LOCAL ROLE`). `SELECT` is restricted to the `admin` role via a dedicated grant in migration `0013`.

**Scope**: only mutating operations (`create`, `update`, `delete`) on clinical entities are audited. Infrastructure paths (health, docs, OpenAPI schema) are excluded. The middleware maps HTTP `POST`→`create`, `PUT`/`PATCH`→`update`, `DELETE`→`delete`.

## Requirements

### Requirement: Automatic audit of mutating requests

The system MUST intercept every mutating HTTP request (`POST`, `PUT`, `PATCH`, `DELETE`) via middleware and persist one audit row AFTER the response has been produced, derived from the request and the authenticated context. The audited endpoints MUST NOT need any per-route instrumentation — auditing is transparent and global.

#### Scenario: Mutating request by an authenticated principal is audited

- GIVEN an authenticated principal whose internal `identity_id` is resolvable from the `current_user` context var
- WHEN `POST /api/recordings/` is sent and the response is produced
- THEN exactly one row is inserted into `audit.event_log` with:
  - `actor_id` = the principal's `clinical.app_user.identity_id` (UUID)
  - `entity_type` = the affected entity's schema.table (e.g. `"recording.exercise_recording"`)
  - `entity_id` = the UUID of the created/updated/deleted row
  - `action` = mapped from HTTP method (`POST`→`create`, `PUT`/`PATCH`→`update`, `DELETE`→`delete`)
  - `payload` = JSONB snapshot or diff of the entity state (nullable)
  - `occurred_at` = UTC timestamp
- AND the row is written using a raw `SessionLocal()` connection (pool login user, no `SET LOCAL ROLE`).

#### Scenario: Mutating request without a resolved principal

- GIVEN a mutating request that reaches the middleware with no authenticated principal in context
- WHEN the request completes
- THEN an audit row is still inserted with `actor_id = null`
- AND all other fields are populated as usual.

#### Scenario: Safe methods are not audited

- GIVEN any authenticated principal
- WHEN a `GET`, `HEAD`, or `OPTIONS` request is sent to any path
- THEN NO row is inserted into `audit.event_log`.

### Requirement: Excluded paths

The system MUST NOT write audit rows for infrastructure and documentation paths, even when the HTTP method is mutating. At minimum, health checks, interactive docs, and the OpenAPI schema MUST be excluded; static asset paths MUST also be excluded.

#### Scenario: Health check is not audited

- GIVEN the audit middleware is active
- WHEN a request hits a health endpoint (e.g. `/health` or `/healthz`)
- THEN NO row is inserted into `audit.event_log`, regardless of HTTP method.

#### Scenario: Docs and OpenAPI schema are not audited

- GIVEN the audit middleware is active
- WHEN a request hits `/docs`, `/redoc`, or `/openapi.json`
- THEN NO row is inserted into `audit.event_log`.

#### Scenario: Static assets are not audited

- GIVEN the audit middleware is active
- WHEN a request hits a static asset path (e.g. under `/static`)
- THEN NO row is inserted into `audit.event_log`.

### Requirement: Resilience (audit failure must not affect the HTTP response)

The audit write MUST be fire-and-forget with respect to the client outcome: a failure to persist an audit row MUST NOT change the HTTP status, body, or headers returned to the caller, and MUST NOT raise an exception into the request path. Failures MUST be logged for operational visibility.

#### Scenario: Audit write fails but the request still succeeds

- GIVEN a mutating request that the endpoint handles successfully (e.g. `201 Created`)
- WHEN the subsequent audit insert into `audit.event_log` raises an error (DB unavailable, constraint failure, etc.)
- THEN the client still receives the original successful response unchanged
- AND the error is captured and logged at `error` level
- AND no exception propagates to the client.

#### Scenario: Audit session is isolated from the request session

- GIVEN a mutating request whose business transaction has already committed/rolled back via `get_db()`
- WHEN the audit row is written
- THEN it uses its OWN raw `SessionLocal()` session (pool login user, no `SET LOCAL ROLE`), independent of the request's RLS session
- AND a rollback or failure in the audit session does not affect the already-completed request transaction.

### Requirement: Read audit log (admin only, paginated, filterable)

The system MUST expose `GET /iam/audit-log` returning audit entries ordered most-recent-first, restricted to the `admin` role. The endpoint MUST support pagination and optional filtering by `actor_id` and by date range (`from`/`to` on `ts`).

#### Scenario: Admin reads the audit log

- GIVEN an authenticated principal with the `admin` role
- WHEN `GET /iam/audit-log` is sent
- THEN the API returns `200` with a paginated list of audit entries, each containing `event_id`, `entity_type`, `entity_id`, `action`, `actor_id`, `payload`, and `occurred_at`
- AND entries are ordered by `occurred_at` descending.

#### Scenario: Filter by actor and date range

- GIVEN an authenticated `admin`
- WHEN `GET /iam/audit-log?actor_id=<uuid>&from=2026-06-01T00:00:00Z&to=2026-06-28T23:59:59Z` is sent
- THEN the API returns `200` with only entries whose `actor_id` matches AND whose `occurred_at` falls within `[from, to]`.

#### Scenario: Pagination

- GIVEN an authenticated `admin` and more entries than one page
- WHEN `GET /iam/audit-log?limit=50&offset=50` is sent
- THEN the API returns `200` with at most 50 entries, skipping the first 50.

#### Scenario: Non-admin is forbidden

- GIVEN an authenticated principal whose role is NOT `admin` (e.g. `ftm_medical_specialist` or `ftm_patient`)
- WHEN `GET /iam/audit-log` is sent
- THEN the API returns `403` and no audit data is disclosed.

#### Scenario: Unauthenticated request is rejected

- GIVEN no authenticated principal
- WHEN `GET /iam/audit-log` is sent
- THEN the API returns `401`.

### Requirement: RLS / access control (only system can INSERT, only admin can SELECT)

The system MUST enforce at the database level that the per-request application RLS roles cannot write the audit table, that only the system/superuser session can `INSERT`, and that reads are limited to the `admin` role. This guarantees the audit trail cannot be forged or tampered with by ordinary clinical traffic.

#### Scenario: App RLS roles cannot INSERT audit rows

- GIVEN the per-request RLS roles (`ftm_patient`, `ftm_medical_specialist`, `ftm_worker`, etc.)
- WHEN an `INSERT` into `audit.event_log` is attempted under any of those roles
- THEN the database rejects the write — the `audit` schema has no `GRANT USAGE` nor table grants to any app role in `ftm_schema.sql`.

#### Scenario: Pool login user can INSERT audit rows

- GIVEN the raw `SessionLocal()` connection (pool login user, no `SET LOCAL ROLE` applied)
- WHEN an `INSERT` into `audit.event_log` is performed
- THEN the row is accepted and persisted — the pool user owns the `audit` schema.

#### Scenario: Only admin may SELECT audit rows

- GIVEN migration `0013` has applied `GRANT SELECT ON audit.event_log TO ftm_medical_specialist`
- WHEN a `SELECT` on `audit.event_log` is attempted
- THEN it succeeds only for the `admin` role (mapped to `ftm_medical_specialist` in `DB_ROLE_BY_APP_ROLE`)
- AND is denied for `ftm_patient`, `ftm_worker`, `ftm_technician`, and `ftm_ai`.

#### Scenario: Audit rows are not updatable or deletable

- GIVEN the append-only invariant
- WHEN an `UPDATE` or `DELETE` on `audit.event_log` is attempted under any application role
- THEN the database rejects the operation — no `UPDATE` or `DELETE` grant exists on this table.
