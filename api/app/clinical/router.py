import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.auth import require_role
from app.clinical.adapters.postgres_diagnostic_repository import PostgresDiagnosticRepository
from app.clinical.adapters.postgres_program_repository import PostgresProgramRepository
from app.clinical.diagnostic_service import DiagnosticService
from app.clinical.models import CareAssignment, Diagnostic, Doctor, Patient, PseudonymMap
from app.clinical.program_service import ProgramService
from app.clinical.schemas import DiagnosticIn as ClinicalDiagnosticIn
from app.clinical.schemas import DoctorOut
from app.clinical.schemas import ProgramExerciseIn, ProgramIn
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
    last_assessment_sq = (
        select(
            Diagnostic.patient_id,
            func.max(func.coalesce(Diagnostic.signed_at, Diagnostic.created_at)).label("last_assessment"),
        )
        .group_by(Diagnostic.patient_id)
        .subquery()
    )
    rows = db.execute(
        select(Patient, last_assessment_sq.c.last_assessment)
        .outerjoin(last_assessment_sq, last_assessment_sq.c.patient_id == Patient.id)
        .order_by(Patient.apellidos, Patient.nombre)
    ).all()
    return [
        {
            "id": str(p.id),
            "nombre": p.nombre,
            "apellidos": p.apellidos,
            "birth_date": p.birth_date,
            "sex": p.sex,
            "last_assessment": last_assessment,
        }
        for p, last_assessment in rows
    ]


@router.get("/doctors", response_model=list[DoctorOut])
def list_doctors(_=Depends(require_role("medical", "admin")), db=Depends(get_db)):
    rows = db.scalars(select(Doctor).order_by(Doctor.apellidos, Doctor.nombre)).all()
    return [
        DoctorOut(
            id=doctor.id,
            nombre=doctor.nombre,
            apellidos=doctor.apellidos,
            doctor_type=doctor.doctor_type,
            colegiado_id=doctor.colegiado_id,
        )
        for doctor in rows
    ]


@router.post("/patients/claim")
def claim_patient(body: ClaimIn, principal=Depends(require_role("medical")),
                  db=Depends(get_db)):
    """Reclamar un paciente por DNI exacto (crea la relacion). Via SECURITY DEFINER en BD."""
    row = db.execute(text("SELECT clinical.claim_patient(:nid)"),
                     {"nid": body.national_id}).first()
    if not row or not row[0]:
        raise HTTPException(404, "paciente no encontrado")
    return {"patient_id": str(row[0])}


class LegacyDiagnosticIn(BaseModel):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID | None = None  # Deprecated: ignored; principal decides doctor.
    dolencia: str
    descripcion: str | None = None
    history: str | None = None
    symptoms: str | None = None


@router.post("/diagnostics", status_code=status.HTTP_201_CREATED)
def create_diagnostic(
    body: LegacyDiagnosticIn,
    principal=Depends(require_role("medical")),
    db=Depends(get_db),
):
    """Deprecated compatibility endpoint.

    Creates a diagnostic and an initial rehab program, preserving the legacy
    response shape while delegating to the diagnostic/program services.
    """
    diagnostic_service = DiagnosticService(PostgresDiagnosticRepository(db))
    program_service = ProgramService(PostgresProgramRepository(db))

    diagnostic = diagnostic_service.create_diagnostic(
        ClinicalDiagnosticIn(
            patient_id=body.patient_id,
            dolencia=body.dolencia,
            descripcion=body.descripcion,
            history=body.history,
            symptoms=body.symptoms,
        ),
        principal["sub"],
    )
    program = program_service.create_program(ProgramIn(diagnostic_id=diagnostic.id), principal["sub"])
    return {"diagnostic_id": str(diagnostic.id), "program_id": str(program.id)}


class AssignExerciseIn(BaseModel):
    program_id: uuid.UUID
    exercise_id: uuid.UUID
    pauta: str | None = None


@router.post("/programs/exercises")
def assign_exercise(
    body: AssignExerciseIn,
    principal=Depends(require_role("medical")),
    db=Depends(get_db),
):
    """Deprecated compatibility endpoint, replaced by POST /programs/{id}/exercises."""
    service = ProgramService(PostgresProgramRepository(db))
    return service.assign_exercise(
        body.program_id,
        ProgramExerciseIn(exercise_id=body.exercise_id, pauta=body.pauta),
        principal["sub"],
    )
