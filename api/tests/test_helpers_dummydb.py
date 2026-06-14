from fastapi import HTTPException
from starlette.status import HTTP_403_FORBIDDEN
from uuid import UUID

class DummyDB:
    def __init__(self, patient=None, assignment=None, diagnostic=None, program=None, exercise=None):
        self.patient = patient
        self.assignment = assignment
        self.diagnostic = diagnostic
        self.program = program
        self.exercise = exercise

    def scalar(self, query):
        query_str = str(query)
        if 'Patient.id' in query_str:
            return self.patient
        if 'CareAssignment.patient_id' in query_str and 'CareAssignment.doctor_keycloak_id' in query_str:
            if self.patient is None:
                return None
            if self.assignment is None:
                raise HTTPException(HTTP_403_FORBIDDEN, 'Doctor not assigned to this patient')
            return self.assignment
        if 'Diagnostic.id' in query_str:
            return self.diagnostic
        if 'RehabProgram.id' in query_str:
            return self.program
        if 'RehabExercise.id' in query_str:
            return self.exercise
        return None
