from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ProgramRecord:
    id: UUID
    diagnostic_id: UUID
    estado: str
    name: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    physiotherapist_id: UUID | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class ProgramExerciseRecord:
    id: UUID
    program_id: UUID
    exercise_id: UUID
    pauta: str | None = None
    estado: str | None = None
    created_at: datetime | None = None
