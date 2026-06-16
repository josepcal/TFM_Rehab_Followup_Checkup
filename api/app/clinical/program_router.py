from fastapi import APIRouter, Depends, status
from pydantic import UUID4

from app.auth import require_role
from app.clinical.adapters.postgres_program_repository import PostgresProgramRepository
from app.clinical.program_service import ProgramService
from app.clinical.schemas import (
    ListQuery,
    PaginatedResponse,
    ProgramExerciseIn,
    ProgramExerciseOut,
    ProgramIn,
    ProgramOut,
)
from app.db import get_db

router = APIRouter(prefix="/programs", tags=["programs"])


def get_program_service(db=Depends(get_db)) -> ProgramService:
    return ProgramService(PostgresProgramRepository(db))


@router.post("/", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
def create_program(
    body: ProgramIn,
    principal=Depends(require_role("medical")),
    service: ProgramService = Depends(get_program_service),
):
    return service.create_program(body, principal["sub"])


@router.get("/", response_model=PaginatedResponse[ProgramOut])
def list_programs(
    diagnostic_id: UUID4 | None = None,
    patient_id: UUID4 | None = None,
    query: ListQuery = Depends(),
    principal=Depends(require_role("medical")),
    service: ProgramService = Depends(get_program_service),
):
    return service.list_programs(diagnostic_id, patient_id, query, principal["sub"])


@router.get("/{program_id}", response_model=ProgramOut)
def get_program(
    program_id: UUID4,
    principal=Depends(require_role("medical")),
    service: ProgramService = Depends(get_program_service),
):
    return service.get_program(program_id, principal["sub"])


@router.get("/{program_id}/exercises", response_model=PaginatedResponse[ProgramExerciseOut])
def list_program_exercises(
    program_id: UUID4,
    query: ListQuery = Depends(),
    principal=Depends(require_role("medical")),
    service: ProgramService = Depends(get_program_service),
):
    return service.list_program_exercises(program_id, query, principal["sub"])


@router.post("/{program_id}/exercises", response_model=ProgramExerciseOut, status_code=status.HTTP_201_CREATED)
def assign_exercise(
    program_id: UUID4,
    body: ProgramExerciseIn,
    principal=Depends(require_role("medical")),
    service: ProgramService = Depends(get_program_service),
):
    return service.assign_exercise(program_id, body, principal["sub"])
