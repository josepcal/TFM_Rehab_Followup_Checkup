<!-- engram-topic-key: sdd/audit-log-uc15/tasks -->
# Tasks: Audit Log (UC-15)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 150–200 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Delivery strategy | single-pr |

---

## Phase 0: Migration

- [ ] **0.1** Create `bbdd_dev_setup/alembic/migrations/versions/0013_audit_select_grant.py`.
  - `revision = "0013_audit_select_grant"`, `down_revision = "0012_consent_rls_policy"`
  - `upgrade()`:
    1. `GRANT USAGE ON SCHEMA audit TO ftm_medical_specialist`
    2. `GRANT SELECT ON audit.event_log TO ftm_medical_specialist`
  - `downgrade()`: `REVOKE SELECT ON audit.event_log FROM ftm_medical_specialist` + `REVOKE USAGE ON SCHEMA audit FROM ftm_medical_specialist`
  - **Acceptance**: `alembic upgrade head` idempotent; `GET /iam/audit-log` as `admin` returns 200 after migration.

---

## Phase 1: IAM — Model, Service, and Schemas

- [ ] **1.1** Add `EventLog` ORM model to `api/app/iam/models.py`.
  - `__tablename__ = "event_log"`, `__table_args__ = {"schema": "audit"}`
  - Columns matching `ftm_schema.sql`:
    - `event_id: UUID PK DEFAULT gen_random_uuid()`
    - `entity_type: String NOT NULL`
    - `entity_id: UUID nullable`
    - `action: String NOT NULL` (maps to `audit.action` enum values: `"create"`, `"update"`, `"delete"`)
    - `actor_id: UUID nullable` (FK `clinical.app_user.identity_id` — declare as plain UUID, no FK in ORM to avoid cross-schema complexity)
    - `payload: JSON nullable`
    - `occurred_at: DateTime(timezone=True) DEFAULT now()`
  - **Acceptance**: `from app.iam.models import EventLog` resolves; no import errors.

- [ ] **1.2** Create `api/app/iam/audit_service.py`.
  - `write_event_log(*, entity_type: str, entity_id: uuid.UUID | None, action: str, actor_id: uuid.UUID | None, payload: dict | None, db: Session) -> None`
  - Instantiates `EventLog` ORM object, calls `db.add()` + `db.flush()`.
  - Does NOT open or close the session — caller owns the session lifetime.
  - **Acceptance**: `from app.iam.audit_service import write_event_log` resolves; unit test verifies one `EventLog` row inserted per call.

- [ ] **1.3** Create `api/app/iam/schemas.py`.
  - `EventLogEntry(BaseModel)`: `event_id: uuid.UUID`, `entity_type: str`, `entity_id: uuid.UUID | None`, `action: str`, `actor_id: uuid.UUID | None`, `payload: dict | None`, `occurred_at: datetime`; `model_config = ConfigDict(from_attributes=True)`
  - **Acceptance**: `from app.iam.schemas import EventLogEntry` resolves; no import errors.

---

## Phase 2: IAM — Router

- [ ] **2.1** Create `api/app/iam/router.py`.
  - `router = APIRouter(prefix="/iam", tags=["iam"])`
  - `GET /iam/audit-log` with query params:
    - `actor_id: uuid.UUID | None = None` — optional filter on `actor_id`
    - `entity_type: str | None = None` — optional filter on `entity_type`
    - `from_ts: datetime | None = None` — optional lower bound on `occurred_at`
    - `to_ts: datetime | None = None` — optional upper bound on `occurred_at`
    - `limit: int = Query(default=50, ge=1, le=200)`
    - `offset: int = Query(default=0, ge=0)`
  - Requires `Depends(require_role("admin"))`.
  - Uses `get_db()` session. Queries `EventLog` ordered by `occurred_at DESC`. Applies filters when provided.
  - Returns `list[EventLogEntry]`.
  - **Requires migration `0013`** to be applied first (GRANT SELECT on `audit.event_log` to `ftm_medical_specialist`).
  - **Acceptance**: `GET /iam/audit-log` returns 200 for `admin`; 403 for `medical`/`patient`/`technician`; 401 for unauthenticated.

---

## Phase 3: Middleware

- [ ] **3.1** Add `AuditMiddleware` to `api/app/main.py`.
  - Import `BaseHTTPMiddleware` from `starlette.middleware.base`.
  - Import `SessionLocal`, `_resolve_identity_id` from `app.db`; `current_user` from `app.context`; `write_event_log` from `app.iam.audit_service`.
  - Class `AuditMiddleware(BaseHTTPMiddleware)`:
    - `EXCLUDED: frozenset = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})`
    - `METHOD_TO_ACTION: dict = {"POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}`
    - `async def dispatch(self, request, call_next)`:
      1. `response = await call_next(request)`
      2. If `request.method in self.METHOD_TO_ACTION` and `request.url.path not in self.EXCLUDED`:
         - `db = SessionLocal()`
         - `try/finally db.close()`
         - Inside try:
           - `sub = current_user.get()`
           - `actor_id = _resolve_identity_id(db, sub) if sub else None` (returns UUID or None)
           - `action = self.METHOD_TO_ACTION[request.method]`
           - `with db.begin(): write_event_log(entity_type=request.url.path, entity_id=None, action=action, actor_id=actor_id, payload=None, db=db)`
         - Wrap entire block in `except Exception: logger.error("audit write failed", exc_info=True)` — never propagate
      3. Return `response` unconditionally
  - Register **after** all `include_router` calls: `app.add_middleware(AuditMiddleware)` (Starlette wraps in reverse order — last added = outermost, runs after auth has set context vars).

- [ ] **3.2** Register IAM router in `api/app/main.py`.
  - `from app.iam.router import router as iam_router`
  - Add `iam_router` to the existing `for r in (...)` block.
  - **Acceptance**: `GET /iam/audit-log` resolves; existing routes and health check unaffected.

---

## Phase 4: Tests (TDD — write RED first)

- [ ] **4.1** Write failing tests in `api/tests/test_audit_log.py` (RED before phases 0–3).
  - `test_write_event_log_inserts_row`: call `write_event_log` with a mock Session; assert `db.add` called with an `EventLog` instance with correct `action`, `entity_type`, `actor_id`.
  - `test_get_audit_log_admin_returns_200`: `GET /iam/audit-log` as `admin` → 200 with list.
  - `test_get_audit_log_medical_returns_403`: `GET /iam/audit-log` as `medical` → 403.
  - `test_get_audit_log_patient_returns_403`: `GET /iam/audit-log` as `patient` → 403.
  - `test_get_audit_log_unauthenticated_returns_401`: no token → 401.
  - `test_get_audit_log_filter_by_actor`: `?actor_id=<uuid>` returns only matching rows.
  - `test_get_audit_log_filter_by_entity_type`: `?entity_type=recording.exercise_recording` returns only matching rows.
  - `test_get_audit_log_pagination`: `?limit=1&offset=0` returns at most 1 entry.
  - `test_middleware_logs_post_request`: make a `POST` to any endpoint; assert one `EventLog` row exists in `audit.event_log` with `action="create"`.
  - `test_middleware_logs_delete_request`: make a `DELETE`; assert `action="delete"` in new row.
  - `test_middleware_skips_get_request`: make a `GET`; assert no new `EventLog` row.
  - `test_middleware_audit_failure_does_not_break_response`: patch `write_event_log` to raise; assert the original response is still returned unchanged.
  - **Acceptance**: all tests RED before implementation; all GREEN after.
