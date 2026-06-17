from typing import Protocol
from uuid import UUID

from app.clinical.diagnostic_domain import DiagnosticRecord
from app.clinical.program_domain import ProgramExerciseRecord, ProgramRecord


class ProgramRepository(Protocol):
    def create_program(
        self,
        diagnostic_id: UUID,
        estado: str | None,
        doctor_subject: str,
        name: str | None = None,
        start_date=None,
        end_date=None,
        physiotherapist_id: UUID | None = None,
    ) -> ProgramRecord:
        ...

    def list_programs(
        self,
        diagnostic_id: UUID | None,
        patient_id: UUID | None,
        limit: int,
        offset: int,
        doctor_subject: str,
    ) -> tuple[list[ProgramRecord], int]:
        ...

    def get_program(self, program_id: UUID, doctor_subject: str) -> ProgramRecord:
        ...

    def update_program(
        self,
        program_id: UUID,
        doctor_subject: str,
        estado: str | None = None,
        name: str | None = None,
        start_date=None,
        end_date=None,
        physiotherapist_id: UUID | None = None,
    ) -> ProgramRecord:
        ...

    def assign_exercise(
        self,
        program_id: UUID,
        exercise_id: UUID,
        pauta: str | None,
        doctor_subject: str,
    ) -> ProgramExerciseRecord:
        ...

    def list_program_exercises(
        self,
        program_id: UUID,
        limit: int,
        offset: int,
        doctor_subject: str,
    ) -> tuple[list[ProgramExerciseRecord], int]:
        ...


class DiagnosticRepository(Protocol):
    def create_diagnostic(
        self,
        patient_id: UUID,
        dolencia: str,
        descripcion: str | None,
        history: str | None,
        symptoms: str | None,
        doctor_subject: str,
    ) -> DiagnosticRecord:
        ...

    def list_diagnostics(self, limit: int, offset: int, doctor_subject: str) -> tuple[list[DiagnosticRecord], int]:
        ...

    def get_diagnostic(self, diagnostic_id: UUID, doctor_subject: str) -> DiagnosticRecord:
        ...

    def update_diagnostic(
        self,
        diagnostic_id: UUID,
        dolencia: str | None,
        descripcion: str | None,
        history: str | None,
        symptoms: str | None,
        doctor_subject: str,
    ) -> DiagnosticRecord:
        ...
