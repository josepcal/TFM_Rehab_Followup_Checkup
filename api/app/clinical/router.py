import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text

from app.auth import require_role
from app.clinical.models import (CareAssignment, Diagnostic, Patient,
                                 ProgramExercise, PseudonymMap, RehabProgram)
from app.db import get_db

router = APIRouter(tags=["clinical"])


class PatientIn(BaseModel):
    nombre: str
    apellidos: str
    national_id: str | None = None


class ClaimIn(BaseModel):
    national_id: str


@router.post("/patients")
def create_patient(body: PatientIn, principal=Depends(require_role("medical", "admin")),
                   db=Depends(get_db)):
    p = Patient(nombre=body.nombre, apellidos=body.apellidos, national_id=body.national_id)
    db.add(p)
    db.flush()
    db.add(PseudonymMap(patient_id=p.id, pseudonym_id=uuid.uuid4()))
    # el medico que lo da de alta queda asignado (relacion terapeutica)
    db.add(CareAssignment(doctor_keycloak_id=principal["sub"], patient_id=p.id))
    return {"id": str(p.id)}


@router.get("/patients")
def list_patients(_=Depends(require_role("medical", "admin")), db=Depends(get_db)):
    # La RLS filtra: el medico solo ve los pacientes que tiene asignados.
    rows = db.scalars(select(Patient)).all()
    return [{"id": str(p.id), "nombre": p.nombre, "apellidos": p.apellidos} for p in rows]


@router.post("/patients/claim")
def claim_patient(body: ClaimIn, principal=Depends(require_role("medical")),
                  db=Depends(get_db)):
    """Reclamar un paciente por DNI exacto (crea la relacion). Via SECURITY DEFINER en BD."""
    row = db.execute(text("SELECT clinical.claim_patient(:nid)"),
                     {"nid": body.national_id}).first()
    if not row or not row[0]:
        raise HTTPException(404, "paciente no encontrado")
    return {"patient_id": str(row[0])}


class DiagnosticIn(BaseModel):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    dolencia: str
    descripcion: str | None = None


@router.post("/diagnostics")
def create_diagnostic(body: DiagnosticIn, _=Depends(require_role("medical")),
                      db=Depends(get_db)):
    d = Diagnostic(**body.model_dump())
    db.add(d)
    db.flush()
    prog = RehabProgram(diagnostic_id=d.id)
    db.add(prog)
    db.flush()
    return {"diagnostic_id": str(d.id), "program_id": str(prog.id)}


class AssignExerciseIn(BaseModel):
    program_id: uuid.UUID
    exercise_id: uuid.UUID
    pauta: str | None = None


# Deprecated endpoint, replaced by program_router
@router.post("/programs/exercises")
def assign_exercise(body: AssignExerciseIn, principal=Depends(), db=Depends(get_db)):
    from app.clinical.program_router import assign_exercise as new_assign_exercise
    return new_assign_exercise(body.program_id, body, principal, db)

