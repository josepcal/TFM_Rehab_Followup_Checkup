from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select

from app.clinical.diagnostic_domain import DiagnosticRecord
from app.clinical.models import AppUser, Diagnostic, Doctor, Patient
from app.clinical.validation import check_diagnostic_authorized


class PostgresDiagnosticRepository:
    """PostgreSQL adapter for doctor diagnostic use cases."""

    def __init__(self, db):
        self.db = db

    def create_diagnostic(
        self,
        patient_id: UUID,
        dolencia: str,
        descripcion: str | None,
        doctor_subject: str,
    ) -> DiagnosticRecord:
        patient = self.db.scalar(select(Patient).where(Patient.id == patient_id))
        if not patient:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")

        doctor = self._doctor_by_subject(doctor_subject)
        if not doctor:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Doctor not assigned to this patient")

        diagnostic = Diagnostic(
            id=uuid4(),
            patient_id=patient_id,
            doctor_id=doctor.id,
            dolencia=dolencia,
            descripcion=descripcion,
            signature=f"unsigned:{uuid4()}",
        )
        self.db.add(diagnostic)
        self.db.flush()
        return self._diagnostic_record(diagnostic)

    def list_diagnostics(self, limit: int, offset: int, doctor_subject: str) -> tuple[list[DiagnosticRecord], int]:
        doctor = self._doctor_by_subject(doctor_subject)
        if not doctor:
            return [], 0

        total_q = select(func.count()).select_from(Diagnostic).where(Diagnostic.doctor_id == doctor.id)
        total = self.db.scalar(total_q) or 0

        diagnostics_q = (
            select(Diagnostic)
            .where(Diagnostic.doctor_id == doctor.id)
            .order_by(Diagnostic.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        diagnostics = self.db.scalars(diagnostics_q).all()
        return [self._diagnostic_record(diagnostic) for diagnostic in diagnostics], total

    def get_diagnostic(self, diagnostic_id: UUID, doctor_subject: str) -> DiagnosticRecord:
        diagnostic = check_diagnostic_authorized(diagnostic_id, doctor_subject, self.db)
        return self._diagnostic_record(diagnostic)

    def update_diagnostic(
        self,
        diagnostic_id: UUID,
        dolencia: str | None,
        descripcion: str | None,
        doctor_subject: str,
    ) -> DiagnosticRecord:
        diagnostic = check_diagnostic_authorized(diagnostic_id, doctor_subject, self.db)
        if dolencia is not None:
            diagnostic.dolencia = dolencia
        if descripcion is not None:
            diagnostic.descripcion = descripcion
        self.db.add(diagnostic)
        self.db.flush()
        return self._diagnostic_record(diagnostic)

    def _doctor_by_subject(self, doctor_subject: str) -> Doctor | None:
        return self.db.scalar(
            select(Doctor)
            .join(AppUser, Doctor.identity_id == AppUser.identity_id)
            .where(AppUser.external_subject == doctor_subject)
        )

    @staticmethod
    def _diagnostic_record(diagnostic: Diagnostic) -> DiagnosticRecord:
        return DiagnosticRecord(
            id=diagnostic.id,
            patient_id=diagnostic.patient_id,
            doctor_id=diagnostic.doctor_id,
            dolencia=diagnostic.dolencia,
            descripcion=diagnostic.descripcion,
            signature=diagnostic.signature,
            signed_at=diagnostic.signed_at,
            created_at=diagnostic.created_at,
            updated_at=diagnostic.updated_at,
        )
