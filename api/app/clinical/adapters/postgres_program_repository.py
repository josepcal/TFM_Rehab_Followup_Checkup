from uuid import UUID

from sqlalchemy import func, select

from app.clinical.models import AppUser, Diagnostic, Doctor, ProgramExercise, RehabProgram
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
        check_diagnostic_authorized(diagnostic_id, doctor_subject, self.db)
        program = RehabProgram(
            diagnostic_id=diagnostic_id,
            estado=self._normalize_program_status(estado),
            name=name,
            start_date=start_date,
            end_date=end_date,
            physiotherapist_id=physiotherapist_id,
        )
        self.db.add(program)
        self.db.flush()
        return self._program_record(program)

    def list_programs(
        self,
        diagnostic_id: UUID | None,
        patient_id: UUID | None,
        limit: int,
        offset: int,
        doctor_subject: str,
    ) -> tuple[list[ProgramRecord], int]:
        filters = [AppUser.external_subject == doctor_subject]
        if diagnostic_id is not None:
            filters.append(RehabProgram.diagnostic_id == diagnostic_id)
        if patient_id is not None:
            filters.append(Diagnostic.patient_id == patient_id)

        total_q = (
            select(func.count())
            .select_from(RehabProgram)
            .join(Diagnostic, RehabProgram.diagnostic_id == Diagnostic.id)
            .join(Doctor, Diagnostic.doctor_id == Doctor.id)
            .join(AppUser, Doctor.identity_id == AppUser.identity_id)
            .where(*filters)
        )
        total = self.db.scalar(total_q) or 0

        programs_q = (
            select(RehabProgram)
            .join(Diagnostic, RehabProgram.diagnostic_id == Diagnostic.id)
            .join(Doctor, Diagnostic.doctor_id == Doctor.id)
            .join(AppUser, Doctor.identity_id == AppUser.identity_id)
            .where(*filters)
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
        program = check_program_belongs_to_diagnostic(program_id, None, self.db)
        check_diagnostic_authorized(program.diagnostic_id, doctor_subject, self.db)

        program.estado = self._normalize_program_status(estado)
        program.name = name
        program.start_date = start_date
        program.end_date = end_date
        program.physiotherapist_id = physiotherapist_id
        program.updated_at = func.now()
        self.db.flush()
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

    def list_program_exercises(
        self,
        program_id: UUID,
        limit: int,
        offset: int,
        doctor_subject: str,
    ) -> tuple[list[ProgramExerciseRecord], int]:
        program = check_program_belongs_to_diagnostic(program_id, None, self.db)
        check_diagnostic_authorized(program.diagnostic_id, doctor_subject, self.db)

        total_q = select(func.count()).select_from(ProgramExercise).where(
            ProgramExercise.program_id == program_id
        )
        total = self.db.scalar(total_q) or 0

        assignments_q = (
            select(ProgramExercise)
            .where(ProgramExercise.program_id == program_id)
            .order_by(ProgramExercise.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        assignments = self.db.scalars(assignments_q).all()
        return [self._program_exercise_record(assignment) for assignment in assignments], total

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
            name=program.name,
            start_date=program.start_date,
            end_date=program.end_date,
            physiotherapist_id=program.physiotherapist_id,
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
            created_at=assignment.created_at,
        )
