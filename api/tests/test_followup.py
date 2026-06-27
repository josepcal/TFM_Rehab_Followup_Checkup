"""Unit tests for the followup checkup endpoints (UC-09).

All tests use a FakeSession — no live DB required. They exercise the router
functions directly, injecting fakes for db and principal (bypassing FastAPI
dependency injection).
"""

import uuid
from datetime import date
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.followup import router as followup_router
from app.followup.schemas import CheckupIn


# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

MEDICAL = {"sub": "doc-sub", "role": "medical"}
PATIENT = {"sub": "pat-sub", "role": "patient"}
TECHNICIAN = {"sub": "tec-sub", "role": "technician"}

IDENTITY_ID = uuid.uuid4()

PROG_ID = uuid.uuid4()
PROG_ID_2 = uuid.uuid4()
DIAG_ID = uuid.uuid4()
PATIENT_ID = uuid.uuid4()
DOCTOR_ID = uuid.uuid4()
REPORT_ID_1 = uuid.uuid4()
REPORT_ID_2 = uuid.uuid4()
CHECKUP_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Fake session infrastructure
# ---------------------------------------------------------------------------


class FakeExecuteResult:
    """Returned by FakeSession.execute() — supports .all()."""

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeScalarResult:
    """Returned by FakeSession.scalars() — supports .all()."""

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    """Minimal SQLAlchemy session stub for isolated unit tests.

    ``scalar_values``   — consumed sequentially by .scalar() calls.
    ``execute_rows``    — returned by .execute().all() (used for aggregation queries).
    ``scalars_rows``    — returned by .scalars().all() (used for ORM object lists).
    """

    def __init__(
        self,
        identity_id: uuid.UUID | None = IDENTITY_ID,
        scalar_values: list | None = None,
        execute_rows: list | None = None,
        scalars_rows: list | None = None,
    ):
        self.added: list = []
        self.deleted: list = []
        self.flushed = False
        self.committed = False
        self.info = {"identity_id": str(identity_id)} if identity_id else {}
        self._scalar_values = list(scalar_values or [])
        self._execute_rows = list(execute_rows or [])
        self._scalars_rows = list(scalars_rows or [])

    def scalar(self, _statement) -> Any:
        return self._scalar_values.pop(0) if self._scalar_values else None

    def execute(self, _statement) -> FakeExecuteResult:
        return FakeExecuteResult(self._execute_rows)

    def scalars(self, _statement) -> FakeScalarResult:
        return FakeScalarResult(self._scalars_rows)

    def add(self, value: Any) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flushed = True
        for obj in self.added:
            if not getattr(obj, "followup_checkup_id", None):
                obj.followup_checkup_id = uuid.uuid4()

    def delete(self, value: Any) -> None:
        self.deleted.append(value)

    def commit(self) -> None:
        self.committed = True

    def get(self, model, pk):
        """Convenience: return the next scalar value (simulates db.get)."""
        return self._scalar_values.pop(0) if self._scalar_values else None


# ---------------------------------------------------------------------------
# Factory helpers for fake rows
# ---------------------------------------------------------------------------


def _program_row(
    prog_id: uuid.UUID = PROG_ID,
    diag_id: uuid.UUID = DIAG_ID,
):
    """Fake RehabProgram ORM row."""
    return type(
        "Program",
        (),
        {"id": prog_id, "rehab_program_id": prog_id, "diagnostic_id": diag_id},
    )()


def _diagnostic_row(
    diag_id: uuid.UUID = DIAG_ID,
    patient_id: uuid.UUID = PATIENT_ID,
):
    """Fake Diagnostic ORM row."""
    return type(
        "Diagnostic",
        (),
        {"id": diag_id, "patient_id": patient_id},
    )()


def _doctor_row(
    doctor_id: uuid.UUID = DOCTOR_ID,
    identity_id: uuid.UUID = IDENTITY_ID,
):
    """Fake Doctor ORM row."""
    return type(
        "Doctor",
        (),
        {"id": doctor_id, "identity_id": identity_id},
    )()


def _report_row(
    report_id: uuid.UUID = REPORT_ID_1,
    prog_id: uuid.UUID = PROG_ID,
):
    """Fake ExerciseReport ORM row."""
    return type(
        "ExerciseReport",
        (),
        {
            "exercise_report_id": report_id,
            "rehab_program_id": prog_id,
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "summary": "Report summary",
        },
    )()


def _checkup_row(
    checkup_id: uuid.UUID = CHECKUP_ID,
    prog_id: uuid.UUID = PROG_ID,
    patient_id: uuid.UUID = PATIENT_ID,
):
    """Fake FollowupCheckup ORM row."""
    return type(
        "Checkup",
        (),
        {
            "followup_checkup_id": checkup_id,
            "rehab_program_id": prog_id,
            "patient_id": patient_id,
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "summary": "Checkup summary",
            "created_by": DOCTOR_ID,
            "created_at": None,
        },
    )()


