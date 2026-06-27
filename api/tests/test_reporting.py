"""Unit tests for the reporting endpoints (UC-07 / UC-08).

All tests use a FakeSession — no live DB required. They exercise the router
functions directly, injecting fakes for db and principal (bypassing FastAPI
dependency injection).
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.reporting import router as reporting_router
from app.reporting.schemas import ReportIn


# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

MEDICAL = {"sub": "doc-sub", "role": "medical"}
PATIENT = {"sub": "pat-sub", "role": "patient"}
TECHNICIAN = {"sub": "tec-sub", "role": "technician"}

IDENTITY_ID = uuid.uuid4()

PE_ID = uuid.uuid4()
PROG_ID = uuid.uuid4()
REC_ID_1 = uuid.uuid4()
REC_ID_2 = uuid.uuid4()
REPORT_ID = uuid.uuid4()
RESULT_ID = uuid.uuid4()
INSIGHT_ID = uuid.uuid4()


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
        self.flushed = False
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
            if not getattr(obj, "exercise_report_id", None):
                obj.exercise_report_id = uuid.uuid4()


# ---------------------------------------------------------------------------
# Factory helpers for fake rows
# ---------------------------------------------------------------------------


def _pe_row(program_id: uuid.UUID = PROG_ID, pe_id: uuid.UUID = PE_ID):
    """Fake ProgramExercise ORM row."""
    return type("PE", (), {"id": pe_id, "program_id": program_id, "program_exercise_id": pe_id})()


def _recording_row_obj(
    recording_id: uuid.UUID = REC_ID_1,
    program_exercise_id: uuid.UUID = PE_ID,
):
    """Fake ExerciseRecording ORM row."""
    return type(
        "Rec",
        (),
        {
            "recording_id": recording_id,
            "program_exercise_id": program_exercise_id,
            "recording_date": date.today(),
            "duration_seconds": 4.0,
            "media_status": "available",
        },
    )()


def _report_obj(
    report_id: uuid.UUID = REPORT_ID,
    program_id: uuid.UUID = PROG_ID,
    pe_id: uuid.UUID = PE_ID,
):
    """Fake ExerciseReport ORM row."""
    return type(
        "Report",
        (),
        {
            "exercise_report_id": report_id,
            "rehab_program_id": program_id,
            "program_exercise_id": pe_id,
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "summary": "Test summary",
            "created_by": IDENTITY_ID,
            "attested_at": None,
        },
    )()


def _list_report_row(
    report_id: uuid.UUID = REPORT_ID,
    pe_id: uuid.UUID = PE_ID,
    recording_count: int = 2,
):
    """Flat row as returned by the aggregate SELECT in list_program_reports."""
    return type(
        "ListRow",
        (),
        {
            "exercise_report_id": report_id,
            "program_exercise_id": pe_id,
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "summary": None,
            "created_by": IDENTITY_ID,
            "attested_at": None,
            "recording_count": recording_count,
        },
    )()


def _detail_recording_row(
    recording_id: uuid.UUID = REC_ID_1,
    include_metrics: bool = True,
    include_insight: bool = True,
):
    """Flat row as returned by the join SELECT in get_report_detail."""
    return type(
        "DetailRow",
        (),
        {
            "recording_id": recording_id,
            "recording_date": date.today(),
            "duration_seconds": 5.0,
            "media_status": "available",
            "metrics_status": "success" if include_metrics else None,
            "raw_json": {"f0": 220.0} if include_metrics else None,
            "insight_text": "Good phonation" if include_insight else None,
            "model_used": "gpt-4o" if include_insight else None,
        },
    )()


# ---------------------------------------------------------------------------
# Phase 5.5: ReportIn schema validation
# ---------------------------------------------------------------------------


class TestReportInSchema:
    def test_valid_period_equal_dates(self):
        d = date(2026, 6, 1)
        body = ReportIn(
            program_exercise_id=PE_ID,
            recording_ids=[REC_ID_1],
            period_start=d,
            period_end=d,
        )
        assert body.period_start == body.period_end

    def test_period_end_before_start_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ReportIn(
                program_exercise_id=PE_ID,
                recording_ids=[REC_ID_1],
                period_start=date(2026, 6, 10),
                period_end=date(2026, 6, 1),
            )

    def test_empty_recording_ids_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ReportIn(
                program_exercise_id=PE_ID,
                recording_ids=[],
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 30),
            )


# ---------------------------------------------------------------------------
# Phase 5.1: POST /reports
# ---------------------------------------------------------------------------


class TestCreateReport:
    def _body(self, **overrides):
        base = dict(
            program_exercise_id=PE_ID,
            recording_ids=[REC_ID_1],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
        )
        base.update(overrides)
        return ReportIn(**base)

    def test_valid_body_creates_report_and_returns_201(self):
        pe = _pe_row()
        rec = _recording_row_obj()
        # scalar_values: (1) ProgramExercise lookup, (2) ExerciseRecording lookup
        session = FakeSession(scalar_values=[pe, rec])
        result = reporting_router.create_report(self._body(), MEDICAL, session)
        assert result.exercise_report_id is not None
        assert session.flushed

    def test_unknown_program_exercise_returns_404(self):
        session = FakeSession(scalar_values=[None])
        with pytest.raises(HTTPException) as exc:
            reporting_router.create_report(self._body(), MEDICAL, session)
        assert exc.value.status_code == 404

    def test_unknown_recording_returns_404(self):
        pe = _pe_row()
        session = FakeSession(scalar_values=[pe, None])
        with pytest.raises(HTTPException) as exc:
            reporting_router.create_report(self._body(), MEDICAL, session)
        assert exc.value.status_code == 404

    def test_non_medical_role_returns_403(self):
        with pytest.raises(HTTPException) as exc:
            reporting_router.create_report(self._body(), PATIENT, FakeSession())
        assert exc.value.status_code == 403

    def test_period_end_before_start_is_422_via_pydantic(self):
        with pytest.raises(ValidationError):
            self._body(period_start=date(2026, 6, 10), period_end=date(2026, 6, 1))


# ---------------------------------------------------------------------------
# Phase 5.2: GET /programs/{program_id}/reports
# ---------------------------------------------------------------------------


class TestListProgramReports:
    def test_returns_list_with_recording_count(self):
        row = _list_report_row(recording_count=3)
        session = FakeSession(execute_rows=[row])
        result = reporting_router.list_program_reports(PROG_ID, MEDICAL, session)
        assert len(result) == 1
        assert result[0].recording_count == 3

    def test_returns_empty_list_when_no_reports(self):
        session = FakeSession(execute_rows=[])
        result = reporting_router.list_program_reports(PROG_ID, MEDICAL, session)
        assert result == []

    def test_technician_returns_403(self):
        with pytest.raises(HTTPException) as exc:
            reporting_router.list_program_reports(PROG_ID, TECHNICIAN, FakeSession())
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Phase 5.3: GET /reports/{report_id}
# ---------------------------------------------------------------------------


class TestGetReportDetail:
    def test_full_detail_with_recordings(self):
        report = _report_obj()
        detail_row = _detail_recording_row(include_metrics=True, include_insight=True)
        # scalar() for report header; execute() for the flat join
        session = FakeSession(scalar_values=[report], execute_rows=[detail_row])
        result = reporting_router.get_report_detail(REPORT_ID, MEDICAL, session)
        assert result.exercise_report_id == REPORT_ID
        assert len(result.recordings) == 1
        assert result.recordings[0].insight_text == "Good phonation"
        assert result.recordings[0].metrics_status == "success"

    def test_null_metrics_and_insight_still_returns_recording(self):
        report = _report_obj()
        detail_row = _detail_recording_row(include_metrics=False, include_insight=False)
        session = FakeSession(scalar_values=[report], execute_rows=[detail_row])
        result = reporting_router.get_report_detail(REPORT_ID, MEDICAL, session)
        assert result.recordings[0].metrics_status is None
        assert result.recordings[0].raw_json is None
        assert result.recordings[0].insight_text is None

    def test_report_not_found_returns_404(self):
        session = FakeSession(scalar_values=[None])
        with pytest.raises(HTTPException) as exc:
            reporting_router.get_report_detail(uuid.uuid4(), MEDICAL, session)
        assert exc.value.status_code == 404

    def test_technician_returns_403(self):
        with pytest.raises(HTTPException) as exc:
            reporting_router.get_report_detail(REPORT_ID, TECHNICIAN, FakeSession())
        assert exc.value.status_code == 403
