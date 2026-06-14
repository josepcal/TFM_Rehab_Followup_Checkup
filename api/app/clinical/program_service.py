from uuid import UUID

from app.clinical.ports import ProgramRepository
from app.clinical.schemas import (
    ListQuery,
    PaginatedResponse,
    ProgramExerciseIn,
    ProgramExerciseOut,
    ProgramIn,
    ProgramOut,
)
from app.clinical.validation import parse_pagination


class ProgramService:
    def __init__(self, repository: ProgramRepository):
        self.repository = repository

    def create_program(self, body: ProgramIn, doctor_subject: str) -> ProgramOut:
        program = self.repository.create_program(body.diagnostic_id, body.estado, doctor_subject)
        return self._program_out(program)

    def list_programs(self, diagnostic_id: UUID, query: ListQuery, doctor_subject: str) -> PaginatedResponse[ProgramOut]:
        limit, offset = parse_pagination(query.limit, query.offset)
        programs, total = self.repository.list_programs(diagnostic_id, limit, offset, doctor_subject)
        return PaginatedResponse[ProgramOut](
            data=[self._program_out(program) for program in programs],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_program(self, program_id: UUID, doctor_subject: str) -> ProgramOut:
        program = self.repository.get_program(program_id, doctor_subject)
        return self._program_out(program)

    def assign_exercise(self, program_id: UUID, body: ProgramExerciseIn, doctor_subject: str) -> ProgramExerciseOut:
        assignment = self.repository.assign_exercise(program_id, body.exercise_id, body.pauta, doctor_subject)
        return ProgramExerciseOut(
            id=assignment.id,
            program_id=assignment.program_id,
            exercise_id=assignment.exercise_id,
            pauta=assignment.pauta,
            estado=assignment.estado,
        )

    @staticmethod
    def _program_out(program) -> ProgramOut:
        return ProgramOut(
            id=program.id,
            diagnostic_id=program.diagnostic_id,
            estado=program.estado,
            created_at=program.created_at,
        )
