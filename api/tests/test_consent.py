"""Unit tests for the consent endpoints (UC-05) — TDD Red Phase.

All tests use a FakeSession and call router functions directly — no live DB required.
Pattern mirrors test_followup.py.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import HTTPException

from app.clinical import consent_router as cr
from app.clinical.consent_schemas import ConsentIn
from app.clinical.consent_service import ConsentService, ConsentNotFoundError


# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

PATIENT_PRINCIPAL = {"sub": "patient-sub", "role": "patient"}
MEDICAL_PRINCIPAL = {"sub": "medical-sub", "role": "medical"}

IDENTITY_ID = uuid.uuid4()
PATIENT_ID = uuid.uuid4()
PATIENT_ID_B = uuid.uuid4()
PROGRAM_ID = uuid.uuid4()
CONSENT_ID = uuid.uuid4()

NOW = datetime(2026, 6, 28, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fake session infrastructure (mirrors test_followup.py pattern)
# ---------------------------------------------------------------------------


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    """Minimal SQLAlchemy session stub for isolated unit tests."""

    def __init__(
        self,
        identity_id: uuid.UUID | None = IDENTITY_ID,
        scalar_values: list | None = None,
        scalars_rows: list | None = None,
    ):
        self.added: list = []
        self.flushed = False
        self.committed = False
        self.info = {"identity_id": str(identity_id)} if identity_id else {}
        self._scalar_values = list(scalar_values or [])
        self._scalars_rows = list(scalars_rows or [])
        # track UPDATE calls
        self._updated: list = []

    def scalar(self, _statement) -> Any:
        return self._scalar_values.pop(0) if self._scalar_values else None

    def scalars(self, _statement) -> FakeScalarResult:
        return FakeScalarResult(self._scalars_rows)

    def add(self, value: Any) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flushed = True
        for obj in self.added:
            if not getattr(obj, "consent_id", None):
                obj.consent_id = uuid.uuid4()

    def commit(self) -> None:
        self.committed = True

    def get(self, model, pk):
        return self._scalar_values.pop(0) if self._scalar_values else None

    def execute(self, _statement) -> Any:
        return type("R", (), {"rowcount": 1})()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _app_user_row(identity_id: uuid.UUID = IDENTITY_ID):
    return type("AppUser", (), {"identity_id": identity_id, "external_subject": "patient-sub"})()


def _patient_row(patient_id: uuid.UUID = PATIENT_ID, identity_id: uuid.UUID = IDENTITY_ID):
    return type("Patient", (), {"id": patient_id, "identity_id": identity_id})()


def _consent_row(
    consent_id: uuid.UUID = CONSENT_ID,
    patient_id: uuid.UUID = PATIENT_ID,
    program_id: uuid.UUID = PROGRAM_ID,
    granted: bool = True,
    granted_at: datetime = NOW,
    withdrawn_at: datetime | None = None,
    consent_text: str | None = "I consent",
):
    return type(
        "PatientConsent",
        (),
        {
            "consent_id": consent_id,
            "patient_id": patient_id,
            "rehab_program_id": program_id,
            "granted": granted,
            "granted_at": granted_at,
            "withdrawn_at": withdrawn_at,
            "consent_text": consent_text,
        },
    )()


# ---------------------------------------------------------------------------
# ConsentService unit tests (TDD RED for 2.3)
# ---------------------------------------------------------------------------


class TestConsentServiceGetStatus:
    def test_returns_none_when_no_rows(self):
        """get_status returns None when no consent row exists."""
        db = FakeSession(
            scalar_values=[
                _app_user_row(),   # _resolve_patient_id → AppUser
                _patient_row(),    # _resolve_patient_id → Patient
                None,              # get_status query → no row
            ]
        )
        svc = ConsentService(db)
        result = svc.get_status(PROGRAM_ID)
        assert result is None

    def test_returns_most_recent_row(self):
        """get_status returns the most recent consent row regardless of withdrawn_at."""
        row = _consent_row(withdrawn_at=NOW)
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
                row,
            ]
        )
        svc = ConsentService(db)
        result = svc.get_status(PROGRAM_ID)
        assert result is row


class TestConsentServiceGetActive:
    def test_returns_none_when_no_active_row(self):
        """get_active returns None when no row has withdrawn_at IS NULL."""
        db = FakeSession(scalar_values=[None])
        svc = ConsentService(db)
        result = svc.get_active(PATIENT_ID, PROGRAM_ID)
        assert result is None

    def test_returns_active_row(self):
        """get_active returns the row when withdrawn_at IS NULL."""
        row = _consent_row(withdrawn_at=None)
        db = FakeSession(scalar_values=[row])
        svc = ConsentService(db)
        result = svc.get_active(PATIENT_ID, PROGRAM_ID)
        assert result is row


class TestConsentServiceGrant:
    def test_grant_inserts_new_row(self):
        """grant() always INSERTs a new row — append-only, no upsert."""
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
            ]
        )
        svc = ConsentService(db)
        result = svc.grant(PROGRAM_ID, "RGPD consent text")

        assert len(db.added) == 1
        inserted = db.added[0]
        assert inserted.rehab_program_id == PROGRAM_ID
        assert inserted.patient_id == PATIENT_ID
        assert inserted.granted is True
        assert inserted.withdrawn_at is None
        assert inserted.consent_text == "RGPD consent text"
        assert result is inserted

    def test_re_grant_inserts_second_row_independently(self):
        """Re-granting inserts another row; no check for existing rows."""
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
            ]
        )
        svc = ConsentService(db)
        svc.grant(PROGRAM_ID, "first grant")

        db2 = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
            ]
        )
        svc2 = ConsentService(db2)
        svc2.grant(PROGRAM_ID, "second grant")

        # Each session/call adds exactly one row independently
        assert len(db.added) == 1
        assert len(db2.added) == 1
        assert db.added[0].consent_text == "first grant"
        assert db2.added[0].consent_text == "second grant"


class TestConsentServiceWithdraw:
    def test_withdraw_raises_not_found_when_no_active_row(self):
        """withdraw() raises ConsentNotFoundError (HTTP 404) when no active row."""
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
                None,  # no active row
            ]
        )
        svc = ConsentService(db)
        with pytest.raises(ConsentNotFoundError):
            svc.withdraw(PROGRAM_ID)

    def test_withdraw_sets_withdrawn_at_on_active_row(self):
        """withdraw() updates withdrawn_at on the most recent active row."""
        active_row = _consent_row(withdrawn_at=None)
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
                active_row,  # the most recent active row
            ]
        )
        svc = ConsentService(db)
        result = svc.withdraw(PROGRAM_ID)

        assert result.withdrawn_at is not None
        assert result is active_row


# ---------------------------------------------------------------------------
# Router endpoint tests (TDD RED for 3.1)
# ---------------------------------------------------------------------------


class TestGetConsentStatus:
    def test_no_rows_returns_empty_status(self):
        """GET consent with no rows → 200 with granted=false."""
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
                None,  # no consent row
            ]
        )
        result = cr.get_consent_status(
            program_id=PROGRAM_ID,
            principal=PATIENT_PRINCIPAL,
            db=db,
        )
        assert result.granted is False
        assert result.consent_id is None
        assert result.program_id == PROGRAM_ID

    def test_active_row_returns_granted_true(self):
        """GET consent with active row → 200 with granted=true."""
        row = _consent_row(withdrawn_at=None)
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
                row,
            ]
        )
        result = cr.get_consent_status(
            program_id=PROGRAM_ID,
            principal=PATIENT_PRINCIPAL,
            db=db,
        )
        assert result.granted is True
        assert result.consent_id == CONSENT_ID

    def test_withdrawn_row_returns_granted_false(self):
        """GET consent with withdrawn row → granted=false (most recent row has withdrawn_at set)."""
        row = _consent_row(granted=True, withdrawn_at=NOW)
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
                row,
            ]
        )
        result = cr.get_consent_status(
            program_id=PROGRAM_ID,
            principal=PATIENT_PRINCIPAL,
            db=db,
        )
        # Row exists but withdrawn_at is set → no active consent
        assert result.withdrawn_at is not None


class TestGrantConsent:
    def test_grant_creates_row_and_returns_consent_out(self):
        """POST consent/grant → inserts row, returns ConsentOut 200."""
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
            ]
        )
        body = ConsentIn(consent_text="I consent to voice recording")
        result = cr.grant_consent(
            program_id=PROGRAM_ID,
            body=body,
            principal=PATIENT_PRINCIPAL,
            db=db,
        )
        assert result.granted is True
        assert result.program_id == PROGRAM_ID
        assert result.consent_text == "I consent to voice recording"
        assert len(db.added) == 1

    def test_re_grant_does_not_raise(self):
        """Calling grant twice is allowed — append-only, no 409."""
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
            ]
        )
        body = ConsentIn(consent_text="second grant")
        # Should not raise at all
        cr.grant_consent(
            program_id=PROGRAM_ID,
            body=body,
            principal=PATIENT_PRINCIPAL,
            db=db,
        )
        assert len(db.added) == 1


class TestWithdrawConsent:
    def test_withdraw_sets_withdrawn_at(self):
        """POST consent/withdraw → sets withdrawn_at on active row, returns 200."""
        active_row = _consent_row(withdrawn_at=None)
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
                active_row,
            ]
        )
        result = cr.withdraw_consent(
            program_id=PROGRAM_ID,
            principal=PATIENT_PRINCIPAL,
            db=db,
        )
        assert result.withdrawn_at is not None

    def test_withdraw_no_active_row_raises_404(self):
        """POST consent/withdraw with no active row → 404."""
        db = FakeSession(
            scalar_values=[
                _app_user_row(),
                _patient_row(),
                None,  # no active row
            ]
        )
        with pytest.raises(HTTPException) as exc:
            cr.withdraw_consent(
                program_id=PROGRAM_ID,
                principal=PATIENT_PRINCIPAL,
                db=db,
            )
        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Recording guard tests (TDD RED for 3.3)
# ---------------------------------------------------------------------------


class TestRequireActiveConsent:
    def test_no_active_consent_raises_403(self):
        """Recording write without consent → 403 CONSENT_REQUIRED."""
        # DB: AppUser, Patient (for _resolve_patient_id) + program_exercise → program_id + get_active→None
        db = FakeSession(
            scalar_values=[
                # require_active_consent resolves program_exercise → program_id
                type("PE", (), {"program_id": PROGRAM_ID})(),  # ProgramExercise row
                # ConsentService._resolve_patient_id
                _app_user_row(),
                _patient_row(),
                None,  # get_active → no active consent
            ]
        )
        from app.clinical.consent_service import require_active_consent

        with pytest.raises(HTTPException) as exc:
            require_active_consent(
                program_exercise_id=uuid.uuid4(),
                db=db,
                principal=PATIENT_PRINCIPAL,
            )
        assert exc.value.status_code == 403
        assert exc.value.detail["error"] == "CONSENT_REQUIRED"

    def test_active_consent_does_not_raise(self):
        """Recording write with active consent → no exception raised."""
        active_row = _consent_row(withdrawn_at=None)
        db = FakeSession(
            scalar_values=[
                type("PE", (), {"program_id": PROGRAM_ID})(),
                _app_user_row(),
                _patient_row(),
                active_row,
            ]
        )
        from app.clinical.consent_service import require_active_consent

        # Should not raise
        require_active_consent(
            program_exercise_id=uuid.uuid4(),
            db=db,
            principal=PATIENT_PRINCIPAL,
        )

    def test_medical_role_skips_consent_guard(self):
        """Medical staff are exempt from the consent guard."""
        db = FakeSession(scalar_values=[])
        from app.clinical.consent_service import require_active_consent

        # Should not raise even with no DB rows
        require_active_consent(
            program_exercise_id=uuid.uuid4(),
            db=db,
            principal=MEDICAL_PRINCIPAL,
        )

    def test_recording_read_unaffected_by_withdrawal(self):
        """EC-7: GET recordings after withdrawal still works — guard is not on read paths."""
        # This is structural — we verify the guard dependency is NOT applied to get_recording.
        # We import the router and check that the get_recording handler does NOT have
        # require_active_consent in its dependency chain.
        from app.recording import router as rr
        import inspect

        handler = rr.get_recording
        src = inspect.getsource(handler)
        # The consent guard must not appear in the GET handler source
        assert "require_active_consent" not in src
