from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select

from app.clinical.models import AppUser, Diagnostic, Doctor, Patient, ProgramExercise, RehabProgram


class ProgramExerciseAccessService:
    """Clinical service boundary for UC-05 program-exercise authorization."""

    def __init__(self, db):
        self.db = db

    def require_access(self, program_exercise_id: UUID, principal: dict) -> UUID:
        role = principal["role"]
        subject = principal["sub"]
        statement = (
            select(ProgramExercise.id)
            .join(RehabProgram, ProgramExercise.program_id == RehabProgram.id)
            .join(Diagnostic, RehabProgram.diagnostic_id == Diagnostic.id)
            .where(ProgramExercise.id == program_exercise_id)
        )

        if role == "patient":
            statement = (
                statement
                .join(Patient, Diagnostic.patient_id == Patient.id)
                .join(AppUser, Patient.identity_id == AppUser.identity_id)
                .where(AppUser.external_subject == subject)
            )
        elif role == "medical":
            statement = (
                statement
                .join(Doctor, or_(Diagnostic.doctor_id == Doctor.id, RehabProgram.physiotherapist_id == Doctor.id))
                .join(AppUser, Doctor.identity_id == AppUser.identity_id)
                .where(AppUser.external_subject == subject)
            )
        else:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "role not authorized for recordings")

        authorized_id = self.db.scalar(statement)
        if authorized_id is None:
            # Do not reveal whether another patient's exercise exists.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "program exercise not found")
        return authorized_id


class ProgramAccessService:
    """Clinical service boundary for rehab-program authorization.

    Reports and follow-up check-ups hang off ``rehab_program_id``, so access to
    them is decided by the caller's link to the program itself:

    - patient → the program treats them
    - medical → they diagnosed the case, or are its assigned physiotherapist

    RLS does not enforce this for medical roles: the staff policies on
    ``exercise_report`` and ``followup_checkup`` are ``USING (true)``. This
    guard is therefore the only control keeping one doctor out of another
    doctor's patients.
    """

    def __init__(self, db):
        self.db = db

    def require_access(self, program_id: UUID, principal: dict) -> UUID:
        role = principal["role"]
        subject = principal["sub"]
        statement = (
            select(RehabProgram.id)
            .join(Diagnostic, RehabProgram.diagnostic_id == Diagnostic.id)
            .where(RehabProgram.id == program_id)
        )

        if role == "patient":
            statement = (
                statement
                .join(Patient, Diagnostic.patient_id == Patient.id)
                .join(AppUser, Patient.identity_id == AppUser.identity_id)
                .where(AppUser.external_subject == subject)
            )
        elif role == "medical":
            statement = (
                statement
                .join(Doctor, or_(Diagnostic.doctor_id == Doctor.id, RehabProgram.physiotherapist_id == Doctor.id))
                .join(AppUser, Doctor.identity_id == AppUser.identity_id)
                .where(AppUser.external_subject == subject)
            )
        else:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "role not authorized for rehab programs")

        authorized_id = self.db.scalar(statement)
        if authorized_id is None:
            # Do not reveal whether another patient's program exists.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "rehab program not found")
        return authorized_id

    def require_access_via_program_exercise(self, program_exercise_id: UUID, principal: dict) -> UUID:
        """Same check, entered from a program_exercise_id (report creation)."""
        program_id = self.db.scalar(
            select(ProgramExercise.program_id).where(ProgramExercise.id == program_exercise_id)
        )
        if program_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "program_exercise not found")
        return self.require_access(program_id, principal)
