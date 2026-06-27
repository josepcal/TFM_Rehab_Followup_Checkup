"""Reporting endpoints: exercise reports (UC-07 / UC-08, D14).

Authorization model:
- POST /reports              → medical only
- GET /programs/.../reports  → medical, patient (RLS filters rows)
- GET /reports/{id}          → medical, patient (RLS filters rows)
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text

from app.auth import require_role
from app.clinical.models import ProgramExercise
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
    _require_medical(principal)

    # 1. Resolve program_exercise → rehab_program_id (also validates existence)
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

    # 3. Insert ExerciseReport
    created_by_raw = db.info.get("identity_id")
    report = ExerciseReport(
        rehab_program_id=pe.program_id,
        program_exercise_id=body.program_exercise_id,
        period_start=body.period_start,
        period_end=body.period_end,
        summary=body.summary,
        created_by=uuid.UUID(str(created_by_raw)) if created_by_raw else None,
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


@router.get("/programs/{program_id}/reports", response_model=list[ReportListItem])
def list_program_reports(
    program_id: uuid.UUID,
    principal: dict = Depends(require_role("medical", "patient")),
    db=Depends(get_db),
) -> list[ReportListItem]:
    """List exercise reports for a rehabilitation program (UC-07 REQ-3).

    Returns a flat list where each row already carries ``recording_count``.
    RLS handles cross-tenant filtering transparently.
    """
    _require_not_technician(principal)

    # Aggregate query: one row per report with linked recording count.
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
        )
        .outerjoin(
            ExerciseReportRecording,
            ExerciseReportRecording.exercise_report_id
            == ExerciseReport.exercise_report_id,
        )
        .where(ExerciseReport.rehab_program_id == program_id)
        .group_by(ExerciseReport.exercise_report_id)
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
            attested_at=row.attested_at,
            recording_count=row.recording_count,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /reports/{report_id}
# ---------------------------------------------------------------------------


@router.get("/reports/{report_id}", response_model=ReportDetailOut)
def get_report_detail(
    report_id: uuid.UUID,
    principal: dict = Depends(require_role("medical", "patient")),
    db=Depends(get_db),
) -> ReportDetailOut:
    """Return full detail for one exercise report (UC-08 REQ-4).

    Includes per-recording metrics (status, raw_json) and AI insight text.
    Missing metrics or insight are represented as null fields.
    """
    _require_not_technician(principal)

    # Fetch the report header (RLS will hide unauthorised rows → None → 404)
    report = db.scalar(
        select(ExerciseReport).where(
            ExerciseReport.exercise_report_id == report_id
        )
    )
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")

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


# ---------------------------------------------------------------------------
# Private guards
# ---------------------------------------------------------------------------


def _require_medical(principal: dict) -> None:
    if principal.get("role") != "medical":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "medical role required")


def _require_not_technician(principal: dict) -> None:
    if principal.get("role") == "technician":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "technicians cannot access reports")
