"""DB-backed integration tests for program detail and exercise assignment endpoints.

These tests are opt-in so the default unit suite stays isolated from PostgreSQL.
Run with a migrated test database, for example:

    RUN_INTEGRATION=1 DATABASE_URL=postgresql://ftm_app:thisIsMyFTMAppDBPassword123@localhost:5432/appdb \
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
from fastapi import HTTPException  # noqa: E402
from sqlalchemy import create_engine, event, select, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.catalog.models import RehabExercise  # noqa: E402
from app.clinical.models import AppUser, Diagnostic, Doctor, Patient, ProgramExercise, RehabProgram  # noqa: E402
from app.clinical.program_access_service import ProgramExerciseAccessService  # noqa: E402
from app.recording.models import ExerciseRecording  # noqa: E402


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
            conn.execute(text("SET ROLE ftm_medical_specialist"))
            existing_columns = {
                (row.table_schema, row.table_name, row.column_name)
                for row in conn.execute(text("""
                    SELECT table_schema, table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema IN ('clinical', 'catalog', 'recording')
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
        ("recording", "exercise_recording", "recording_id"),
        ("recording", "exercise_recording", "content_type"),
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

    @event.listens_for(session, "after_begin")
    def apply_fixture_role(_session, _transaction, connection):
        connection.exec_driver_sql("SET LOCAL ROLE ftm_medical_specialist")

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


def test_patient_recording_rls_isolates_other_patient_rows(db_session):
    """A real ftm_patient role can read its recording but not another patient's."""
    db_session.execute(text("SET LOCAL ROLE ftm_medical_specialist"))
    suffix = uuid4().hex
    doctor = get_or_create_dev_doctor(db_session, suffix)
    exercise = RehabExercise(
        id=uuid4(),
        nombre=f"Grabacion {suffix}",
        descripcion="RLS recording integration exercise",
        tipo="phonation",
    )
    db_session.add(exercise)
    db_session.flush()

    recordings = []
    patients = []
    assignments = []
    for index in range(2):
        user = AppUser(
            identity_id=uuid4(),
            role="patient",
            external_subject=f"recording-patient-{index}-{suffix}",
        )
        patient = Patient(
            id=uuid4(),
            identity_id=user.identity_id,
            national_id=f"REC-{index}-{suffix}",
            nombre="Paciente",
            apellidos=f"Grabacion {index}",
        )
        db_session.add_all([user, patient])
        db_session.flush()
        diagnostic = Diagnostic(
            id=uuid4(),
            patient_id=patient.id,
            doctor_id=doctor.id,
            dolencia="Rehabilitacion voz",
            descripcion="Caso RLS",
            signature=f"recording-signature-{index}-{suffix}",
        )
        db_session.add(diagnostic)
        db_session.flush()
        program = RehabProgram(id=uuid4(), diagnostic_id=diagnostic.id, estado="active")
        db_session.add(program)
        db_session.flush()
        assignment = ProgramExercise(
            id=uuid4(),
            program_id=program.id,
            exercise_id=exercise.id,
            estado="active",
        )
        db_session.add(assignment)
        db_session.flush()
        recording = ExerciseRecording(
            recording_id=uuid4(),
            program_exercise_id=assignment.id,
            recorded_by=user.identity_id,
            media_kind="audio",
            media_uri=f"recordings/{assignment.id}/{uuid4()}.webm",
            content_type="audio/webm",
        )
        db_session.add(recording)
        db_session.flush()
        patients.append(patient)
        assignments.append(assignment)
        recordings.append(recording)

    own_recording_id = recordings[0].recording_id
    other_recording_id = recordings[1].recording_id
    patient_identity_id = patients[0].identity_id
    db_session.execute(text("RESET ROLE"))
    db_session.execute(
        text("SELECT set_config('app.identity_id', :identity_id, true)"),
        {"identity_id": str(patient_identity_id)},
    )
    db_session.execute(text("SET LOCAL ROLE ftm_patient"))

    assert db_session.scalar(
        select(ExerciseRecording.recording_id).where(ExerciseRecording.recording_id == own_recording_id)
    ) == own_recording_id
    assert db_session.scalar(
        select(ExerciseRecording.recording_id).where(ExerciseRecording.recording_id == other_recording_id)
    ) is None
    access_service = ProgramExerciseAccessService(db_session)
    principal = {"sub": f"recording-patient-0-{suffix}", "role": "patient"}
    assert access_service.require_access(assignments[0].id, principal) == assignments[0].id
    with pytest.raises(HTTPException) as exc_info:
        access_service.require_access(assignments[1].id, principal)
    assert exc_info.value.status_code == 404


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


