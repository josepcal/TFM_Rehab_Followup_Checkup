"""RGPD consent service and recording guard dependency (UC-05)."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinical.models import AppUser, Patient, PatientConsent, ProgramExercise


class ConsentNotFoundError(HTTPException):
    """Raised by withdraw() when no active consent row exists for the patient+program pair."""

    def __init__(self, program_id: uuid.UUID):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no active consent found for program {program_id}",
        )


class ConsentService:
    """Thin service for RGPD consent lifecycle on clinical.patient_consent (append-only)."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_patient_id(self) -> uuid.UUID:
        """Derive the patient_id from the JWT identity stored in db.info."""
        identity_id_raw = self.db.info.get("identity_id")
        if identity_id_raw is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="authenticated user identity not found",
            )
        identity_id = uuid.UUID(str(identity_id_raw))

        # Resolve AppUser → Patient (matches pattern in followup/router.py)
        app_user = self.db.scalar(
            select(AppUser).where(AppUser.identity_id == identity_id)
        )
        if app_user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="app_user not found for identity",
            )

        patient = self.db.scalar(
            select(Patient).where(Patient.identity_id == app_user.identity_id)
        )
        if patient is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="patient not found for identity",
            )

        return patient.id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_active(self, patient_id: uuid.UUID, program_id: uuid.UUID) -> PatientConsent | None:
        """Return the current consent row **only if it is active**, else None.

        The table is an append-only trail with no UNIQUE constraint (migration 0012
        drops it), so a (patient, programme) pair may hold several rows. The current
        state is the MOST RECENT row. Filtering by `withdrawn_at IS NULL` *before*
        ordering would return an older, orphaned active row and mask a subsequent
        withdrawal — so order first, then check whether that latest row is active.
        """
        latest = self.db.scalar(
            select(PatientConsent)
            .where(
                PatientConsent.patient_id == patient_id,
                PatientConsent.rehab_program_id == program_id,
            )
            .order_by(PatientConsent.granted_at.desc())
            .limit(1)
        )
        return latest if latest is not None and latest.withdrawn_at is None else None

    def get_status(self, program_id: uuid.UUID) -> PatientConsent | None:
        """Return the most recent consent row regardless of withdrawn_at, or None."""
        patient_id = self._resolve_patient_id()
        return self.db.scalar(
            select(PatientConsent)
            .where(
                PatientConsent.patient_id == patient_id,
                PatientConsent.rehab_program_id == program_id,
            )
            .order_by(PatientConsent.granted_at.desc())
            .limit(1)
        )

    def grant(self, program_id: uuid.UUID, consent_text: str) -> PatientConsent:
        """Always INSERT a new consent row — append-only for RGPD audit trail."""
        patient_id = self._resolve_patient_id()
        row = PatientConsent(
            patient_id=patient_id,
            rehab_program_id=program_id,
            granted=True,
            withdrawn_at=None,
            consent_text=consent_text,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def withdraw(self, program_id: uuid.UUID) -> PatientConsent:
        """SET withdrawn_at=now() on **every** active row for this patient+programme.

        The table has no UNIQUE constraint, so duplicate grants (double click, network
        retry) can leave several active rows. Withdrawing only the most recent one would
        leave orphaned active rows behind, and any "is there an active row?" check would
        then still see consent after the patient revoked it (RGPD art. 7.3). The patient
        said no — every open grant is closed, with a single shared timestamp.

        Returns the most recent of the rows just withdrawn.
        Raises ConsentNotFoundError (HTTP 404) if no active row exists.
        """
        patient_id = self._resolve_patient_id()
        rows = list(
            self.db.scalars(
                select(PatientConsent)
                .where(
                    PatientConsent.patient_id == patient_id,
                    PatientConsent.rehab_program_id == program_id,
                    PatientConsent.withdrawn_at.is_(None),
                )
                .order_by(PatientConsent.granted_at.desc())
            )
        )
        if not rows:
            raise ConsentNotFoundError(program_id)

        withdrawn_at = datetime.now(timezone.utc)
        for row in rows:
            row.withdrawn_at = withdrawn_at
        self.db.flush()
        return rows[0]


# ---------------------------------------------------------------------------
# Guard helper — guards recording WRITE paths (UC-05 §3.3)
# ---------------------------------------------------------------------------


def require_active_consent(
    program_exercise_id: uuid.UUID,
    db: Session,
    principal: dict,
) -> None:
    """Called inline in recording write handlers.

    Resolves program_id from program_exercise_id via a single DB query,
    then checks active consent for the authenticated patient.

    Medical staff are exempt — consent is the patient's own act.
    Patients without an active consent row receive HTTP 403 CONSENT_REQUIRED.
    """
    if principal.get("role") == "medical":
        return  # Medical staff bypass the consent gate

    # Resolve program_id from program_exercise_id
    pe = db.scalar(
        select(ProgramExercise).where(ProgramExercise.id == program_exercise_id)
    )
    if pe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "program exercise not found")

    program_id = pe.program_id

    # Resolve patient_id from session identity and check active consent
    svc = ConsentService(db)
    patient_id = svc._resolve_patient_id()

    active = svc.get_active(patient_id, program_id)
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "CONSENT_REQUIRED", "program_id": str(program_id)},
        )
