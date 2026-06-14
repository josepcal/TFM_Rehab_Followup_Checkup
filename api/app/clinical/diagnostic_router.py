from fastapi import APIRouter, Depends, status
from sqlalchemy import select, func
from pydantic import UUID4

from app.auth import require_role
from app.clinical.schemas import DiagnosticIn, DiagnosticOut, DiagnosticPatchIn, ListQuery, PaginatedResponse
from app.clinical.validation import (
    check_patient_exists_and_assigned, check_diagnostic_authorized, parse_pagination
)
from app.db import get_db
from app.clinical.models import Diagnostic, CareAssignment

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

@router.post("/", response_model=DiagnosticOut, status_code=status.HTTP_201_CREATED)
def create_diagnostic(
    body: DiagnosticIn,
    principal=Depends(require_role("medical")),
    db=Depends(get_db)
):
    # Validations
    check_patient_exists_and_assigned(body.patient_id, principal["sub"], db)

    diag = Diagnostic(
        patient_id=body.patient_id,
        doctor_id=principal["sub"],
        dolencia=body.dolencia,
        descripcion=body.descripcion,
    )
    db.add(diag)
    db.flush()

    return DiagnosticOut(
        id=diag.id,
        patient_id=diag.patient_id,
        doctor_id=diag.doctor_id,
        dolencia=diag.dolencia,
        descripcion=diag.descripcion,
        signature=diag.signature,
        signed_at=diag.signed_at,
        created_at=diag.created_at,
    )

@router.get("/", response_model=PaginatedResponse[DiagnosticOut])
def list_diagnostics(
    query: ListQuery = Depends(),
    principal=Depends(require_role("medical")),
    db=Depends(get_db),
):
    limit, offset = parse_pagination(query.limit, query.offset)

    # Query diagnostics with CareAssignment filter by principal
    subq = select(CareAssignment.patient_id).where(CareAssignment.doctor_keycloak_id == principal["sub"])

    total_q = select(func.count()).select_from(Diagnostic).where(Diagnostic.patient_id.in_(subq))
    total = db.scalar(total_q)

    diagnostics_q = (
        select(Diagnostic)
        .where(Diagnostic.patient_id.in_(subq))
        .limit(limit)
        .offset(offset)
        .order_by(Diagnostic.created_at.desc())
    )

    diagnostics = (db.scalars(diagnostics_q)).all()

    diagnostics_out = [DiagnosticOut(
        id=d.id,
        patient_id=d.patient_id,
        doctor_id=d.doctor_id,
        dolencia=d.dolencia,
        descripcion=d.descripcion,
        signature=d.signature,
        signed_at=d.signed_at,
        created_at=d.created_at,
    ) for d in diagnostics]

    return PaginatedResponse[
        DiagnosticOut
    ](data=diagnostics_out, total=total, limit=limit, offset=offset)

@router.get("/{diagnostic_id}", response_model=DiagnosticOut)
def get_diagnostic(
    diagnostic_id: UUID4, principal=Depends(require_role("medical")), db=Depends(get_db)
):
    diag = check_diagnostic_authorized(diagnostic_id, principal["sub"], db)

    return DiagnosticOut(
        id=diag.id,
        patient_id=diag.patient_id,
        dolencia=diag.dolencia,
        descripcion=diag.descripcion
    )

@router.patch("/{diagnostic_id}", response_model=DiagnosticOut)
def update_diagnostic(
    diagnostic_id: UUID4,
    body: DiagnosticPatchIn,
    principal=Depends(require_role("medical")),
    db=Depends(get_db),
):
    diag = check_diagnostic_authorized(diagnostic_id, principal["sub"], db)

    if body.dolencia is not None:
        diag.dolencia = body.dolencia
    if body.descripcion is not None:
        diag.descripcion = body.descripcion

    db.add(diag)
    db.flush()

    return DiagnosticOut(
        id=diag.id,
        patient_id=diag.patient_id,
        dolencia=diag.dolencia,
        descripcion=diag.descripcion
    )