@pytest.mark.ac("Program-C-01", "Program-C-02", "Program-C-03", "Program-C-04")
def test_create_program_with_metadata(app_client, assigned_program):
    """
    GIVEN an authenticated doctor and an owned diagnostic
    WHEN POST /programs/ is requested with optional plan metadata
    THEN the API creates a program and returns the metadata.
    """
    response = app_client.post(
        "/programs/",
        json={
            "diagnostic_id": str(assigned_program.diagnostic_id),
            "estado": "active",
            "name": "Plan de movilidad",
            "start_date": "2026-06-16T00:00:00Z",
            "end_date": "2026-07-16T00:00:00Z",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["diagnostic_id"] == str(assigned_program.diagnostic_id)
    assert body["name"] == "Plan de movilidad"
    assert body["start_date"]
    assert body["end_date"]


@pytest.mark.ac("Program-C-01", "Program-C-02")
def test_create_program_forbidden_when_diagnostic_not_owned(app_client, unassigned_program):
    """
    GIVEN an authenticated doctor and a diagnostic authored by another doctor
    WHEN POST /programs/ is requested for that diagnostic
    THEN the API returns 403 authorization denied.
    """
    response = app_client.post(
        "/programs/",
        json={"diagnostic_id": str(unassigned_program.diagnostic_id), "estado": "active"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Doctor not authorized for this diagnostic"


@pytest.mark.ac("Program-R-01", "Program-R-02", "Program-R-03", "Program-R-04", "Program-R-05")
def test_list_programs_doctor_wide_and_optional_filters(app_client, db_session, assigned_program, unassigned_program):
    """
    GIVEN programs owned by the authenticated doctor and another doctor
    WHEN GET /programs/ is requested with and without filters
    THEN the API returns only authorized programs and honors diagnostic/patient filters.
    """
    diagnostic = db_session.scalar(select(Diagnostic).where(Diagnostic.id == assigned_program.diagnostic_id))

    response = app_client.get("/programs/?limit=100&offset=0")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert str(assigned_program.id) in ids
    assert str(unassigned_program.id) not in ids

    by_diagnostic = app_client.get(f"/programs/?diagnostic_id={assigned_program.diagnostic_id}")
    assert by_diagnostic.status_code == 200
    assert {item["id"] for item in by_diagnostic.json()["data"]} == {str(assigned_program.id)}

    by_patient = app_client.get(f"/programs/?patient_id={diagnostic.patient_id}")
    assert by_patient.status_code == 200
    assert str(assigned_program.id) in {item["id"] for item in by_patient.json()["data"]}


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


@pytest.mark.ac("Exercise-L-01", "Exercise-L-02", "Exercise-L-03")
def test_list_program_exercises_happy_path(app_client, db_session, assigned_program, exercise):
    """
    GIVEN an authenticated doctor and an owned program with assigned exercises
    WHEN GET /programs/{id}/exercises is requested
    THEN the API returns a paginated list of ProgramExerciseOut rows.
    """
    assignment = ProgramExercise(
        program_id=assigned_program.id,
        exercise_id=exercise.id,
        pauta="3 series semanales",
    )
    db_session.add(assignment)
    db_session.commit()

    response = app_client.get(f"/programs/{assigned_program.id}/exercises?limit=20&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    rows = [item for item in body["data"] if item["id"] == str(assignment.id)]
    assert rows
    assert rows[0]["program_id"] == str(assigned_program.id)
    assert rows[0]["exercise_id"] == str(exercise.id)
    assert rows[0]["pauta"] == "3 series semanales"
    assert rows[0]["created_at"]


@pytest.mark.ac("Exercise-L-01", "Exercise-L-02")
def test_list_program_exercises_forbidden_when_program_not_owned(app_client, unassigned_program):
    """
    GIVEN an authenticated doctor and a program linked to another doctor's diagnostic
    WHEN GET /programs/{id}/exercises is requested
    THEN the API returns 403 authorization denied.
    """
    response = app_client.get(f"/programs/{unassigned_program.id}/exercises")

    assert response.status_code == 403
    assert response.json()["detail"] == "Doctor not authorized for this diagnostic"
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
