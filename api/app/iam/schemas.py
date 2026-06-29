"""Pydantic schemas for the IAM domain (UC-15 audit log + RGPD data-subject rights)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EventLogEntry(BaseModel):
    event_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    actor_id: uuid.UUID | None
    payload: dict | None
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# RGPD Art. 15 — export schema
# ---------------------------------------------------------------------------

class PatientProfileOut(BaseModel):
    patient_id: uuid.UUID
    first_name: str
    last_name: str
    national_id: str | None
    birth_date: datetime | None
    sex: str | None
    created_at: datetime | None


class DiagnosticOut(BaseModel):
    diagnostic_id: uuid.UUID
    dolencia: str
    description: str | None
    signed_at: datetime | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class RehabProgramOut(BaseModel):
    rehab_program_id: uuid.UUID
    name: str | None
    status: str
    start_date: datetime | None
    end_date: datetime | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ConsentOut(BaseModel):
    consent_id: uuid.UUID
    rehab_program_id: uuid.UUID
    granted: bool
    granted_at: datetime | None
    withdrawn_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PatientExportOut(BaseModel):
    exported_at: datetime
    profile: PatientProfileOut
    diagnostics: list[DiagnosticOut]
    rehab_programs: list[RehabProgramOut]
    consents: list[ConsentOut]
    note: str = (
        "WAV recordings (biometric data) are excluded from this export. "
        "Request them via the supervised erasure process."
    )

    @classmethod
    def build(cls, patient: Any, diagnostics: list, programs: list, consents: list, national_id: str | None = None) -> "PatientExportOut":
        return cls(
            exported_at=datetime.utcnow(),
            profile=PatientProfileOut(
                patient_id=patient.id,
                first_name=patient.nombre,
                last_name=patient.apellidos,
                national_id=national_id,
                birth_date=patient.birth_date,
                sex=patient.sex,
                created_at=patient.created_at,
            ),
            diagnostics=[
                DiagnosticOut(
                    diagnostic_id=d.id,
                    dolencia=d.dolencia,
                    description=d.descripcion,
                    signed_at=d.signed_at,
                    created_at=d.created_at,
                )
                for d in diagnostics
            ],
            rehab_programs=[
                RehabProgramOut(
                    rehab_program_id=p.id,
                    name=p.name,
                    status=p.estado,
                    start_date=p.start_date,
                    end_date=p.end_date,
                    created_at=p.created_at,
                )
                for p in programs
            ],
            consents=[
                ConsentOut(
                    consent_id=c.consent_id,
                    rehab_program_id=c.rehab_program_id,
                    granted=c.granted,
                    granted_at=c.granted_at,
                    withdrawn_at=c.withdrawn_at,
                )
                for c in consents
            ],
        )
