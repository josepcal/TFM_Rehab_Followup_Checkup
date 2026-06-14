from uuid import UUID

from sqlalchemy import func, select

from app.clinical.models import ProgramExercise, RehabProgram
from app.clinical.program_domain import ProgramExerciseRecord, ProgramRecord
from app.clinical.validation import (
    check_diagnostic_authorized,
    check_exercise_exists,
    check_program_belongs_to_diagnostic,
)


class PostgresProgramRepository:
    """PostgreSQL adapter for doctor program use cases.

    This is the hexagonal boundary: routers/services use the repository port and
    domain records; SQLAlchemy ORM and SDD/ERD column mapping stay here.
    """

    def __init__(self, db):
        self.db = db

    def create_program(self, diagnostic_id: UUID, estado: str | None, doctor_subject: str) -> ProgramRecord:
        check_diagnostic_authorized(diagnostic_id, doctor_subject, self.db)
        program = RehabProgram(diagnostic_id=diagnostic_id, estado=self._normalize_program_status(estado))
        self.db.add(program)
        self.db.flush()
        return self._program_record(program)

    def list_programs(self, diagnostic_id: UUID, limit: int, offset: int, doctor_subject: str) -> tuple[list[ProgramRecord], int]:
        check_diagnostic_authorized(diagnostic_id, doctor_subject, self.db)

        total_q = select(func.count()).select_from(RehabProgram).where(RehabProgram.diagnostic_id == diagnostic_id)
        total = self.db.scalar(total_q) or 0

        programs_q = (
            select(RehabProgram)
            .where(RehabProgram.diagnostic_id == diagnostic_id)
            .order_by(RehabProgram.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        programs = self.db.scalars(programs_q).all()
        return [self._program_record(program) for program in programs], total

    def get_program(self, program_id: UUID, doctor_subject: str) -> ProgramRecord:
        program = check_program_belongs_to_diagnostic(program_id, None, self.db)
        check_diagnostic_authorized(program.diagnostic_id, doctor_subject, self.db)
        return self._program_record(program)

    def assign_exercise(
        self,
        program_id: UUID,
        exercise_id: UUID,
        pauta: str | None,
        doctor_subject: str,
    ) -> ProgramExerciseRecord:
        program = check_program_belongs_to_diagnostic(program_id, None, self.db)
        check_diagnostic_authorized(program.diagnostic_id, doctor_subject, self.db)
        check_exercise_exists(exercise_id, self.db)

        assignment = ProgramExercise(program_id=program_id, exercise_id=exercise_id, pauta=pauta)
        self.db.add(assignment)
        self.db.flush()
        return self._program_exercise_record(assignment)

    @staticmethod
    def _normalize_program_status(estado: str | None) -> str:
        if estado in (None, "", "activo"):
            return "active"
        return estado

    @staticmethod
    def _program_record(program: RehabProgram) -> ProgramRecord:
        return ProgramRecord(
            id=program.id,
            diagnostic_id=program.diagnostic_id,
            estado=program.estado,
            created_at=program.created_at,
        )

    @staticmethod
    def _program_exercise_record(assignment: ProgramExercise) -> ProgramExerciseRecord:
        return ProgramExerciseRecord(
            id=assignment.id,
            program_id=assignment.program_id,
            exercise_id=assignment.exercise_id,
            pauta=assignment.pauta,
            estado=assignment.estado,
        )
