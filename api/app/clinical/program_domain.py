from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ProgramRecord:
    id: UUID
    diagnostic_id: UUID
    estado: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class ProgramExerciseRecord:
    id: UUID
    program_id: UUID
    exercise_id: UUID
    pauta: str | None = None
    estado: str | None = None
