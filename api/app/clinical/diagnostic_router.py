from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from pydantic import UUID4
from typing import List

from app.clinical.schemas import DiagnosticIn, DiagnosticOut, DiagnosticPatchIn, ListQuery, PaginatedResponse
from app.clinical.validation import (
    check_patient_exists_and_assigned, check_diagnostic_authorized, parse_pagination
)
from app.db import get_db
from app.clinical.models import Diagnostic, CareAssignment

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

@router.post("/", response_model=DiagnosticOut, status_code=status.HTTP_201_CREATED)
async def create_diagnostic(
    body: DiagnosticIn,
    principal=Depends(),  # Implement your auth dependency
    db=Depends(get_db)
):
    # Validations
    await check_patient_exists_and_assigned(body.patient_id, principal["sub"], db)

    diag = Diagnostic(
        patient_id=body.patient_id,
        doctor_id=principal["sub"],
        dolencia=body.dolencia,
        descripcion=body.descripcion,
    )
    db.add(diag)
    await db.flush()
    await db.commit()

    return DiagnosticOut(
        id=diag.id,
        patient_id=diag.patient_id,
        dolencia=diag.dolencia,
        descripcion=diag.descripcion,
    )

@router.get("/", response_model=PaginatedResponse[DiagnosticOut])
async def list_diagnostics(
    query: ListQuery = Depends(),
    principal=Depends(),  # Implement your auth dependency
    db=Depends(get_db),
):
    limit, offset = parse_pagination(query.limit, query.offset)

    # Query diagnostics with CareAssignment filter by principal
    subq = select(CareAssignment.patient_id).where(CareAssignment.doctor_keycloak_id == principal["sub"])

    total_q = select(func.count()).select_from(Diagnostic).where(Diagnostic.patient_id.in_(subq))
    total = await db.scalar(total_q)

    diagnostics_q = (
        select(Diagnostic)
        .where(Diagnostic.patient_id.in_(subq))
        .limit(limit)
        .offset(offset)
        .order_by(Diagnostic.created_at.desc())
    )

    diagnostics = (await db.scalars(diagnostics_q)).all()

    diagnostics_out = [DiagnosticOut(
        id=d.id,
        patient_id=d.patient_id,
        dolencia=d.dolencia,
        descripcion=d.descripcion
    ) for d in diagnostics]

    return PaginatedResponse[
        DiagnosticOut
    ](items=diagnostics_out, total=total, limit=limit, offset=offset)

@router.get("/{diagnostic_id}", response_model=DiagnosticOut)
async def get_diagnostic(
    diagnostic_id: UUID4, principal=Depends(), db=Depends(get_db)
):
    diag = await check_diagnostic_authorized(diagnostic_id, principal["sub"], db)

    return DiagnosticOut(
        id=diag.id,
        patient_id=diag.patient_id,
        dolencia=diag.dolencia,
        descripcion=diag.descripcion
    )

@router.patch("/{diagnostic_id}", response_model=DiagnosticOut)
async def update_diagnostic(
    diagnostic_id: UUID4,
    body: DiagnosticPatchIn,
    principal=Depends(),
    db=Depends(get_db),
):
    diag = await check_diagnostic_authorized(diagnostic_id, principal["sub"], db)

    if body.dolencia is not None:
        diag.dolencia = body.dolencia
    if body.descripcion is not None:
        diag.descripcion = body.descripcion

    db.add(diag)
    await db.flush()
    await db.commit()

    return DiagnosticOut(
        id=diag.id,
        patient_id=diag.patient_id,
        dolencia=diag.dolencia,
        descripcion=diag.descripcion
    )
