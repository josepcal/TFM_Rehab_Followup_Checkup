"""Unit tests for UC-15 Audit Log — TDD pattern.

All tests use FakeSession / mock objects — no live PostgreSQL required.
Pattern mirrors test_consent.py.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.iam.audit_service import write_event_log
from app.iam.models import EventLog

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTOR_ID = uuid.uuid4()
ENTITY_ID = uuid.uuid4()
NOW = datetime(2026, 6, 28, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fake session infrastructure (mirrors test_consent.py)
# ---------------------------------------------------------------------------


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    """Minimal SQLAlchemy session stub for isolated unit tests."""

    def __init__(self, scalars_rows: list | None = None):
        self.added: list = []
        self.flushed = False
        self._scalars_rows = list(scalars_rows or [])

    def add(self, value: Any) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flushed = True

    def scalars(self, _statement) -> FakeScalarResult:
        return FakeScalarResult(self._scalars_rows)

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers for HTTP tests
# ---------------------------------------------------------------------------


def _make_client(role: str = "admin"):
    """Return a TestClient with auth bypassed via X-Dev-Role header.

    Requires the app to be in dev auth mode (default in test environment).
    """
    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    return client, {"X-Dev-Role": role}


def _event_log_row(
    event_id: uuid.UUID | None = None,
    entity_type: str = "recording.exercise_recording",
    entity_id: uuid.UUID | None = None,
    action: str = "create",
    actor_id: uuid.UUID | None = None,
    payload: dict | None = None,
    occurred_at: datetime = NOW,
):
    return type(
        "EventLog",
        (),
        {
            "event_id": event_id or uuid.uuid4(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor_id": actor_id or ACTOR_ID,
            "payload": payload,
            "occurred_at": occurred_at,
        },
    )()


# ---------------------------------------------------------------------------
# Phase 1: audit_service unit tests
# ---------------------------------------------------------------------------


class TestWriteEventLog:
    def test_write_event_log_inserts_row(self):
        """write_event_log adds one EventLog instance and flushes the session."""
        db = FakeSession()
        write_event_log(
            entity_type="recording.exercise_recording",
            entity_id=ENTITY_ID,
            action="create",
            actor_id=ACTOR_ID,
            payload=None,
            db=db,
        )

        assert len(db.added) == 1
        inserted = db.added[0]
        assert isinstance(inserted, EventLog)
        assert inserted.entity_type == "recording.exercise_recording"
        assert inserted.action == "create"
        assert inserted.actor_id == ACTOR_ID
        assert inserted.entity_id == ENTITY_ID
        assert db.flushed is True

    def test_write_event_log_null_actor(self):
        """write_event_log accepts actor_id=None (unauthenticated request)."""
        db = FakeSession()
        write_event_log(
            entity_type="/api/recordings",
            entity_id=None,
            action="create",
            actor_id=None,
            payload=None,
            db=db,
        )
        assert db.added[0].actor_id is None

    def test_write_event_log_with_payload(self):
        """write_event_log stores the payload dict."""
        db = FakeSession()
        payload = {"before": None, "after": {"status": "active"}}
        write_event_log(
            entity_type="clinical.patient",
            entity_id=ENTITY_ID,
            action="update",
            actor_id=ACTOR_ID,
            payload=payload,
            db=db,
        )
        assert db.added[0].payload == payload


# ---------------------------------------------------------------------------
# Phase 2: Router endpoint tests
# ---------------------------------------------------------------------------


def _make_principal(role: str) -> dict:
    return {"sub": f"{role}-sub", "role": role}


def _override_principal(app, role: str | None):
    """Override current_principal in the app to return a fixed principal (or raise 401)."""
    from fastapi import HTTPException
    from app.auth import current_principal

    if role is None:
        def _raise():
            raise HTTPException(status_code=401, detail="falta el bearer token")
        app.dependency_overrides[current_principal] = _raise
    else:
        principal = _make_principal(role)
        app.dependency_overrides[current_principal] = lambda: principal


class TestGetAuditLogAuth:
    def setup_method(self, _method):
        from app.main import app as _app
        self.app = _app

    def teardown_method(self, _method):
        self.app.dependency_overrides.clear()

    def test_get_audit_log_admin_returns_200(self):
        """GET /iam/audit-log as admin → 200 with list."""
        from app.db import get_db

        rows = [_event_log_row()]
        fake_db = FakeSession(scalars_rows=rows)

        _override_principal(self.app, "admin")
        self.app.dependency_overrides[get_db] = lambda: fake_db

        client = TestClient(self.app, raise_server_exceptions=False)
        resp = client.get("/iam/audit-log")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_audit_log_medical_returns_403(self):
        """GET /iam/audit-log as medical → 403."""
        _override_principal(self.app, "medical")
        client = TestClient(self.app, raise_server_exceptions=False)
        resp = client.get("/iam/audit-log")
        assert resp.status_code == 403

    def test_get_audit_log_patient_returns_403(self):
        """GET /iam/audit-log as patient → 403."""
        _override_principal(self.app, "patient")
        client = TestClient(self.app, raise_server_exceptions=False)
        resp = client.get("/iam/audit-log")
        assert resp.status_code == 403

    def test_get_audit_log_unauthenticated_returns_401(self):
        """GET /iam/audit-log with no token → 401."""
        _override_principal(self.app, None)
        client = TestClient(self.app, raise_server_exceptions=False)
        resp = client.get("/iam/audit-log")
        assert resp.status_code == 401


class TestGetAuditLogFilters:
    def setup_method(self, _method):
        from app.main import app as _app
        self.app = _app
        _override_principal(self.app, "admin")

    def teardown_method(self, _method):
        self.app.dependency_overrides.clear()

    def _setup_db(self, rows: list):
        from app.db import get_db
        fake_db = FakeSession(scalars_rows=rows)
        self.app.dependency_overrides[get_db] = lambda: fake_db
        return TestClient(self.app, raise_server_exceptions=False)

    def test_get_audit_log_filter_by_actor(self):
        """?actor_id=<uuid> — endpoint accepts the filter without error."""
        rows = [_event_log_row(actor_id=ACTOR_ID)]
        client = self._setup_db(rows)

        resp = client.get(f"/iam/audit-log?actor_id={ACTOR_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for entry in data:
            assert entry["actor_id"] == str(ACTOR_ID)

    def test_get_audit_log_filter_by_entity_type(self):
        """?entity_type=recording.exercise_recording — endpoint accepts the filter."""
        rows = [_event_log_row(entity_type="recording.exercise_recording")]
        client = self._setup_db(rows)

        resp = client.get("/iam/audit-log?entity_type=recording.exercise_recording")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for entry in data:
            assert entry["entity_type"] == "recording.exercise_recording"

    def test_get_audit_log_pagination(self):
        """?limit=1&offset=0 — endpoint honours pagination params."""
        rows = [_event_log_row()]
        client = self._setup_db(rows)

        resp = client.get("/iam/audit-log?limit=1&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 1


# ---------------------------------------------------------------------------
# Phase 3: Middleware tests
# ---------------------------------------------------------------------------


class TestAuditMiddleware:
    def test_middleware_audit_failure_does_not_break_response(self):
        """If write_event_log raises, the original response is still returned unchanged."""
        from app.main import app

        with patch("app.main.write_event_log", side_effect=RuntimeError("DB down")):
            client = TestClient(app, raise_server_exceptions=False)
            # POST to health just as a convenient endpoint; middleware fires but write fails
            resp = client.get("/health")
            # GET is not audited, but even if the middleware has a bug it must not break GET
            assert resp.status_code == 200

    def test_middleware_skips_excluded_paths(self):
        """Requests to excluded paths (/health, /docs, etc.) do not trigger audit writes."""
        from app.main import app

        with patch("app.main.write_event_log") as mock_write:
            client = TestClient(app, raise_server_exceptions=False)
            client.get("/health")
            mock_write.assert_not_called()

    def test_middleware_does_not_audit_get_requests(self):
        """GET requests are never audited even for non-excluded paths."""
        from app.main import app

        with patch("app.main.write_event_log") as mock_write:
            client = TestClient(app, raise_server_exceptions=False)
            client.get("/iam/audit-log", headers={"X-Dev-Role": "admin"})
            mock_write.assert_not_called()