def _list_checkup_row(
    checkup_id: uuid.UUID = CHECKUP_ID,
    prog_id: uuid.UUID = PROG_ID,
    report_count: int = 2,
):
    """Flat row returned by aggregate SELECT in list_program_checkups."""
    return type(
        "ListRow",
        (),
        {
            "followup_checkup_id": checkup_id,
            "rehab_program_id": prog_id,
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "summary": None,
            "created_by": DOCTOR_ID,
            "created_by_name": None,
            "report_count": report_count,
        },
    )()


# ---------------------------------------------------------------------------
# Task 6.1 — Schema validators
# ---------------------------------------------------------------------------


class TestCheckupInSchema:
    def test_valid_period_equal_dates(self):
        d = date(2026, 6, 1)
        body = CheckupIn(
            rehab_program_id=PROG_ID,
            exercise_report_ids=[REPORT_ID_1],
            period_start=d,
            period_end=d,
        )
        assert body.period_start == body.period_end

    def test_period_end_before_start_raises_validation_error(self):
        with pytest.raises(ValidationError):
            CheckupIn(
                rehab_program_id=PROG_ID,
                exercise_report_ids=[REPORT_ID_1],
                period_start=date(2026, 6, 10),
                period_end=date(2026, 6, 1),
            )

    def test_empty_exercise_report_ids_raises_validation_error(self):
        with pytest.raises(ValidationError):
            CheckupIn(
                rehab_program_id=PROG_ID,
                exercise_report_ids=[],
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 30),
            )

    def test_valid_body_no_error(self):
        body = CheckupIn(
            rehab_program_id=PROG_ID,
            exercise_report_ids=[REPORT_ID_1, REPORT_ID_2],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            summary="A useful summary",
        )
        assert len(body.exercise_report_ids) == 2


# ---------------------------------------------------------------------------
# Task 6.2 — POST /followup-checkups
# ---------------------------------------------------------------------------


class TestCreateCheckup:
    def _body(self, **overrides):
        base = dict(
            rehab_program_id=PROG_ID,
            exercise_report_ids=[REPORT_ID_1],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
        )
        base.update(overrides)
        return CheckupIn(**base)

    def test_valid_body_creates_checkup_and_returns_201(self):
        program = _program_row()
        diagnostic = _diagnostic_row()
        doctor = _doctor_row()
        report = _report_row()
        # scalar order: program, diagnostic, doctor, report (cross-program check)
        session = FakeSession(scalar_values=[program, diagnostic, doctor, report])
        result = followup_router.create_checkup(self._body(), MEDICAL, session)
        assert result.followup_checkup_id is not None
        assert session.flushed

    def test_patient_id_is_derived_from_diagnostic(self):
        program = _program_row(diag_id=DIAG_ID)
        diagnostic = _diagnostic_row(patient_id=PATIENT_ID)
        doctor = _doctor_row()
        report = _report_row()
        session = FakeSession(scalar_values=[program, diagnostic, doctor, report])
        followup_router.create_checkup(self._body(), MEDICAL, session)
        # Find the FollowupCheckup object in added list
        from app.followup.models import FollowupCheckup
        checkup_obj = next(
            obj for obj in session.added
            if isinstance(obj, FollowupCheckup)
        )
        assert checkup_obj.patient_id == PATIENT_ID

    def test_period_end_before_start_is_422_via_pydantic(self):
        with pytest.raises(ValidationError):
            self._body(period_start=date(2026, 6, 10), period_end=date(2026, 6, 1))

    def test_empty_report_list_is_422_via_pydantic(self):
        with pytest.raises(ValidationError):
            self._body(exercise_report_ids=[])

    def test_unknown_program_returns_404(self):
        session = FakeSession(scalar_values=[None])
        with pytest.raises(HTTPException) as exc:
            followup_router.create_checkup(self._body(), MEDICAL, session)
        assert exc.value.status_code == 404

    def test_non_medical_role_returns_403(self):
        with pytest.raises(HTTPException) as exc:
            followup_router.create_checkup(self._body(), PATIENT, FakeSession())
        assert exc.value.status_code == 403

    def test_cross_program_report_returns_422(self):
        program = _program_row(prog_id=PROG_ID)
        diagnostic = _diagnostic_row()
        doctor = _doctor_row()
        # Report belongs to a DIFFERENT program
        wrong_report = _report_row(prog_id=PROG_ID_2)
        session = FakeSession(scalar_values=[program, diagnostic, doctor, wrong_report])
        with pytest.raises(HTTPException) as exc:
            followup_router.create_checkup(self._body(), MEDICAL, session)
        assert exc.value.status_code == 422
        assert str(REPORT_ID_1) in str(exc.value.detail)


