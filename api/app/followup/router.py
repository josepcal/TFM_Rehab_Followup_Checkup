"""Follow-up checkup endpoints (UC-09, FR-07, AC-14).

Authorization model — two layers, both required:

1. ``require_role`` gates the endpoint by role (medical / patient).
2. ``ProgramAccessService.require_access`` gates the *object*: the caller must
   be linked to the check-up's rehab program (the patient it treats, the doctor
   who diagnosed it, or its assigned physiotherapist).

Layer 2 is not optional. RLS filters rows for patients, but the staff policies
on ``followup_checkup`` are ``USING (true)``, so without this guard any
authenticated doctor could read and modify another doctor's check-ups (BOLA).

- POST /followup-checkups                      → medical, linked to the program
- GET /programs/{id}/followup-checkups         → medical, patient, linked
- GET /followup-checkups/{id}                  → medical, patient, linked
- PATCH/DELETE /followup-checkups/{id}         → medical, linked
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.auth import audit_read, require_role
from app.clinical.doctor_identity_service import DoctorIdentityService
from app.clinical.models import Diagnostic, Doctor, RehabProgram
from app.clinical.program_access_service import ProgramAccessService
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
    # 1. Resolve rehab program → 404 if not found or the doctor is not linked to it
    ProgramAccessService(db).require_access(body.rehab_program_id, principal)
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
    doctor_id = DoctorIdentityService(db).current_doctor_id()

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
    dependencies=[Depends(audit_read)],
)
def list_program_checkups(
    program_id: uuid.UUID,
    principal: dict = Depends(require_role("medical", "patient")),
    db=Depends(get_db),
) -> list[CheckupListItem]:
    """List follow-up check-ups for a rehabilitation program (UC-09).

    Returns a flat list where each row already carries ``report_count``.
    """
    ProgramAccessService(db).require_access(program_id, principal)

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
    dependencies=[Depends(audit_read)],
)
def get_checkup_detail(
    followup_checkup_id: uuid.UUID,
    principal: dict = Depends(require_role("medical", "patient")),
    db=Depends(get_db),
) -> CheckupDetailOut:
    """Return full detail for one follow-up check-up (UC-09).

    Includes embedded linked exercise report metadata.
    """
    checkup = _require_authorized_checkup(followup_checkup_id, principal, db)

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
    _require_authorized_checkup(followup_checkup_id, principal, db).summary = body.summary


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
    db.delete(_require_authorized_checkup(followup_checkup_id, principal, db))


def _require_authorized_checkup(
    followup_checkup_id: uuid.UUID, principal: dict, db
) -> FollowupCheckup:
    """Load a check-up only if the caller is linked to its rehab program.

    A missing check-up and an unauthorized one both yield 404, so the response
    does not reveal that another doctor's check-up exists.
    """
    checkup = db.scalar(
        select(FollowupCheckup).where(
            FollowupCheckup.followup_checkup_id == followup_checkup_id
        )
    )
    if checkup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "followup_checkup not found")
    ProgramAccessService(db).require_access(checkup.rehab_program_id, principal)
    return checkup


