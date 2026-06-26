import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.auth import require_role
from app.catalog.models import RehabExercise
from app.clinical.adapters.postgres_diagnostic_repository import PostgresDiagnosticRepository
from app.clinical.adapters.postgres_program_repository import PostgresProgramRepository
from app.clinical.diagnostic_service import DiagnosticService
from app.clinical.models import AppUser, CareAssignment, Diagnostic, Doctor, Patient, ProgramExercise, PseudonymMap, RehabProgram
from app.clinical.program_service import ProgramService
from app.clinical.schemas import DiagnosticIn as ClinicalDiagnosticIn
from app.clinical.schemas import DiagnosticOut, DoctorOut, ListQuery, PaginatedResponse, PatientOut, ProgramExerciseOut, ProgramOut
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


@router.get("/patients/me", response_model=PatientOut)
def get_my_patient(principal=Depends(require_role("patient")), db=Depends(get_db)):
    patient = _patient_by_subject(principal["sub"], db)
    return PatientOut(
        id=patient.id,
        nombre=patient.nombre,
        apellidos=patient.apellidos,
        birth_date=patient.birth_date,
        sex=patient.sex,
    )


@router.get("/patients/me/diagnostics", response_model=PaginatedResponse[DiagnosticOut])
def list_my_diagnostics(
    query: ListQuery = Depends(),
    principal=Depends(require_role("patient")),
    db=Depends(get_db),
):
    patient = _patient_by_subject(principal["sub"], db)
    total = db.scalar(select(func.count()).select_from(Diagnostic).where(Diagnostic.patient_id == patient.id)) or 0
    diagnostics = db.scalars(
        select(Diagnostic)
        .where(Diagnostic.patient_id == patient.id)
        .order_by(func.coalesce(Diagnostic.signed_at, Diagnostic.created_at).desc())
        .limit(query.limit)
        .offset(query.offset)
    ).all()
    return PaginatedResponse[DiagnosticOut](
        data=[
            DiagnosticOut(
                id=diagnostic.id,
                patient_id=diagnostic.patient_id,
                doctor_id=diagnostic.doctor_id,
                dolencia=diagnostic.dolencia,
                descripcion=diagnostic.descripcion,
                history=diagnostic.history,
                symptoms=diagnostic.symptoms,
                signature=diagnostic.signature,
                signed_at=diagnostic.signed_at,
                content_hash=diagnostic.content_hash,
                created_at=diagnostic.created_at,
                updated_at=diagnostic.updated_at,
            )
            for diagnostic in diagnostics
        ],
        total=total,
        limit=query.limit,
        offset=query.offset,
    )


@router.get("/patients/me/programs", response_model=PaginatedResponse[ProgramOut])
def list_my_programs(
    query: ListQuery = Depends(),
    principal=Depends(require_role("patient")),
    db=Depends(get_db),
):
    patient = _patient_by_subject(principal["sub"], db)
    total = (
        db.scalar(
            select(func.count())
            .select_from(RehabProgram)
            .join(Diagnostic, RehabProgram.diagnostic_id == Diagnostic.id)
            .where(Diagnostic.patient_id == patient.id)
        )
        or 0
    )
    programs = db.scalars(
        select(RehabProgram)
        .join(Diagnostic, RehabProgram.diagnostic_id == Diagnostic.id)
        .where(Diagnostic.patient_id == patient.id)
        .order_by(RehabProgram.created_at.desc())
        .limit(query.limit)
        .offset(query.offset)
    ).all()
    return PaginatedResponse[ProgramOut](
        data=[_program_out(program) for program in programs],
        total=total,
        limit=query.limit,
        offset=query.offset,
    )


@router.get("/patients/me/programs/{program_id}", response_model=ProgramOut)
def get_my_program(
    program_id: uuid.UUID,
    principal=Depends(require_role("patient")),
    db=Depends(get_db),
):
    patient = _patient_by_subject(principal["sub"], db)
    program = _patient_program(program_id, patient.id, db)
    return _program_out(program)


@router.get("/patients/me/programs/{program_id}/exercises", response_model=PaginatedResponse[ProgramExerciseOut])
def list_my_program_exercises(
    program_id: uuid.UUID,
    query: ListQuery = Depends(),
    principal=Depends(require_role("patient")),
    db=Depends(get_db),
):
    patient = _patient_by_subject(principal["sub"], db)
    _patient_program(program_id, patient.id, db)
    total = db.scalar(select(func.count()).select_from(ProgramExercise).where(ProgramExercise.program_id == program_id)) or 0
    assignments = db.execute(
        select(ProgramExercise, RehabExercise)
        .join(RehabExercise, RehabExercise.id == ProgramExercise.exercise_id)
        .where(ProgramExercise.program_id == program_id)
        .order_by(ProgramExercise.created_at.desc())
        .limit(query.limit)
        .offset(query.offset)
    ).all()
    return PaginatedResponse[ProgramExerciseOut](
        data=[
            ProgramExerciseOut(
                id=assignment.id,
                program_id=assignment.program_id,
                exercise_id=assignment.exercise_id,
                pauta=assignment.pauta,
                estado=assignment.estado,
                created_at=assignment.created_at,
                exercise_type=exercise.nombre,
                exercise_description=exercise.descripcion,
            )
            for assignment, exercise in assignments
        ],
        total=total,
        limit=query.limit,
        offset=query.offset,
    )


def _patient_by_subject(subject: str, db) -> Patient:
    patient = db.scalar(
        select(Patient).join(AppUser, Patient.identity_id == AppUser.identity_id).where(AppUser.external_subject == subject)
    )
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient profile not found")
    return patient


def _patient_program(program_id: uuid.UUID, patient_id: uuid.UUID, db) -> RehabProgram:
    program = db.scalar(
        select(RehabProgram)
        .join(Diagnostic, RehabProgram.diagnostic_id == Diagnostic.id)
        .where(RehabProgram.id == program_id, Diagnostic.patient_id == patient_id)
    )
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rehab program not found")
    return program


def _program_out(program: RehabProgram) -> ProgramOut:
    return ProgramOut(
        id=program.id,
        diagnostic_id=program.diagnostic_id,
        estado=program.estado,
        name=program.name,
        start_date=program.start_date,
        end_date=program.end_date,
        physiotherapist_id=program.physiotherapist_id,
        created_at=program.created_at,
    )


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
