from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from pydantic import UUID4
from typing import List

from app.clinical.schemas import (
    ProgramIn, ProgramOut, ProgramExerciseIn, ProgramExerciseOut, ListQuery, PaginatedResponse
)
from app.clinical.validation import (
    check_diagnostic_authorized, check_exercise_exists, check_program_belongs_to_diagnostic, parse_pagination
)
from app.db import get_db
from app.clinical.models import RehabProgram, ProgramExercise

router = APIRouter(prefix="/programs", tags=["programs"])

@router.post("/", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
async def create_program(
    body: ProgramIn,
    principal=Depends(),  # Implement your auth dependency
    db=Depends(get_db)
):
    # Validación
    await check_diagnostic_authorized(body.diagnostic_id, principal["sub"], db)

    program = RehabProgram(
        diagnostic_id=body.diagnostic_id,
        estado=body.estado or "activo"
    )
    db.add(program)
    await db.flush()
    await db.commit()

    return ProgramOut(
        id=program.id,
        diagnostic_id=program.diagnostic_id,
        estado=program.estado
    )

@router.get("/", response_model=PaginatedResponse[ProgramOut])
async def list_programs(
    diagnostic_id: UUID4,
    query: ListQuery = Depends(),
    principal=Depends(),
    db=Depends(get_db),
):
    limit, offset = parse_pagination(query.limit, query.offset)

    # Validar autorizacion para diagnostic id
    await check_diagnostic_authorized(diagnostic_id, principal["sub"], db)

    total_q = select(func.count()).select_from(RehabProgram).where(RehabProgram.diagnostic_id == diagnostic_id)
    total = await db.scalar(total_q)

    programs_q = (
        select(RehabProgram)
        .where(RehabProgram.diagnostic_id == diagnostic_id)
        .limit(limit)
        .offset(offset)
        .order_by(RehabProgram.created_at.desc())
    )

    programs = (await db.scalars(programs_q)).all()

    programs_out = [ProgramOut(
        id=p.id,
        diagnostic_id=p.diagnostic_id,
        estado=p.estado
    ) for p in programs]

    return PaginatedResponse[
        ProgramOut
    ](items=programs_out, total=total, limit=limit, offset=offset)

@router.get("/{program_id}", response_model=ProgramOut)
async def get_program(
    program_id: UUID4,
    principal=Depends(),
    db=Depends(get_db)
):
    # Validar programa existe y autorizado
    program = await check_program_belongs_to_diagnostic(program_id, None, db)  # diagnostic_id None -> no check here
    # Verificar asignacion doctor
    await check_diagnostic_authorized(program.diagnostic_id, principal["sub"], db)

    return ProgramOut(
        id=program.id,
        diagnostic_id=program.diagnostic_id,
        estado=program.estado
    )

@router.post("/{program_id}/exercises", response_model=ProgramExerciseOut, status_code=status.HTTP_201_CREATED)
async def assign_exercise(
    program_id: UUID4,
    body: ProgramExerciseIn,
    principal=Depends(),
    db=Depends(get_db),
):
    # Validar programa y diagnostico
    program = await check_program_belongs_to_diagnostic(program_id, None, db)  # no diagnostic_id
    await check_diagnostic_authorized(program.diagnostic_id, principal["sub"], db)

    # Verificar ejercicio existe
    await check_exercise_exists(body.exercise_id, db)

    # Crear asignacion
    assignment = ProgramExercise(
        program_id=program_id,
        exercise_id=body.exercise_id,
        pauta=body.pauta
    )
    db.add(assignment)
    await db.flush()
    await db.commit()

    return ProgramExerciseOut(
        id=assignment.id,
        program_id=assignment.program_id,
        exercise_id=assignment.exercise_id,
        pauta=assignment.pauta
    )
