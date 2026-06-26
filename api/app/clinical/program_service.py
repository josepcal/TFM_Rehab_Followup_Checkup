from uuid import UUID

from app.clinical.ports import ProgramRepository
from app.clinical.schemas import (
    ListQuery,
    PaginatedResponse,
    ProgramExerciseIn,
    ProgramExerciseOut,
    ProgramIn,
    ProgramOut,
    ProgramPatchIn,
)
from app.clinical.validation import parse_pagination


class ProgramService:
    def __init__(self, repository: ProgramRepository):
        self.repository = repository

    def create_program(self, body: ProgramIn, doctor_subject: str) -> ProgramOut:
        program = self.repository.create_program(
            body.diagnostic_id,
            body.estado,
            doctor_subject,
            name=body.name,
            start_date=body.start_date,
            end_date=body.end_date,
            physiotherapist_id=body.physiotherapist_id,
        )
        return self._program_out(program)

    def list_programs(
        self,
        diagnostic_id: UUID | None,
        patient_id: UUID | None,
        query: ListQuery,
        doctor_subject: str,
    ) -> PaginatedResponse[ProgramOut]:
        limit, offset = parse_pagination(query.limit, query.offset)
        programs, total = self.repository.list_programs(
            diagnostic_id, patient_id, limit, offset, doctor_subject
        )
        return PaginatedResponse[ProgramOut](
            data=[self._program_out(program) for program in programs],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_program(self, program_id: UUID, doctor_subject: str) -> ProgramOut:
        program = self.repository.get_program(program_id, doctor_subject)
        return self._program_out(program)

    def update_program(self, program_id: UUID, body: ProgramPatchIn, doctor_subject: str) -> ProgramOut:
        current = self.repository.get_program(program_id, doctor_subject)
        program = self.repository.update_program(
            program_id,
            doctor_subject,
            estado=body.estado if "estado" in body.model_fields_set else current.estado,
            name=body.name if "name" in body.model_fields_set else current.name,
            start_date=body.start_date if "start_date" in body.model_fields_set else current.start_date,
            end_date=body.end_date if "end_date" in body.model_fields_set else current.end_date,
            physiotherapist_id=(
                body.physiotherapist_id
                if "physiotherapist_id" in body.model_fields_set
                else current.physiotherapist_id
            ),
        )
        return self._program_out(program)

    def assign_exercise(self, program_id: UUID, body: ProgramExerciseIn, doctor_subject: str) -> ProgramExerciseOut:
        assignment = self.repository.assign_exercise(program_id, body.exercise_id, body.pauta, doctor_subject)
        return self._program_exercise_out(assignment)

    def list_program_exercises(
        self,
        program_id: UUID,
        query: ListQuery,
        doctor_subject: str,
    ) -> PaginatedResponse[ProgramExerciseOut]:
        limit, offset = parse_pagination(query.limit, query.offset)
        assignments, total = self.repository.list_program_exercises(
            program_id, limit, offset, doctor_subject
        )
        return PaginatedResponse[ProgramExerciseOut](
            data=[self._program_exercise_out(assignment) for assignment in assignments],
            total=total,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _program_exercise_out(assignment) -> ProgramExerciseOut:
        return ProgramExerciseOut(
            id=assignment.id,
            program_id=assignment.program_id,
            exercise_id=assignment.exercise_id,
            pauta=assignment.pauta,
            estado=assignment.estado,
            created_at=assignment.created_at,
            exercise_type=assignment.exercise_type,
            exercise_description=assignment.exercise_description,
        )

    @staticmethod
    def _program_out(program) -> ProgramOut:
        return ProgramOut(
            id=program.id,
            diagnostic_id=program.diagnostic_id,
            estado=program.estado,
            name=program.name,
            start_date=program.start_date,
            end_date=program.end_date,
            physiotherapist_id=program.physiotherapist_id,
            created_at=program.created_at,
        )
