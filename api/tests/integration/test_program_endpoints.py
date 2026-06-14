"""DB-backed integration tests for program detail and exercise assignment endpoints.

These tests are opt-in so the default unit suite stays isolated from PostgreSQL.
Run with a migrated test database, for example:

    RUN_INTEGRATION=1 DATABASE_URL=postgresql://ftm_app:ftm@localhost:5432/ftm \
        api/.venv/bin/python -m pytest api/tests/integration -q
"""

import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration

if os.getenv("RUN_INTEGRATION") != "1":
    pytest.skip(
        "Set RUN_INTEGRATION=1 with a migrated PostgreSQL test DB to run.",
        allow_module_level=True,
    )

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.catalog.models import RehabExercise  # noqa: E402
from app.clinical.models import AppUser, Diagnostic, Doctor, Patient, RehabProgram  # noqa: E402


DEV_DOCTOR_SUB = "dev-user"


def get_or_create_dev_doctor(db_session, suffix: str) -> Doctor:
    doctor_user = db_session.scalar(
        select(AppUser).where(AppUser.external_subject == DEV_DOCTOR_SUB)
    )
    if doctor_user is None:
        doctor_user = AppUser(identity_id=uuid4(), role="medical", external_subject=DEV_DOCTOR_SUB)
        db_session.add(doctor_user)
        db_session.flush()

    doctor = db_session.scalar(select(Doctor).where(Doctor.identity_id == doctor_user.identity_id))
    if doctor is None:
        doctor = Doctor(
            id=uuid4(),
            identity_id=doctor_user.identity_id,
            colegiado_id=f"COL-DEV-{suffix}",
            doctor_type="gp",
            nombre="Doctor",
            apellidos="Dev",
        )
        db_session.add(doctor)
        db_session.flush()
    return doctor


@pytest.fixture(scope="session")
def integration_engine():
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL or DATABASE_URL for integration tests.")

    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            existing_columns = {
                (row.table_schema, row.table_name, row.column_name)
                for row in conn.execute(text("""
                    SELECT table_schema, table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema IN ('clinical', 'catalog')
                """))
            }
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL integration database is not reachable: {exc}")

    required_columns = {
        ("clinical", "app_user", "identity_id"),
        ("clinical", "patient", "patient_id"),
        ("clinical", "doctor", "doctor_id"),
        ("clinical", "diagnostic", "diagnostic_id"),
        ("clinical", "rehab_program", "rehab_program_id"),
        ("clinical", "program_exercise", "program_exercise_id"),
        ("clinical", "rehab_exercise", "rh_exercise_id"),
    }
    missing_columns = sorted(required_columns - existing_columns)
    if missing_columns:
        missing = ", ".join(".".join(column) for column in missing_columns)
        pytest.skip(
            "PostgreSQL schema does not match current SQLAlchemy models; "
            f"missing expected columns/tables: {missing}"
        )

    return engine


@pytest.fixture(scope="session")
def app_client(integration_engine):
    import app.db as app_db
    from app.main import app

    app_db.SessionLocal = sessionmaker(bind=integration_engine, autoflush=False, expire_on_commit=False)
    return TestClient(app)


@pytest.fixture
def db_session(integration_engine):
    Session = sessionmaker(bind=integration_engine, autoflush=False, expire_on_commit=False)
    session = Session()
    session.execute(text("SELECT set_config('app.user', 'integration-test', false)"))
    session.execute(text("SELECT set_config('app.role', 'system', false)"))
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def assigned_program(db_session):
    suffix = uuid4().hex
    patient_user = AppUser(identity_id=uuid4(), role="patient", external_subject=f"patient-integration-{suffix}")
    patient = Patient(
        id=uuid4(),
        identity_id=patient_user.identity_id,
        national_id=f"NID-{suffix}",
        nombre="Paciente",
        apellidos="Integracion",
    )
    db_session.add_all([patient_user, patient])
    db_session.flush()
    doctor = get_or_create_dev_doctor(db_session, suffix)

    diagnostic = Diagnostic(
        id=uuid4(),
        patient_id=patient.id,
        doctor_id=doctor.id,
        dolencia="Dolor de hombro",
        descripcion="Caso de integracion",
        signature=f"signature-{suffix}",
    )
    db_session.add(diagnostic)
    db_session.flush()

    program = RehabProgram(id=uuid4(), diagnostic_id=diagnostic.id, estado="active")
    db_session.add(program)
    db_session.flush()
    db_session.commit()
    return program


