import uuid
from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class DiagnosticIn(BaseModel):
    patient_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None  # Will be injected, not required in request
    dolencia: str = Field(..., min_length=1, max_length=500)
    descripcion: Optional[str] = Field(None, max_length=5000)
    history: Optional[str] = Field(None, max_length=5000)
    symptoms: Optional[str] = Field(None, max_length=2000)


class DiagnosticOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None
    dolencia: str
    descripcion: Optional[str]
    history: Optional[str] = None
    symptoms: Optional[str] = None
    signature: Optional[str] = None
    signed_at: Optional[datetime] = None
    content_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DiagnosticPatchIn(BaseModel):
    dolencia: Optional[str] = Field(None, min_length=1, max_length=500)
    descripcion: Optional[str] = Field(None, max_length=5000)
    history: Optional[str] = Field(None, max_length=5000)
    symptoms: Optional[str] = Field(None, max_length=2000)


class ProgramIn(BaseModel):
    diagnostic_id: uuid.UUID
    estado: Optional[str] = "activo"
    name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    physiotherapist_id: Optional[uuid.UUID] = None


class ProgramPatchIn(BaseModel):
    estado: Optional[str] = None
    name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    physiotherapist_id: Optional[uuid.UUID] = None


class ProgramOut(BaseModel):
    id: uuid.UUID
    diagnostic_id: uuid.UUID
    estado: str
    name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    physiotherapist_id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None


class ProgramExerciseIn(BaseModel):
    exercise_id: uuid.UUID
    pauta: Optional[str] = None


class ProgramExerciseOut(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    exercise_id: uuid.UUID
    pauta: Optional[str] = None
    estado: Optional[str] = None
    created_at: Optional[datetime] = None


class PatientOut(BaseModel):
    id: uuid.UUID
    nombre: str
    apellidos: str
    birth_date: Optional[datetime] = None
    sex: Optional[str] = None
    last_assessment: Optional[datetime] = None


class ListQuery(BaseModel):
    limit: int = Field(20, ge=0, le=100)
    offset: int = Field(0, ge=0)


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    detail: str
    code: str
