from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select

from app.clinical.attestation import attest_diagnostic
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
        history: str | None,
        symptoms: str | None,
        doctor_subject: str,
    ) -> DiagnosticRecord:
        patient = self.db.scalar(select(Patient).where(Patient.id == patient_id))
        if not patient:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")

        doctor = self._doctor_by_subject(doctor_subject)
        if not doctor:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Doctor not assigned to this patient")

        attestation = attest_diagnostic(
            patient_id=patient_id,
            doctor_id=doctor.id,
            doctor_subject=doctor_subject,
            colegiado_id=doctor.colegiado_id,
            dolencia=dolencia,
            descripcion=descripcion,
            history=history,
            symptoms=symptoms,
        )
        diagnostic = Diagnostic(
            id=uuid4(),
            patient_id=patient_id,
            doctor_id=doctor.id,
            dolencia=dolencia,
            descripcion=descripcion,
            history=history,
            symptoms=symptoms,
            signature=attestation.signature,
            signed_at=attestation.signed_at,
            content_hash=attestation.content_hash,
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
        history: str | None,
        symptoms: str | None,
        doctor_subject: str,
    ) -> DiagnosticRecord:
        diagnostic = check_diagnostic_authorized(diagnostic_id, doctor_subject, self.db)
        if dolencia is not None:
            diagnostic.dolencia = dolencia
        if descripcion is not None:
            diagnostic.descripcion = descripcion
        if history is not None:
            diagnostic.history = history
        if symptoms is not None:
            diagnostic.symptoms = symptoms
        attestation = attest_diagnostic(
            patient_id=diagnostic.patient_id,
            doctor_id=diagnostic.doctor_id,
            doctor_subject=doctor_subject,
            colegiado_id=self._doctor_by_subject(doctor_subject).colegiado_id,
            dolencia=diagnostic.dolencia,
            descripcion=diagnostic.descripcion,
            history=diagnostic.history,
            symptoms=diagnostic.symptoms,
        )
        diagnostic.signature = attestation.signature
        diagnostic.signed_at = attestation.signed_at
        diagnostic.content_hash = attestation.content_hash
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
            history=diagnostic.history,
            symptoms=diagnostic.symptoms,
            signature=diagnostic.signature,
            signed_at=diagnostic.signed_at,
            content_hash=diagnostic.content_hash,
            created_at=diagnostic.created_at,
            updated_at=diagnostic.updated_at,
        )
