from fastapi import HTTPException
from starlette.status import HTTP_403_FORBIDDEN
from uuid import UUID

class DummyDB:
    def __init__(self, patient=None, assignment=None, diagnostic=None, program=None, exercise=None, assignment_patient_id=None, assignment_doctor_keycloak_id=None):
        self.patient = patient
        self.assignment = assignment
        self.diagnostic = diagnostic
        self.program = program
        self.exercise = exercise
        self.assignment_patient_id = assignment_patient_id
        self.assignment_doctor_keycloak_id = assignment_doctor_keycloak_id

    def scalar(self, query):
        entity = query.column_descriptions[0]["entity"].__name__
        if entity == "Patient":
            return self.patient
        if entity == "CareAssignment":
            if self.assignment is None:
                return None
            if self.assignment_patient_id is None and self.assignment_doctor_keycloak_id is None:
                return self.assignment
            if (
                self.patient is not None
                and self.assignment_patient_id == self.patient.id
                and self.assignment_doctor_keycloak_id == self.assignment.doctor_keycloak_id
            ):
                return self.assignment
            return None
        if entity == "Diagnostic":
            return self.diagnostic
        if entity == "RehabProgram":
            return self.program
        if entity == "RehabExercise":
            return self.exercise
        return None

import pytest
from fastapi import HTTPException, status
from uuid import uuid4
from app.clinical.validation import check_patient_exists_and_assigned
from app.clinical.models import Patient, CareAssignment

def test_check_patient_exists_and_assigned_success():
    patient_id = uuid4()
    doctor_id = 'doctor123'
    patient = Patient(id=patient_id)
    assignment = CareAssignment(doctor_keycloak_id=doctor_id, patient_id=patient_id)

    db = DummyDB(patient=patient, assignment=assignment, assignment_patient_id=patient_id, assignment_doctor_keycloak_id=doctor_id)

    result = check_patient_exists_and_assigned(patient_id, doctor_id, db)
    assert result == patient

def test_check_patient_not_found():
    db = DummyDB(patient=None, assignment=None)
    with pytest.raises(HTTPException) as excinfo:
        check_patient_exists_and_assigned(uuid4(), 'doctor', db)
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND

def test_check_doctor_not_assigned():
    patient_id = uuid4()
    patient = Patient(id=patient_id)
    db = DummyDB(patient=patient, assignment=None)
    with pytest.raises(HTTPException) as excinfo:
        check_patient_exists_and_assigned(patient_id, 'wrongdoc', db)
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
