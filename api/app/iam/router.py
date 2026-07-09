"""IAM router — UC-15 audit log + RGPD data-subject rights (Art. 15 / Art. 17)."""

import logging
import uuid
from datetime import UTC, datetime

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
from app.recording.models import ExerciseRecording
from app.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iam", tags=["iam"])


def _purge_patient_recordings(db: Session, patient_id: uuid.UUID) -> None:
    """Delete every raw WAV of a patient from object storage (RGPD Art. 17 / Art. 9).

    Resolves the patient's recordings through the clinical chain, deletes each media
    object best-effort (a storage failure is logged, not raised — it must not abort
    the surrounding anonymisation), and marks the row as purged.
    """
    recording_ids = db.scalars(
        text(
            """
            SELECT r.recording_id
            FROM recording.exercise_recording r
            JOIN clinical.program_exercise pe ON pe.program_exercise_id = r.program_exercise_id
            JOIN clinical.rehab_program rp     ON rp.rehab_program_id = pe.rehab_program_id
            JOIN clinical.diagnostic d         ON d.diagnostic_id = rp.diagnostic_id
            WHERE d.patient_id = :pid
              AND r.media_uri IS NOT NULL
            """
        ),
        {"pid": str(patient_id)},
    ).all()

    if not recording_ids:
        return

    storage = get_storage()
    for recording_id in recording_ids:
        recording = db.get(ExerciseRecording, recording_id)
        if recording is None or not recording.media_uri:
            continue
        try:
            storage.delete(recording.media_uri)
        except Exception:  # noqa: BLE001 - a storage error must not block erasure
            logger.error("failed to purge WAV for recording %s", recording_id, exc_info=True)
        recording.media_uri = None
        recording.media_status = "purged"
        recording.is_deleted = True
        recording.deleted_at = datetime.now(UTC)


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

    What this does:
    - Overwrites first_name / last_name with '[deleted]' in clinical.patient
    - Sets national_id to NULL
    - Purges every raw WAV of the patient from object storage (biometric data, Art. 9)
      and marks the recording rows as purged
    - Deletes clinical.pseudonym_map (severs the pseudonym↔identity link, which
      makes the retained pseudonymised metrics irreversibly anonymous)
    - Marks clinical.app_user.status = 'deleted'

    What is intentionally deferred (post-MVP):
    - Deactivation of the Keycloak account (requires Admin API credentials)
    - Notification to DPO

    Metrics and reports are retained without any PII link for clinical integrity,
    as permitted by RGPD Art. 17(3)(c) (archiving / research purposes). Once the
    pseudonym_map row is gone they can no longer be tied back to a person.
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

    # Purge raw biometric audio (Art. 9). Best-effort per object: a storage error
    # must not abort the anonymisation — severing the pseudonym link below is what
    # makes the person unidentifiable, and that happens in the same transaction.
    _purge_patient_recordings(db, patient.id)

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