@pytest.fixture
def unassigned_program(db_session):
    suffix = uuid4().hex
    patient_user = AppUser(identity_id=uuid4(), role="patient", external_subject=f"other-patient-{suffix}")
    doctor_user = AppUser(identity_id=uuid4(), role="medical", external_subject=f"other-doctor-{suffix}")
    patient = Patient(
        id=uuid4(),
        identity_id=patient_user.identity_id,
        national_id=f"NID-{suffix}",
        nombre="Paciente",
        apellidos="Sin Asignar",
    )
    doctor = Doctor(
        id=uuid4(),
        identity_id=doctor_user.identity_id,
        colegiado_id=f"COL-{suffix}",
        doctor_type="gp",
        nombre="Doctor",
        apellidos="Otro",
    )
    db_session.add_all([patient_user, doctor_user, patient, doctor])
    db_session.flush()

    diagnostic = Diagnostic(
        id=uuid4(),
        patient_id=patient.id,
        doctor_id=doctor.id,
        dolencia="Dolor de rodilla",
        descripcion="No asignado al medico dev",
        signature=f"signature-{suffix}",
    )
    db_session.add(diagnostic)
    db_session.flush()

    program = RehabProgram(id=uuid4(), diagnostic_id=diagnostic.id, estado="active")
    db_session.add(program)
    db_session.flush()
    db_session.commit()
    return program


@pytest.fixture
def exercise(db_session):
    exercise = RehabExercise(
        id=uuid4(),
        nombre="Ejercicio integracion",
        descripcion="Ejercicio para pruebas de asignacion",
        tipo="movilidad",
    )
    db_session.add(exercise)
    db_session.flush()
    db_session.commit()
    return exercise


