from uuid import UUID

from app.clinical.ports import DiagnosticRepository
from app.clinical.schemas import (
    DiagnosticIn,
    DiagnosticOut,
    DiagnosticPatchIn,
    ListQuery,
    PaginatedResponse,
)
from app.clinical.validation import parse_pagination


class DiagnosticService:
    def __init__(self, repository: DiagnosticRepository):
        self.repository = repository

    def create_diagnostic(self, body: DiagnosticIn, doctor_subject: str) -> DiagnosticOut:
        diagnostic = self.repository.create_diagnostic(
            body.patient_id,
            body.dolencia,
            body.descripcion,
            doctor_subject,
        )
        return self._diagnostic_out(diagnostic)

    def list_diagnostics(self, query: ListQuery, doctor_subject: str) -> PaginatedResponse[DiagnosticOut]:
        limit, offset = parse_pagination(query.limit, query.offset)
        diagnostics, total = self.repository.list_diagnostics(limit, offset, doctor_subject)
        return PaginatedResponse[DiagnosticOut](
            data=[self._diagnostic_out(diagnostic) for diagnostic in diagnostics],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_diagnostic(self, diagnostic_id: UUID, doctor_subject: str) -> DiagnosticOut:
        return self._diagnostic_out(self.repository.get_diagnostic(diagnostic_id, doctor_subject))

    def update_diagnostic(self, diagnostic_id: UUID, body: DiagnosticPatchIn, doctor_subject: str) -> DiagnosticOut:
        diagnostic = self.repository.update_diagnostic(
            diagnostic_id,
            body.dolencia,
            body.descripcion,
            doctor_subject,
        )
        return self._diagnostic_out(diagnostic)

    @staticmethod
    def _diagnostic_out(diagnostic) -> DiagnosticOut:
        return DiagnosticOut(
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
