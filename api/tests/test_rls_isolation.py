"""Cross-patient and cross-role RLS isolation tests (D18).

These tests verify that when RLS filters out a row (simulated by FakeSession
returning None), the router responds with 404/403 — never with another
patient's data. They complement test_db_rls.py (which tests _apply_rls itself)
by exercising the router layer under the assumption that RLS is active.

Pattern: FakeSession returns None for the first scalar() call to simulate that
RLS found no matching row for the requesting patient's identity. The assertion
is that the router raises HTTPException 404 (not 200 with foreign data).
"""

import uuid
from typing import Any

import pytest
from fastapi import HTTPException

from app.recording import router as recording_router
from app.reporting import router as reporting_router
from app.followup import router as followup_router


# ---------------------------------------------------------------------------
# Principals
# ---------------------------------------------------------------------------

PATIENT_A = {"sub": "patient-a-sub", "role": "patient"}
PATIENT_B = {"sub": "patient-b-sub", "role": "patient"}
MEDICAL = {"sub": "doc-sub", "role": "medical"}
TECHNICIAN = {"sub": "tec-sub", "role": "technician"}

IDENTITY_A = uuid.uuid4()
IDENTITY_B = uuid.uuid4()


# ---------------------------------------------------------------------------
# Shared FakeSession
# ---------------------------------------------------------------------------


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    """Minimal session stub. scalar_values consumed sequentially."""

    def __init__(
        self,
        identity_id: uuid.UUID | None = IDENTITY_A,
        scalar_values: list | None = None,
        scalars_rows: list | None = None,
        execute_rows: list | None = None,
    ):
        self.added: list = []
        self.deleted: list = []
        self.flushed = False
        self.committed = False
        self.info = {"identity_id": str(identity_id)} if identity_id else {}
        self._scalar_values = list(scalar_values or [])
        self._scalars_rows = list(scalars_rows or [])
        self._execute_rows = list(execute_rows or [])

    def scalar(self, _statement) -> Any:
        return self._scalar_values.pop(0) if self._scalar_values else None

    def scalars(self, _statement) -> FakeScalarResult:
        return FakeScalarResult(self._scalars_rows)

    def execute(self, _statement) -> FakeExecuteResult:
        return FakeExecuteResult(self._execute_rows)

    def add(self, value: Any) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flushed = True
        for obj in self.added:
            if not getattr(obj, "exercise_report_id", None):
                obj.exercise_report_id = uuid.uuid4()
            if not getattr(obj, "followup_checkup_id", None):
                obj.followup_checkup_id = uuid.uuid4()

    def delete(self, value: Any) -> None:
        self.deleted.append(value)

    def commit(self) -> None:
        self.committed = True

    def get(self, _model, _pk) -> Any:
        return self._scalar_values.pop(0) if self._scalar_values else None


# ---------------------------------------------------------------------------
# Recording isolation
# ---------------------------------------------------------------------------


class TestRecordingCrossPatientIsolation:
    """Patient A cannot access recordings that belong to patient B.

    RLS enforcement: db.scalar() returns None when the program_exercise row
    exists in the DB but belongs to a different patient's RLS context.
    """

    def test_list_recordings_returns_404_when_rls_hides_exercise(self):
        """Patient A requests B's exercise → RLS returns None → 404."""
        foreign_pe_id = uuid.uuid4()
        # scalar_values=[] → scalar() returns None (RLS filtered the row)
        db = FakeSession(identity_id=IDENTITY_A, scalar_values=[None])

        with pytest.raises(HTTPException) as exc_info:
            recording_router.list_exercise_recordings(
                foreign_pe_id,
                PATIENT_A,
                db,
            )

        assert exc_info.value.status_code == 404

    def test_get_recording_detail_returns_404_when_rls_hides_row(self):
        """GET /recordings/{id} with a foreign recording ID → 404.

        _require_authorized_recording calls scalar() once for ExerciseRecording.
        When RLS hides the row, scalar() returns None → 404 before access check.
        """
        foreign_rec_id = uuid.uuid4()
        # scalar() returns None: RLS filtered the ExerciseRecording row
        db = FakeSession(identity_id=IDENTITY_A, scalar_values=[None])

        with pytest.raises(HTTPException) as exc_info:
            recording_router.get_recording(
                foreign_rec_id,
                PATIENT_A,
                db,
            )

        assert exc_info.value.status_code == 404

    def test_delete_recording_returns_404_when_rls_hides_row(self):
        """Patient A cannot delete patient B's recording — 404 before any mutation.

        delete_recording takes (request, recording_id, principal, db).
        We pass request=None (the router handles None request safely).
        """
        from unittest.mock import MagicMock
        foreign_rec_id = uuid.uuid4()
        db = FakeSession(identity_id=IDENTITY_A, scalar_values=[None])
        fake_request = MagicMock()
        fake_request.state = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            recording_router.delete_recording(
                fake_request,
                foreign_rec_id,
                PATIENT_A,
                db,
            )

        assert exc_info.value.status_code == 404

    def test_get_insight_returns_404_when_rls_hides_recording(self):
        """GET insight for a foreign recording → recording hidden by RLS → 404.

        get_recording_insight calls _require_authorized_recording first,
        which returns 404 when scalar() yields None for the ExerciseRecording.
        """
        foreign_rec_id = uuid.uuid4()
        db = FakeSession(identity_id=IDENTITY_A, scalar_values=[None])

        with pytest.raises(HTTPException) as exc_info:
            recording_router.get_recording_insight(
                foreign_rec_id,
                PATIENT_A,
                db,
            )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Reporting isolation
# ---------------------------------------------------------------------------


