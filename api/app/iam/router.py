"""IAM router — UC-15 audit log + RGPD data-subject rights (Art. 15 / Art. 17)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth import require_role
from app.clinical.models import (
    AppUser,
    Diagnostic,
    Patient,
    PatientConsent,
    PseudonymMap,
    RehabProgram,
)
from app.db import get_db
from app.iam.models import EventLog
from app.iam.schemas import EventLogEntry, PatientExportOut

router = APIRouter(prefix="/iam", tags=["iam"])


@router.get("/audit-log", response_model=list[EventLogEntry])
def get_audit_log(
    actor_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _principal: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[EventLogEntry]:
    """Return audit log entries ordered by occurred_at descending.

    Restricted to the admin role.
    Requires migration 0013 (GRANT SELECT ON audit.event_log TO ftm_medical_specialist).
    """
    stmt = select(EventLog).order_by(EventLog.occurred_at.desc())

    if actor_id is not None:
        stmt = stmt.where(EventLog.actor_id == actor_id)
    if entity_type is not None:
        stmt = stmt.where(EventLog.entity_type == entity_type)
    if from_ts is not None:
        stmt = stmt.where(EventLog.occurred_at >= from_ts)
    if to_ts is not None:
        stmt = stmt.where(EventLog.occurred_at <= to_ts)

    stmt = stmt.limit(limit).offset(offset)

    rows = db.scalars(stmt).all()
    return [EventLogEntry.model_validate(row) for row in rows]


# ---------------------------------------------------------------------------
# RGPD Art. 15 — Right of access
# ---------------------------------------------------------------------------

@router.get("/patients/me/export", response_model=PatientExportOut)
def export_my_data(
    principal: dict = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> PatientExportOut:
    """Return all personal data held for the authenticated patient (RGPD Art. 15).

    Scope: profile, diagnostics, rehab programs, consents.
    WAV recordings are excluded — biometric data available on supervised request.
    RLS ensures the session only sees the requesting patient's rows.
    """
    identity_id = db.info.get("identity_id")
    if not identity_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "patient identity not resolved")

    patient = db.scalars(
        select(Patient).where(Patient.identity_id == uuid.UUID(str(identity_id)))
    ).first()
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient record not found")

    diagnostics = db.scalars(
        select(Diagnostic).where(Diagnostic.patient_id == patient.id)
    ).all()

    programs = db.scalars(
        select(RehabProgram).join(
            Diagnostic, RehabProgram.diagnostic_id == Diagnostic.id
        ).where(Diagnostic.patient_id == patient.id)
    ).all()

    consents = db.scalars(
        select(PatientConsent).where(PatientConsent.patient_id == patient.id)
    ).all()

    from app.crypto import decrypt_field
    raw = patient._national_id
    national_id_plain = decrypt_field(raw) if raw is not None else None

    return PatientExportOut.build(patient, diagnostics, programs, consents, national_id_plain)


# ---------------------------------------------------------------------------
# RGPD Art. 17 — Right to erasure ("right to be forgotten")
# ---------------------------------------------------------------------------

@router.delete("/patients/me", status_code=status.HTTP_204_NO_CONTENT)
def erase_my_data(
    principal: dict = Depends(require_role("patient")),
    db: Session = Depends(get_db),
) -> None:
    """Anonymise the authenticated patient's personal data (RGPD Art. 17).

    What this stub does:
    - Overwrites first_name / last_name with '[deleted]' in clinical.patient
    - Sets national_id to NULL
    - Deletes clinical.pseudonym_map (severs the pseudonym↔identity link)
    - Marks clinical.app_user.status = 'deleted'

    What is intentionally deferred (post-MVP):
    - Deletion of WAV files from object storage (irreversible, requires supervised process)
    - Deactivation of the Keycloak account (requires Admin API credentials)
    - Notification to DPO

    Recordings, metrics and reports are retained without any PII link for clinical
    integrity, as permitted by RGPD Art. 17(3)(c) (archiving / research purposes).
    """
    identity_id = db.info.get("identity_id")
    if not identity_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "patient identity not resolved")

    patient = db.scalars(
        select(Patient).where(Patient.identity_id == uuid.UUID(str(identity_id)))
    ).first()
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient record not found")

    # Anonymise PII fields
    patient.nombre = "[deleted]"
    patient.apellidos = "[deleted]"
    patient.national_id = None  # type: ignore[assignment]

    # Sever pseudonym↔identity link (makes metrics unresolvable to a person)
    pseudonym = db.scalars(
        select(PseudonymMap).where(PseudonymMap.patient_id == patient.id)
    ).first()
    if pseudonym:
        db.delete(pseudonym)

    # Mark the app_user as deleted
    app_user = db.scalars(
        select(AppUser).where(AppUser.identity_id == uuid.UUID(str(identity_id)))
    ).first()
    if app_user:
        app_user.status = "deleted"

    db.flush()
