import uuid
from pydantic import BaseModel, Field, validator
from typing import Generic, TypeVar, List, Optional
from pydantic.generics import GenericModel

T = TypeVar('T')

class DiagnosticIn(BaseModel):
    patient_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None  # Will be injected, not required in request
    dolencia: str = Field(..., min_length=1, max_length=500)
    descripcion: Optional[str] = Field(None, max_length=5000)

class DiagnosticOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    dolencia: str
    descripcion: Optional[str]
    created_at: Optional[str] = None  # DateTime as ISO string
    updated_at: Optional[str] = None

class DiagnosticPatchIn(BaseModel):
    dolencia: Optional[str] = Field(None, min_length=1, max_length=500)
    descripcion: Optional[str] = Field(None, max_length=5000)

class ProgramIn(BaseModel):
    diagnostic_id: uuid.UUID
    estado: Optional[str] = "activo"

class ProgramOut(BaseModel):
    id: uuid.UUID
    diagnostic_id: uuid.UUID
    estado: str
    created_at: Optional[str] = None

class ProgramExerciseIn(BaseModel):
    exercise_id: uuid.UUID
    pauta: Optional[str]

class ProgramExerciseOut(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    exercise_id: uuid.UUID
    pauta: Optional[str]

class PatientOut(BaseModel):
    id: uuid.UUID
    nombre: str
    apellidos: str

class ListQuery(BaseModel):
    limit: Optional[int] = Field(20, ge=0, le=100)
    offset: Optional[int] = Field(0, ge=0)

class PaginatedResponse(GenericModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int

class ErrorResponse(BaseModel):
    detail: str
    code: str

# Add any extra validators if needed