# ---------------------------------------------------------------------------
# Task 6.3 — GET /programs/{program_id}/followup-checkups
# ---------------------------------------------------------------------------


class TestListProgramCheckups:
    def test_returns_list_with_report_count(self):
        row = _list_checkup_row(report_count=3)
        session = FakeSession(execute_rows=[row])
        result = followup_router.list_program_checkups(PROG_ID, MEDICAL, session)
        assert len(result) == 1
        assert result[0].report_count == 3

    def test_returns_empty_list_when_no_checkups(self):
        session = FakeSession(execute_rows=[])
        result = followup_router.list_program_checkups(PROG_ID, MEDICAL, session)
        assert result == []

    def test_technician_returns_403(self):
        with pytest.raises(HTTPException) as exc:
            followup_router.list_program_checkups(PROG_ID, TECHNICIAN, FakeSession())
        assert exc.value.status_code == 403

    def test_patient_can_access(self):
        row = _list_checkup_row(report_count=1)
        session = FakeSession(execute_rows=[row])
        result = followup_router.list_program_checkups(PROG_ID, PATIENT, session)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Task 6.4 — GET /followup-checkups/{checkup_id}
# ---------------------------------------------------------------------------


class TestGetCheckupDetail:
    def test_full_detail_with_reports(self):
        checkup = _checkup_row()
        report_row = _report_row()
        session = FakeSession(scalar_values=[checkup], scalars_rows=[report_row])
        result = followup_router.get_checkup_detail(CHECKUP_ID, MEDICAL, session)
        assert result.followup_checkup_id == CHECKUP_ID
        assert len(result.reports) == 1

    def test_checkup_not_found_returns_404(self):
        session = FakeSession(scalar_values=[None])
        with pytest.raises(HTTPException) as exc:
            followup_router.get_checkup_detail(uuid.uuid4(), MEDICAL, session)
        assert exc.value.status_code == 404

    def test_technician_returns_403(self):
        with pytest.raises(HTTPException) as exc:
            followup_router.get_checkup_detail(CHECKUP_ID, TECHNICIAN, FakeSession())
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Task 6.5 — PATCH /followup-checkups/{checkup_id}
# ---------------------------------------------------------------------------


class TestUpdateCheckupSummary:
    def test_updates_summary_returns_204(self):
        checkup = _checkup_row()
        session = FakeSession(scalar_values=[checkup])
        from app.followup.schemas import CheckupPatchIn
        body = CheckupPatchIn(summary="Updated summary")
        result = followup_router.update_checkup(CHECKUP_ID, body, MEDICAL, session)
        assert result is None
        assert checkup.summary == "Updated summary"

    def test_checkup_not_found_returns_404(self):
        session = FakeSession(scalar_values=[None])
        from app.followup.schemas import CheckupPatchIn
        body = CheckupPatchIn(summary="X")
        with pytest.raises(HTTPException) as exc:
            followup_router.update_checkup(uuid.uuid4(), body, MEDICAL, session)
        assert exc.value.status_code == 404

    def test_non_medical_returns_403(self):
        from app.followup.schemas import CheckupPatchIn
        body = CheckupPatchIn(summary="X")
        with pytest.raises(HTTPException) as exc:
            followup_router.update_checkup(CHECKUP_ID, body, PATIENT, FakeSession())
        assert exc.value.status_code == 403

    def test_summary_can_be_set_to_none(self):
        checkup = _checkup_row()
        session = FakeSession(scalar_values=[checkup])
        from app.followup.schemas import CheckupPatchIn
        body = CheckupPatchIn(summary=None)
        followup_router.update_checkup(CHECKUP_ID, body, MEDICAL, session)
        assert checkup.summary is None


# ---------------------------------------------------------------------------
# Task 6.6 — DELETE /followup-checkups/{checkup_id}
# ---------------------------------------------------------------------------


class TestDeleteCheckup:
    def test_delete_removes_checkup_returns_204(self):
        checkup = _checkup_row()
        session = FakeSession(scalar_values=[checkup])
        result = followup_router.delete_checkup(CHECKUP_ID, MEDICAL, session)
        assert result is None
        assert checkup in session.deleted

    def test_checkup_not_found_returns_404(self):
        session = FakeSession(scalar_values=[None])
        with pytest.raises(HTTPException) as exc:
            followup_router.delete_checkup(uuid.uuid4(), MEDICAL, session)
        assert exc.value.status_code == 404

    def test_non_medical_returns_403(self):
        with pytest.raises(HTTPException) as exc:
            followup_router.delete_checkup(CHECKUP_ID, PATIENT, FakeSession())
        assert exc.value.status_code == 403
