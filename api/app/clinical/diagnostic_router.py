from fastapi import APIRouter, Depends, status
from pydantic import UUID4

from app.auth import require_role
from app.clinical.adapters.postgres_diagnostic_repository import PostgresDiagnosticRepository
from app.clinical.diagnostic_service import DiagnosticService
from app.clinical.schemas import DiagnosticIn, DiagnosticOut, DiagnosticPatchIn, ListQuery, PaginatedResponse
from app.db import get_db

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def get_diagnostic_service(db=Depends(get_db)) -> DiagnosticService:
    return DiagnosticService(PostgresDiagnosticRepository(db))


@router.post("/", response_model=DiagnosticOut, status_code=status.HTTP_201_CREATED)
def create_diagnostic(
    body: DiagnosticIn,
    principal=Depends(require_role("medical")),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    return service.create_diagnostic(body, principal["sub"])


@router.get("/", response_model=PaginatedResponse[DiagnosticOut])
def list_diagnostics(
    query: ListQuery = Depends(),
    principal=Depends(require_role("medical")),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    return service.list_diagnostics(query, principal["sub"])


@router.get("/{diagnostic_id}", response_model=DiagnosticOut)
def get_diagnostic(
    diagnostic_id: UUID4,
    principal=Depends(require_role("medical")),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    return service.get_diagnostic(diagnostic_id, principal["sub"])


@router.patch("/{diagnostic_id}", response_model=DiagnosticOut)
def update_diagnostic(
    diagnostic_id: UUID4,
    body: DiagnosticPatchIn,
    principal=Depends(require_role("medical")),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    return service.update_diagnostic(diagnostic_id, body, principal["sub"])
