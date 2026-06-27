"""Follow-up checkup endpoints (UC-09, FR-07, AC-14).

Authorization model:
- POST /followup-checkups                         → medical only
- GET /programs/{program_id}/followup-checkups    → medical, patient (RLS filters rows)
- GET /followup-checkups/{id}                     → medical, patient (RLS filters rows)
- PATCH /followup-checkups/{id}                   → medical only
- DELETE /followup-checkups/{id}                  → medical only
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.auth import require_role
from app.clinical.models import Diagnostic, Doctor, RehabProgram
from app.db import get_db
from app.followup.models import FollowupCheckup, FollowupCheckupReport
from app.followup.schemas import (
    CheckupCreatedOut,
    CheckupDetailOut,
    CheckupIn,
    CheckupListItem,
    CheckupPatchIn,
    LinkedReportItem,
)
from app.reporting.models import ExerciseReport

router = APIRouter(tags=["followup"])


# ---------------------------------------------------------------------------
# POST /followup-checkups
# ---------------------------------------------------------------------------


@router.post(
    "/followup-checkups",
    response_model=CheckupCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
def create_checkup(
    body: CheckupIn,
    principal: dict = Depends(require_role("medical")),
    db=Depends(get_db),
) -> CheckupCreatedOut:
    """Create a follow-up check-up and link exercise reports (UC-09)."""
    _require_medical(principal)

    # 1. Resolve rehab program → 404 if not found
    program = db.scalar(
        select(RehabProgram).where(RehabProgram.id == body.rehab_program_id)
    )
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rehab_program not found")

    # 2. Derive patient_id: program.diagnostic_id → Diagnostic.patient_id
    diagnostic = db.scalar(
        select(Diagnostic).where(Diagnostic.id == program.diagnostic_id)
    )
    if diagnostic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "diagnostic not found for program")
    patient_id = diagnostic.patient_id

    # 3. Resolve created_by from authenticated identity_id
    identity_id_raw = db.info.get("identity_id")
    doctor_id = None
    if identity_id_raw is not None:
        doctor = db.scalar(
            select(Doctor).where(
                Doctor.identity_id == uuid.UUID(str(identity_id_raw))
            )
        )
        doctor_id = doctor.id if doctor is not None else None

    # 4. Cross-program validation: all reports must belong to this program
    for report_id in body.exercise_report_ids:
        report = db.scalar(
            select(ExerciseReport).where(
                ExerciseReport.exercise_report_id == report_id
            )
        )
        if report is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"exercise_report {report_id} not found",
            )
        if report.rehab_program_id != body.rehab_program_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"exercise_report {report_id} does not belong to rehab_program {body.rehab_program_id}",
            )

    # 5. Insert FollowupCheckup
    checkup = FollowupCheckup(
        rehab_program_id=body.rehab_program_id,
        patient_id=patient_id,
        period_start=body.period_start,
        period_end=body.period_end,
        summary=body.summary,
        created_by=doctor_id,
    )
    db.add(checkup)
    db.flush()  # materialise followup_checkup_id from server_default

    # 6. Bulk-insert link rows
    for report_id in body.exercise_report_ids:
        db.add(
            FollowupCheckupReport(
                followup_checkup_id=checkup.followup_checkup_id,
                exercise_report_id=report_id,
            )
        )

    return CheckupCreatedOut(followup_checkup_id=checkup.followup_checkup_id)


# ---------------------------------------------------------------------------
# GET /programs/{program_id}/followup-checkups
# ---------------------------------------------------------------------------


@router.get(
    "/programs/{program_id}/followup-checkups",
    response_model=list[CheckupListItem],
)
def list_program_checkups(
    program_id: uuid.UUID,
    principal: dict = Depends(require_role("medical", "patient")),
    db=Depends(get_db),
) -> list[CheckupListItem]:
    """List follow-up check-ups for a rehabilitation program (UC-09).

    Returns a flat list where each row already carries ``report_count``.
    RLS handles cross-tenant filtering transparently.
    """
    _require_not_technician(principal)

    stmt = (
        select(
            FollowupCheckup.followup_checkup_id,
            FollowupCheckup.rehab_program_id,
            FollowupCheckup.period_start,
            FollowupCheckup.period_end,
            FollowupCheckup.summary,
            FollowupCheckup.created_by,
            func.count(FollowupCheckupReport.exercise_report_id).label("report_count"),
            (
                func.coalesce(Doctor.nombre, "") + " " + func.coalesce(Doctor.apellidos, "")
            ).label("created_by_name"),
        )
        .outerjoin(
            FollowupCheckupReport,
            FollowupCheckupReport.followup_checkup_id
            == FollowupCheckup.followup_checkup_id,
        )
        .outerjoin(Doctor, Doctor.id == FollowupCheckup.created_by)
        .where(FollowupCheckup.rehab_program_id == program_id)
        .group_by(
            FollowupCheckup.followup_checkup_id,
            Doctor.nombre,
            Doctor.apellidos,
        )
    )

    rows = db.execute(stmt).all()
    return [
        CheckupListItem(
            followup_checkup_id=row.followup_checkup_id,
            rehab_program_id=row.rehab_program_id,
            period_start=row.period_start,
            period_end=row.period_end,
            summary=row.summary,
            created_by=row.created_by,
            created_by_name=(row.created_by_name or "").strip() or None,
            report_count=row.report_count,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /followup-checkups/{followup_checkup_id}
# ---------------------------------------------------------------------------


@router.get(
    "/followup-checkups/{followup_checkup_id}",
    response_model=CheckupDetailOut,
)
def get_checkup_detail(
    followup_checkup_id: uuid.UUID,
    principal: dict = Depends(require_role("medical", "patient")),
    db=Depends(get_db),
) -> CheckupDetailOut:
    """Return full detail for one follow-up check-up (UC-09).

    Includes embedded linked exercise report metadata.
    RLS hides unauthorised rows → None → 404.
    """
    _require_not_technician(principal)

    checkup = db.scalar(
        select(FollowupCheckup).where(
            FollowupCheckup.followup_checkup_id == followup_checkup_id
        )
    )
    if checkup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "followup_checkup not found")

    # Fetch linked exercise reports
    linked_reports = db.scalars(
        select(ExerciseReport)
        .join(
            FollowupCheckupReport,
            FollowupCheckupReport.exercise_report_id == ExerciseReport.exercise_report_id,
        )
        .where(
            FollowupCheckupReport.followup_checkup_id == followup_checkup_id
        )
    ).all()

    reports = [
        LinkedReportItem(
            exercise_report_id=r.exercise_report_id,
            period_start=r.period_start,
            period_end=r.period_end,
            summary=r.summary,
        )
        for r in linked_reports
    ]

    return CheckupDetailOut(
        followup_checkup_id=checkup.followup_checkup_id,
        rehab_program_id=checkup.rehab_program_id,
        period_start=checkup.period_start,
        period_end=checkup.period_end,
        summary=checkup.summary,
        created_by=checkup.created_by,
        reports=reports,
    )


# ---------------------------------------------------------------------------
# PATCH /followup-checkups/{followup_checkup_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/followup-checkups/{followup_checkup_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def update_checkup(
    followup_checkup_id: uuid.UUID,
    body: CheckupPatchIn,
    principal: dict = Depends(require_role("medical")),
    db=Depends(get_db),
) -> None:
    """Update the summary of a follow-up check-up (UC-09)."""
    _require_medical(principal)

    checkup = db.scalar(
        select(FollowupCheckup).where(
            FollowupCheckup.followup_checkup_id == followup_checkup_id
        )
    )
    if checkup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "followup_checkup not found")

    checkup.summary = body.summary


# ---------------------------------------------------------------------------
# DELETE /followup-checkups/{followup_checkup_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/followup-checkups/{followup_checkup_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_checkup(
    followup_checkup_id: uuid.UUID,
    principal: dict = Depends(require_role("medical")),
    db=Depends(get_db),
) -> None:
    """Delete a follow-up check-up (UC-09). Junction rows removed by DB cascade."""
    _require_medical(principal)

    checkup = db.scalar(
        select(FollowupCheckup).where(
            FollowupCheckup.followup_checkup_id == followup_checkup_id
        )
    )
    if checkup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "followup_checkup not found")

    db.delete(checkup)


# ---------------------------------------------------------------------------
# Private guards
# ---------------------------------------------------------------------------


def _require_medical(principal: dict) -> None:
    if principal.get("role") != "medical":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "medical role required")


def _require_not_technician(principal: dict) -> None:
    if principal.get("role") == "technician":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "technicians cannot access follow-up checkups"
        )
