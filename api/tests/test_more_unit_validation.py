from uuid import UUID

class DummyDB:
    def __init__(self, results_map):
        self.results_map = results_map

    def scalar(self, query):
        entity = query.column_descriptions[0]["entity"].__name__
        return {
            "Patient": self.results_map.get("patient"),
            "CareAssignment": self.results_map.get("assignment"),
            "Diagnostic": self.results_map.get("diagnostic"),
            "RehabProgram": self.results_map.get("program"),
            "RehabExercise": self.results_map.get("exercise"),
        }.get(entity)

# Ejemplo uso en test

import pytest
from fastapi import HTTPException, status
from uuid import uuid4
from app.clinical.validation import check_patient_exists_and_assigned
from app.clinical.models import Patient, CareAssignment

def test_check_patient_exists_and_assigned():
    patient_id = uuid4()
    doctor_id = 'doctor123'
    patient = Patient(id=patient_id)
    assignment = CareAssignment(doctor_keycloak_id=doctor_id, patient_id=patient_id)
    db = DummyDB({'patient': patient, 'assignment': assignment})
    result = check_patient_exists_and_assigned(patient_id, doctor_id, db)
    assert result == patient

def test_check_patient_not_found():
    db = DummyDB({'patient': None, 'assignment': None})
    with pytest.raises(HTTPException) as excinfo:
        check_patient_exists_and_assigned(uuid4(), 'doctor', db)
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND

def test_check_patient_not_assigned():
    patient_id = uuid4()
    db = DummyDB({'patient': Patient(id=patient_id), 'assignment': None})
    with pytest.raises(HTTPException) as excinfo:
        check_patient_exists_and_assigned(patient_id, 'wrongdoc', db)
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