class TestReportingCrossPatientIsolation:
    """Patients can only read their own reports (RLS-enforced at DB layer)."""

    def test_get_report_detail_returns_404_when_rls_hides_report(self):
        """GET /reports/{id} where RLS filters out the row → 404."""
        foreign_report_id = uuid.uuid4()
        # scalar() → None (RLS hides foreign report)
        db = FakeSession(identity_id=IDENTITY_A, scalar_values=[None])

        with pytest.raises(HTTPException) as exc_info:
            reporting_router.get_report_detail(
                foreign_report_id,
                PATIENT_A,
                db,
            )

        assert exc_info.value.status_code == 404

    def test_list_program_reports_returns_empty_when_rls_filters_all(self):
        """GET /programs/{id}/reports where RLS hides all rows → empty list."""
        foreign_prog_id = uuid.uuid4()
        # scalars_rows=[] → RLS filtered all rows for this patient
        db = FakeSession(
            identity_id=IDENTITY_A,
            scalar_values=[foreign_prog_id],  # program existence check passes
            execute_rows=[],                   # aggregation returns nothing
            scalars_rows=[],                   # report rows hidden by RLS
        )

        result = reporting_router.list_program_reports(
            foreign_prog_id,
            PATIENT_A,
            db,
        )

        assert result == []

    def test_delete_report_returns_404_when_rls_hides_report(self):
        """DELETE /reports/{id} where RLS hides the row → 404, nothing deleted."""
        foreign_report_id = uuid.uuid4()
        db = FakeSession(identity_id=IDENTITY_A, scalar_values=[None])

        with pytest.raises(HTTPException) as exc_info:
            reporting_router.delete_report(
                foreign_report_id,
                MEDICAL,  # only medical can delete; RLS still applies
                db,
            )

        assert exc_info.value.status_code == 404
        assert db.deleted == []


# ---------------------------------------------------------------------------
# Followup isolation
# ---------------------------------------------------------------------------


class TestFollowupCrossPatientIsolation:
    """Patients can only see their own follow-up checkups."""

    def test_get_checkup_detail_returns_404_when_rls_hides_row(self):
        """GET /followup-checkups/{id} where RLS filters the row → 404."""
        foreign_checkup_id = uuid.uuid4()
        db = FakeSession(identity_id=IDENTITY_A, scalar_values=[None])

        with pytest.raises(HTTPException) as exc_info:
            followup_router.get_checkup_detail(
                foreign_checkup_id,
                PATIENT_A,
                db,
            )

        assert exc_info.value.status_code == 404

    def test_list_program_checkups_returns_empty_when_rls_filters_all(self):
        """GET /programs/{id}/followup-checkups where RLS hides all rows → empty list."""
        foreign_prog_id = uuid.uuid4()
        db = FakeSession(
            identity_id=IDENTITY_A,
            scalar_values=[foreign_prog_id],  # program existence check passes
            execute_rows=[],
            scalars_rows=[],
        )

        result = followup_router.list_program_checkups(
            foreign_prog_id,
            PATIENT_A,
            db,
        )

        assert result == []

    def test_delete_checkup_returns_404_when_rls_hides_row(self):
        """DELETE /followup-checkups/{id} where RLS filters → 404, nothing deleted."""
        foreign_checkup_id = uuid.uuid4()
        db = FakeSession(identity_id=IDENTITY_A, scalar_values=[None])

        with pytest.raises(HTTPException) as exc_info:
            followup_router.delete_checkup(
                foreign_checkup_id,
                MEDICAL,
                db,
            )

        assert exc_info.value.status_code == 404
        assert db.deleted == []


# ---------------------------------------------------------------------------
# Clinical endpoints — patient/technician cannot list or create patients
#
# These endpoints use Depends() in their signatures so they can't be called
# directly with a fake principal. We use TestClient + dependency_overrides
# (same pattern as test_audit_log.py).
# ---------------------------------------------------------------------------


class TestClinicalCrossRoleIsolation:
    """Medical-only endpoints must reject non-medical roles regardless of data."""

    def setup_method(self, _method):
        from app.main import app as _app
        self.app = _app

    def teardown_method(self, _method):
        self.app.dependency_overrides.clear()

    def _override(self, role: str | None):
        from app.auth import current_principal
        from fastapi import HTTPException as _HTTPException

        if role is None:
            def _raise():
                raise _HTTPException(status_code=401, detail="no token")
            self.app.dependency_overrides[current_principal] = _raise
        else:
            p = {"sub": f"{role}-sub", "role": role}
            self.app.dependency_overrides[current_principal] = lambda: p

    def _db_override(self, db):
        from app.db import get_db
        self.app.dependency_overrides[get_db] = lambda: db

    def test_patient_cannot_list_patients(self):
        """GET /patients as patient → 403."""
        from starlette.testclient import TestClient

        self._override("patient")
        self._db_override(FakeSession(identity_id=IDENTITY_A, execute_rows=[]))

        client = TestClient(self.app, raise_server_exceptions=False)
        resp = client.get("/patients")
        assert resp.status_code == 403

    def test_technician_cannot_list_patients(self):
        """GET /patients as technician → 403."""
        from starlette.testclient import TestClient

        self._override("technician")
        self._db_override(FakeSession(identity_id=uuid.uuid4(), execute_rows=[]))

        client = TestClient(self.app, raise_server_exceptions=False)
        resp = client.get("/patients")
        assert resp.status_code == 403

    def test_patient_cannot_create_patient(self):
        """POST /patients as patient → 403."""
        from starlette.testclient import TestClient

        self._override("patient")
        self._db_override(FakeSession(identity_id=IDENTITY_A))

        client = TestClient(self.app, raise_server_exceptions=False)
        resp = client.post("/patients", json={"nombre": "Eve", "apellidos": "Evil"})
        assert resp.status_code == 403
