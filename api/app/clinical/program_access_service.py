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
