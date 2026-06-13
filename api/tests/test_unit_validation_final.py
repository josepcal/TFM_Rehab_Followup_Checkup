import pytest
from fastapi import HTTPException, status
from uuid import uuid4
from app.clinical.validation import (
    check_patient_exists_and_assigned,
    check_exercise_exists,
    check_diagnostic_authorized,
    check_program_belongs_to_diagnostic,
    parse_pagination,
)
from app.clinical.models import Patient, CareAssignment, Diagnostic, RehabProgram
from app.catalog.models import RehabExercise

class DummyDB:
    def __init__(self, patient=None, assignment=None, diagnostic=None, program=None, exercise=None):
        self.patient = patient
        self.assignment = assignment
        self.diagnostic = diagnostic
        self.program = program
        self.exercise = exercise

    async def scalar(self, query):
        entity = query.column_descriptions[0]["entity"].__name__
        return {
            "Patient": self.patient,
            "CareAssignment": self.assignment,
            "Diagnostic": self.diagnostic,
            "RehabProgram": self.program,
            "RehabExercise": self.exercise,
        }.get(entity)

@pytest.mark.asyncio
async def test_check_patient_exists_and_assigned_success():
    patient_id = uuid4()
    doctor_id = 'doctor123'
    patient = Patient(id=patient_id)
    assignment = CareAssignment(doctor_keycloak_id=doctor_id, patient_id=patient_id)

    db = DummyDB(patient=patient, assignment=assignment)

    result = await check_patient_exists_and_assigned(patient_id, doctor_id, db)
    assert result == patient

@pytest.mark.asyncio
async def test_check_patient_not_found():
    db = DummyDB(patient=None, assignment=None)
    with pytest.raises(HTTPException) as excinfo:
        await check_patient_exists_and_assigned(uuid4(), 'doctor', db)
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_check_doctor_not_assigned():
    patient_id = uuid4()
    patient = Patient(id=patient_id)
    db = DummyDB(patient=patient, assignment=None)
    with pytest.raises(HTTPException) as excinfo:
        await check_patient_exists_and_assigned(patient_id, 'wrongdoc', db)
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_check_exercise_exists_success():
    exercise_id = uuid4()
    exercise = RehabExercise(id=exercise_id, nombre='Ejercicio', descripcion='Desc', tipo='tipo1')

    db = DummyDB(exercise=exercise)
    result = await check_exercise_exists(exercise_id, db)
    assert result == exercise

@pytest.mark.asyncio
async def test_check_exercise_not_found():
    db = DummyDB(exercise=None)
    with pytest.raises(HTTPException) as excinfo:
        await check_exercise_exists(uuid4(), db)
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_check_diagnostic_authorized_success():
    diagnostic_id = uuid4()
    patient_id = uuid4()
    doctor_id = 'doc123'
    diag = Diagnostic(id=diagnostic_id, patient_id=patient_id, doctor_id=doctor_id, dolencia='dolor')
    assignment = CareAssignment(doctor_keycloak_id=doctor_id, patient_id=patient_id)

    db = DummyDB(diagnostic=diag, assignment=assignment)
    result = await check_diagnostic_authorized(diagnostic_id, doctor_id, db)
    assert result == diag

@pytest.mark.asyncio
async def test_check_diagnostic_not_found():
    db = DummyDB(diagnostic=None, assignment=None)
    with pytest.raises(HTTPException) as excinfo:
        await check_diagnostic_authorized(uuid4(), 'doc', db)
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_check_diagnostic_unauthorized():
    diagnostic_id = uuid4()
    patient_id = uuid4()
    doctor_id = 'doc123'
    diag = Diagnostic(id=diagnostic_id, patient_id=patient_id, doctor_id=doctor_id, dolencia='dolor')

    db = DummyDB(diagnostic=diag, assignment=None)
    with pytest.raises(HTTPException) as excinfo:
        await check_diagnostic_authorized(diagnostic_id, 'another_doc', db)
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_check_program_belongs_to_diagnostic_success():
    program_id = uuid4()
    diagnostic_id = uuid4()
    program = RehabProgram(id=program_id, diagnostic_id=diagnostic_id, estado='activo')

    db = DummyDB(program=program)
    result = await check_program_belongs_to_diagnostic(program_id, diagnostic_id, db)
    assert result == program

@pytest.mark.asyncio
async def test_check_program_not_found():
    db = DummyDB(program=None)
    with pytest.raises(HTTPException) as excinfo:
        await check_program_belongs_to_diagnostic(uuid4(), uuid4(), db)
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_check_program_diagnostic_mismatch():
    program_id = uuid4()
    diagnostic_id = uuid4()
    program = RehabProgram(id=program_id, diagnostic_id=uuid4(), estado='activo')

    db = DummyDB(program=program)
    with pytest.raises(HTTPException) as excinfo:
        await check_program_belongs_to_diagnostic(program_id, diagnostic_id, db)
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.parametrize('limit,offset', [(10,0), (100,1000)])
def test_parse_pagination_valid(limit, offset):
    assert parse_pagination(limit, offset) == (limit, offset)

@pytest.mark.parametrize('limit', [-1, 101])
def test_parse_pagination_limit_invalid(limit):
    with pytest.raises(HTTPException):
        parse_pagination(limit, 0)

@pytest.mark.parametrize('offset', [-1])
def test_parse_pagination_offset_invalid(offset):
    with pytest.raises(HTTPException):
        parse_pagination(10, offset)
