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
    # Denormalised from the program's diagnostic and its patient, so a doctor can
    # recognise a program in a list without resolving raw UUIDs. Only the list
    # query joins them; the single-program reads leave them unset.
    patient_id: UUID | None = None
    patient_nombre: str | None = None
    patient_apellidos: str | None = None
    dolencia: str | None = None


@dataclass(frozen=True)
class ProgramExerciseRecord:
    id: UUID
    program_id: UUID
    exercise_id: UUID
    pauta: str | None = None
    estado: str | None = None
    created_at: datetime | None = None
    exercise_type: str | None = None
    exercise_description: str | None = None
