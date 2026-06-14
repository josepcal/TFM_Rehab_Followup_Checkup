from fastapi import HTTPException, status
from sqlalchemy import select
from app.clinical.models import Patient, Diagnostic, RehabProgram, CareAssignment
from app.catalog.models import RehabExercise

def check_patient_exists_and_assigned(patient_id, doctor_keycloak_id, db):
    # Check if patient exists
    patient = db.scalar(select(Patient).where(Patient.id == patient_id))
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    # Check if doctor assigned
    assignment = db.scalar(select(CareAssignment).where(
        (CareAssignment.patient_id == patient_id) &
        (CareAssignment.doctor_keycloak_id == doctor_keycloak_id)))
    if not assignment:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Doctor not assigned to this patient")
    return patient

def check_exercise_exists(exercise_id, db):
    exercise = db.scalar(select(RehabExercise).where(RehabExercise.id == exercise_id))
    if not exercise:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")
    return exercise

def check_diagnostic_authorized(diagnostic_id, doctor_keycloak_id, db):
    diag = db.scalar(select(Diagnostic).where(Diagnostic.id == diagnostic_id))
    if not diag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnostic not found")
    assignment = db.scalar(select(CareAssignment).where(
        (CareAssignment.patient_id == diag.patient_id) &
        (CareAssignment.doctor_keycloak_id == doctor_keycloak_id)))
    if not assignment:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Doctor not authorized for this diagnostic")
    return diag

def check_program_belongs_to_diagnostic(program_id, diagnostic_id, db):
    prog = db.scalar(select(RehabProgram).where(RehabProgram.id == program_id))
    if not prog:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Program not found")
    if diagnostic_id is not None and prog.diagnostic_id != diagnostic_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Program does not belong to diagnostic")
    return prog


def parse_pagination(limit: int = 20, offset: int = 0):
    if limit < 0 or limit > 100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Limit must be between 0 and 100")
    if offset < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Offset must be 0 or greater")
    return limit, offset
