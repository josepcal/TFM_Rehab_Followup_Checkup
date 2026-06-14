from typing import Protocol
from uuid import UUID

from app.clinical.program_domain import ProgramExerciseRecord, ProgramRecord


class ProgramRepository(Protocol):
    def create_program(self, diagnostic_id: UUID, estado: str | None, doctor_subject: str) -> ProgramRecord:
        ...

    def list_programs(self, diagnostic_id: UUID, limit: int, offset: int, doctor_subject: str) -> tuple[list[ProgramRecord], int]:
        ...

    def get_program(self, program_id: UUID, doctor_subject: str) -> ProgramRecord:
        ...

    def assign_exercise(
        self,
        program_id: UUID,
        exercise_id: UUID,
        pauta: str | None,
        doctor_subject: str,
    ) -> ProgramExerciseRecord:
        ...
