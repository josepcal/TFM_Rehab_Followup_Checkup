"""Reporting endpoints: exercise reports (UC-07 / UC-08, D14).

Authorization model — two layers, both required:

1. ``require_role`` gates the endpoint by role (medical / patient).
2. ``ProgramAccessService.require_access`` gates the *object*: the caller must
   be linked to the report's rehab program (the patient it treats, the doctor
   who diagnosed it, or its assigned physiotherapist).

Layer 2 is not optional. RLS filters rows for patients, but the staff policies
on ``exercise_report`` are ``USING (true)``, so without this guard any
authenticated doctor could read and modify another doctor's reports (BOLA).

- POST /reports              → medical, linked to the program
- GET /programs/.../reports  → medical, patient, linked to the program
- GET /reports/{id}          → medical, patient, linked to the program
- PATCH/DELETE /reports/{id} → medical, linked to the program
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.auth import audit_read, require_role
from app.catalog.models import RehabExercise
from app.clinical.doctor_identity_service import DoctorIdentityService
from app.clinical.models import Doctor, ProgramExercise
from app.clinical.program_access_service import ProgramAccessService
from app.db import get_db
from app.metrics.models import MetricResult
from app.recording.models import ExerciseRecording
from app.reporting.models import AiInsight, ExerciseReport, ExerciseReportRecording
from app.reporting.schemas import (
    RecordingInsightOut,
    ReportCreatedOut,
    ReportDetailOut,
    ReportIn,
    ReportListItem,
    ReportPatchIn,
)

router = APIRouter(tags=["reporting"])


# ---------------------------------------------------------------------------
# POST /reports
# ---------------------------------------------------------------------------


@router.post("/reports", response_model=ReportCreatedOut, status_code=status.HTTP_201_CREATED)
def create_report(
    body: ReportIn,
    principal: dict = Depends(require_role("medical")),
    db=Depends(get_db),
) -> ReportCreatedOut:
    """Create an exercise report and link recordings (UC-07 REQ-2)."""
    # 1. Resolve program_exercise → rehab_program_id, rejecting unlinked doctors
    ProgramAccessService(db).require_access_via_program_exercise(
        body.program_exercise_id, principal
    )
    pe = db.scalar(
        select(ProgramExercise).where(ProgramExercise.id == body.program_exercise_id)
    )
    if pe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "program_exercise not found")

    # 2. Verify every recording exists; abort atomically on first missing
    for rec_id in body.recording_ids:
        rec = db.scalar(
            select(ExerciseRecording).where(ExerciseRecording.recording_id == rec_id)
        )
        if rec is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"recording {rec_id} not found"
            )

    # 3. Resolve doctor_id from the authenticated identity_id
    doctor_id = DoctorIdentityService(db).current_doctor_id()

    report = ExerciseReport(
        rehab_program_id=pe.program_id,
        program_exercise_id=body.program_exercise_id,
        period_start=body.period_start,
        period_end=body.period_end,
        summary=body.summary,
        created_by=doctor_id,
    )
    db.add(report)
    db.flush()  # materialise exercise_report_id from server_default

    # 4. Bulk-insert junction rows (one per recording)
    for rec_id in body.recording_ids:
        db.add(
            ExerciseReportRecording(
                exercise_report_id=report.exercise_report_id,
                recording_id=rec_id,
            )
        )

    return ReportCreatedOut(exercise_report_id=report.exercise_report_id)


# ---------------------------------------------------------------------------
# GET /programs/{program_id}/reports
# ---------------------------------------------------------------------------


@router.get(
    "/programs/{program_id}/reports",
    response_model=list[ReportListItem],
    dependencies=[Depends(audit_read)],
)
def list_program_reports(
    program_id: uuid.UUID,
    principal: dict = Depends(require_role("medical", "patient")),
    db=Depends(get_db),
) -> list[ReportListItem]:
    """List exercise reports for a rehabilitation program (UC-07 REQ-3).

    Returns a flat list where each row already carries ``recording_count``.
    """
    ProgramAccessService(db).require_access(program_id, principal)

    # Aggregate query: one row per report with linked recording count,
    # doctor name, and exercise metadata.
    stmt = (
        select(
            ExerciseReport.exercise_report_id,
            ExerciseReport.program_exercise_id,
            ExerciseReport.period_start,
            ExerciseReport.period_end,
            ExerciseReport.summary,
            ExerciseReport.created_by,
            ExerciseReport.attested_at,
            func.count(ExerciseReportRecording.recording_id).label("recording_count"),
            (func.coalesce(Doctor.nombre, "") + " " + func.coalesce(Doctor.apellidos, "")).label("created_by_name"),
            RehabExercise.id.label("exercise_id"),
            RehabExercise.nombre.label("exercise_name"),
        )
        .outerjoin(
            ExerciseReportRecording,
            ExerciseReportRecording.exercise_report_id
            == ExerciseReport.exercise_report_id,
        )
        .outerjoin(Doctor, Doctor.id == ExerciseReport.created_by)
        .outerjoin(ProgramExercise, ProgramExercise.id == ExerciseReport.program_exercise_id)
        .outerjoin(RehabExercise, RehabExercise.id == ProgramExercise.exercise_id)
        .where(ExerciseReport.rehab_program_id == program_id)
        .group_by(
            ExerciseReport.exercise_report_id,
            Doctor.nombre,
            Doctor.apellidos,
            RehabExercise.id,
            RehabExercise.nombre,
        )
    )

    rows = db.execute(stmt).all()
    return [
        ReportListItem(
            exercise_report_id=row.exercise_report_id,
            program_exercise_id=row.program_exercise_id,
            period_start=row.period_start,
            period_end=row.period_end,
            summary=row.summary,
            created_by=row.created_by,
            created_by_name=(row.created_by_name or "").strip() or None,
            attested_at=row.attested_at,
            recording_count=row.recording_count,
            exercise_id=row.exercise_id,
            exercise_name=row.exercise_name,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# PATCH /reports/{report_id}
# ---------------------------------------------------------------------------


@router.patch("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_report(
    report_id: uuid.UUID,
    body: ReportPatchIn,
    principal: dict = Depends(require_role("medical")),
    db=Depends(get_db),
) -> None:
    """Update mutable fields of an exercise report (summary)."""
    report = _require_authorized_report(report_id, principal, db)

    if body.summary is not None:
        report.summary = body.summary


# ---------------------------------------------------------------------------
# DELETE /reports/{report_id}
# ---------------------------------------------------------------------------


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    report_id: uuid.UUID,
    principal: dict = Depends(require_role("medical")),
    db=Depends(get_db),
) -> None:
    """Hard-delete an exercise report (UC-17). Junction rows removed by DB cascade."""
    db.delete(_require_authorized_report(report_id, principal, db))


# ---------------------------------------------------------------------------
# GET /reports/{report_id}
# ---------------------------------------------------------------------------


@router.get(
    "/reports/{report_id}",
    response_model=ReportDetailOut,
    dependencies=[Depends(audit_read)],
)
def get_report_detail(
    report_id: uuid.UUID,
    principal: dict = Depends(require_role("medical", "patient")),
    db=Depends(get_db),
) -> ReportDetailOut:
    """Return full detail for one exercise report (UC-08 REQ-4).

    Includes per-recording metrics (status, raw_json) and AI insight text.
    Missing metrics or insight are represented as null fields.
    """
    report = _require_authorized_report(report_id, principal, db)

    # Flat join: linked recordings + optional metrics + optional insight
    stmt = (
        select(
            ExerciseRecording.recording_id,
            ExerciseRecording.recording_date,
            ExerciseRecording.duration_seconds,
            ExerciseRecording.media_status,
            MetricResult.status.label("metrics_status"),
            MetricResult.raw_json,
            AiInsight.insight_text,
            AiInsight.model_used,
        )
        .join(
            ExerciseReportRecording,
            ExerciseReportRecording.recording_id == ExerciseRecording.recording_id,
        )
        .outerjoin(
            MetricResult,
            MetricResult.recording_id == ExerciseRecording.recording_id,
        )
        .outerjoin(
            AiInsight,
            AiInsight.result_id == MetricResult.result_id,
        )
        .where(ExerciseReportRecording.exercise_report_id == report_id)
    )

    detail_rows = db.execute(stmt).all()

    recordings = [
        RecordingInsightOut(
            recording_id=row.recording_id,
            recording_date=row.recording_date,
            duration_seconds=row.duration_seconds,
            media_status=str(row.media_status),
            metrics_status=str(row.metrics_status) if row.metrics_status else None,
            raw_json=row.raw_json,
            insight_text=row.insight_text,
            model_used=row.model_used,
        )
        for row in detail_rows
    ]

    return ReportDetailOut(
        exercise_report_id=report.exercise_report_id,
        program_exercise_id=report.program_exercise_id,
        period_start=report.period_start,
        period_end=report.period_end,
        summary=report.summary,
        created_by=report.created_by,
        attested_at=report.attested_at,
        recordings=recordings,
    )


def _require_authorized_report(report_id: uuid.UUID, principal: dict, db) -> ExerciseReport:
    """Load a report only if the caller is linked to its rehab program.

    A missing report and an unauthorized one both yield 404, so the response
    does not reveal that another doctor's report exists.
    """
    report = db.scalar(
        select(ExerciseReport).where(ExerciseReport.exercise_report_id == report_id)
    )
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    ProgramAccessService(db).require_access(report.rehab_program_id, principal)
    return report
