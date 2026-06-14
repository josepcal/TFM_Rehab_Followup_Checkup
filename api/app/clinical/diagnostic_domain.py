from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class DiagnosticRecord:
    id: UUID
    patient_id: UUID
    doctor_id: UUID | None
    dolencia: str
    descripcion: str | None = None
    signature: str | None = None
    signed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