@pytest.mark.ac("Program-G-01", "Program-G-02", "Program-G-03", "Program-G-04")
def test_get_program_happy_path(app_client, assigned_program):
    """
    GIVEN a doctor authenticated in dev mode and a program linked to that doctor's diagnostic
    WHEN GET /programs/{id} is requested
    THEN the API returns 200 with the ProgramOut contract.
    """
    response = app_client.get(f"/programs/{assigned_program.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(assigned_program.id)
    assert body["diagnostic_id"] == str(assigned_program.diagnostic_id)
    assert body["estado"] == "active"


@pytest.mark.ac("Program-G-01", "Program-G-02")
def test_get_program_not_found(app_client):
    """
    GIVEN an authenticated doctor and a program id that does not exist
    WHEN GET /programs/{id} is requested
    THEN the API returns 404 Program not found.
    """
    response = app_client.get(f"/programs/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Program not found"


@pytest.mark.ac("Program-G-01", "Program-G-02", "Program-G-03")
def test_get_program_forbidden_when_doctor_not_assigned(app_client, unassigned_program):
    """
    GIVEN an authenticated doctor and a program linked to another doctor's diagnostic
    WHEN GET /programs/{id} is requested
    THEN the API returns 403 authorization denied.
    """
    response = app_client.get(f"/programs/{unassigned_program.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Doctor not authorized for this diagnostic"


@pytest.mark.ac("Exercise-A-01", "Exercise-A-02", "Exercise-A-03", "Exercise-A-04", "Exercise-A-05", "Exercise-A-06")
def test_assign_exercise_happy_path(app_client, assigned_program, exercise):
    """
    GIVEN an authenticated doctor, an owned program, and an existing rehab exercise
    WHEN POST /programs/{id}/exercises is requested with exercise_id and pauta
    THEN the API returns 201 with ProgramExerciseOut and default status.
    """
    response = app_client.post(
        f"/programs/{assigned_program.id}/exercises",
        json={"exercise_id": str(exercise.id), "pauta": "2 series de 10"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["program_id"] == str(assigned_program.id)
    assert body["exercise_id"] == str(exercise.id)
    assert body["pauta"] == "2 series de 10"
    assert body["estado"] == "active"


@pytest.mark.ac("Exercise-A-01", "Exercise-A-02")
def test_assign_exercise_forbidden_when_doctor_not_assigned(app_client, unassigned_program, exercise):
    """
    GIVEN an authenticated doctor and a program linked to another doctor's diagnostic
    WHEN POST /programs/{id}/exercises is requested
    THEN the API returns 403 authorization denied.
    """
    response = app_client.post(
        f"/programs/{unassigned_program.id}/exercises",
        json={"exercise_id": str(exercise.id), "pauta": "No permitido"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Doctor not authorized for this diagnostic"


@pytest.mark.ac("Exercise-A-01", "Exercise-A-02", "Exercise-A-03", "Exercise-A-04")
def test_assign_exercise_not_found_when_exercise_missing(app_client, assigned_program):
    """
    GIVEN an authenticated doctor, an owned program, and a missing exercise_id
    WHEN POST /programs/{id}/exercises is requested
    THEN the API returns 404 Exercise not found.
    """
    response = app_client.post(
        f"/programs/{assigned_program.id}/exercises",
        json={"exercise_id": str(uuid4()), "pauta": "Ejercicio inexistente"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Exercise not found"


@pytest.mark.ac("Exercise-A-01", "Exercise-A-02")
def test_assign_exercise_not_found_when_program_missing(app_client, exercise):
    """
    GIVEN an authenticated doctor, an existing exercise, and a missing program id
    WHEN POST /programs/{id}/exercises is requested
    THEN the API returns 404 Program not found.
    """
    response = app_client.post(
        f"/programs/{uuid4()}/exercises",
        json={"exercise_id": str(exercise.id), "pauta": "Programa inexistente"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Program not found"


@pytest.mark.ac("Exercise-A-01", "Exercise-A-02", "Exercise-A-03", "Exercise-A-04", "Exercise-A-06", "Exercise-A-07")
def test_assign_exercise_allows_duplicate_assignment(app_client, assigned_program, exercise):
    """
    GIVEN an authenticated doctor, an owned program, and an exercise already assigned once
    WHEN POST /programs/{id}/exercises is requested again with the same exercise_id
    THEN the API returns 201 with a new ProgramExercise assignment.
    """
    payload = {"exercise_id": str(exercise.id), "pauta": "Duplicado permitido"}

    first = app_client.post(f"/programs/{assigned_program.id}/exercises", json=payload)
    second = app_client.post(f"/programs/{assigned_program.id}/exercises", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
@pytest.mark.ac("Exercise-A-01", "Exercise-A-02", "Exercise-A-03", "Exercise-A-04", "Exercise-A-05", "Exercise-A-06")
def test_legacy_assign_exercise_endpoint_delegates_to_service(app_client, assigned_program, exercise):
    """
    GIVEN the deprecated POST /programs/exercises compatibility endpoint
    WHEN a legacy payload with program_id, exercise_id, and pauta is submitted
    THEN the API delegates to the program service and returns ProgramExerciseOut.
    """
    response = app_client.post(
        "/programs/exercises",
        json={
            "program_id": str(assigned_program.id),
            "exercise_id": str(exercise.id),
            "pauta": "Compatibilidad legado",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["program_id"] == str(assigned_program.id)
    assert body["exercise_id"] == str(exercise.id)
    assert body["pauta"] == "Compatibilidad legado"

