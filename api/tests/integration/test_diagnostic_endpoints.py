"""DB-backed integration tests for diagnostic endpoints.

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

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.clinical.models import AppUser, Diagnostic, Doctor, Patient


DEV_DOCTOR_SUB = "dev-user"


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
                    WHERE table_schema = 'clinical'
                """))
            }
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL integration database is not reachable: {exc}")

    required_columns = {
        ("clinical", "app_user", "identity_id"),
        ("clinical", "patient", "patient_id"),
        ("clinical", "doctor", "doctor_id"),
        ("clinical", "diagnostic", "diagnostic_id"),
    }
    missing_columns = sorted(required_columns - existing_columns)
    if missing_columns:
        missing = ", ".join(".".join(column) for column in missing_columns)
        pytest.skip(f"PostgreSQL schema does not match diagnostic ORM mapping: {missing}")

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


def get_or_create_dev_doctor(db_session, suffix: str) -> Doctor:
    doctor_user = db_session.scalar(select(AppUser).where(AppUser.external_subject == DEV_DOCTOR_SUB))
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


@pytest.fixture
def patient(db_session):
    suffix = uuid4().hex
    patient_user = AppUser(identity_id=uuid4(), role="patient", external_subject=f"patient-diagnostic-{suffix}")
    patient = Patient(
        id=uuid4(),
        identity_id=patient_user.identity_id,
        national_id=f"DIAG-NID-{suffix}",
        nombre="Paciente",
        apellidos="Diagnostico",
    )
    db_session.add_all([patient_user, patient])
    db_session.flush()
    db_session.commit()
    return patient


@pytest.fixture
def owned_diagnostic(db_session, patient):
    suffix = uuid4().hex
    doctor = get_or_create_dev_doctor(db_session, suffix)
    diagnostic = Diagnostic(
        id=uuid4(),
        patient_id=patient.id,
        doctor_id=doctor.id,
        dolencia="Dolor cervical",
        descripcion="Diagnostico de integracion",
        signature=f"signature-{suffix}",
    )
    db_session.add(diagnostic)
    db_session.flush()
    db_session.commit()
    return diagnostic


@pytest.fixture
def unowned_diagnostic(db_session, patient):
    suffix = uuid4().hex
    doctor_user = AppUser(identity_id=uuid4(), role="medical", external_subject=f"other-diagnostic-doctor-{suffix}")
    doctor = Doctor(
        id=uuid4(),
        identity_id=doctor_user.identity_id,
        colegiado_id=f"OTHER-DIAG-{suffix}",
        doctor_type="gp",
        nombre="Doctor",
        apellidos="Otro",
    )
    db_session.add_all([doctor_user, doctor])
    db_session.flush()
    diagnostic = Diagnostic(
        id=uuid4(),
        patient_id=patient.id,
        doctor_id=doctor.id,
        dolencia="Dolor lumbar",
        descripcion="No pertenece al dev doctor",
        signature=f"signature-{suffix}",
    )
    db_session.add(diagnostic)
    db_session.flush()
    db_session.commit()
    return diagnostic


@pytest.mark.ac("Diagnostic-C-01", "Diagnostic-C-02", "Diagnostic-C-04", "Diagnostic-C-07", "Diagnostic-C-09", "Diagnostic-C-10")
def test_create_diagnostic_happy_path(app_client, patient):
    """
    GIVEN an authenticated doctor, an existing patient, and a valid diagnostic payload
    WHEN POST /diagnostics is requested
    THEN the API returns 201 with DiagnosticOut and the doctor id is injected by the backend.
    """
    response = app_client.post(
        "/diagnostics/",
        json={"patient_id": str(patient.id), "dolencia": "Dolor hombro", "descripcion": "Alta movilidad limitada"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["patient_id"] == str(patient.id)
    assert body["dolencia"] == "Dolor hombro"
    assert body["doctor_id"]
    assert body["created_at"]


@pytest.mark.ac("Diagnostic-G-01", "Diagnostic-G-02", "Diagnostic-G-03", "Diagnostic-G-04")
def test_get_diagnostic_happy_path(app_client, owned_diagnostic):
    """
    GIVEN an authenticated doctor and a diagnostic authored by that doctor
    WHEN GET /diagnostics/{id} is requested
    THEN the API returns 200 with the DiagnosticOut contract.
    """
    response = app_client.get(f"/diagnostics/{owned_diagnostic.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(owned_diagnostic.id)
    assert body["descripcion"] == owned_diagnostic.descripcion


@pytest.mark.ac("Diagnostic-G-01", "Diagnostic-G-02")
def test_get_diagnostic_not_found(app_client):
    """
    GIVEN an authenticated doctor and a diagnostic id that does not exist
    WHEN GET /diagnostics/{id} is requested
    THEN the API returns 404 Diagnostic not found.
    """
    response = app_client.get(f"/diagnostics/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Diagnostic not found"


@pytest.mark.ac("Diagnostic-G-01", "Diagnostic-G-02", "Diagnostic-G-03")
def test_get_diagnostic_forbidden_when_not_author(app_client, unowned_diagnostic):
    """
    GIVEN an authenticated doctor and a diagnostic authored by another doctor
    WHEN GET /diagnostics/{id} is requested
    THEN the API returns 403 authorization denied.
    """
    response = app_client.get(f"/diagnostics/{unowned_diagnostic.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Doctor not authorized for this diagnostic"


@pytest.mark.ac("Diagnostic-U-01", "Diagnostic-U-02", "Diagnostic-U-03", "Diagnostic-U-04", "Diagnostic-U-07")
def test_patch_diagnostic_updates_only_supplied_fields(app_client, owned_diagnostic):
    """
    GIVEN an authenticated doctor and a diagnostic authored by that doctor
    WHEN PATCH /diagnostics/{id} is requested with only dolencia
    THEN the API returns 200 with dolencia changed and descripcion unchanged.
    """
    response = app_client.patch(
        f"/diagnostics/{owned_diagnostic.id}",
        json={"dolencia": "Dolor cervical actualizado"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dolencia"] == "Dolor cervical actualizado"
    assert body["descripcion"] == owned_diagnostic.descripcion


@pytest.mark.ac("Diagnostic-U-01", "Diagnostic-U-02", "Diagnostic-U-03", "Diagnostic-U-04", "Diagnostic-U-07")
def test_patch_diagnostic_updates_description_only(app_client, owned_diagnostic):
    """
    GIVEN an authenticated doctor and a diagnostic authored by that doctor
    WHEN PATCH /diagnostics/{id} is requested with only descripcion
    THEN the API returns 200 with descripcion changed and dolencia unchanged.
    """
    response = app_client.patch(
        f"/diagnostics/{owned_diagnostic.id}",
        json={"descripcion": "Descripcion actualizada"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["descripcion"] == "Descripcion actualizada"
    assert body["dolencia"] == owned_diagnostic.dolencia


@pytest.mark.ac("Diagnostic-R-01", "Diagnostic-R-03", "Diagnostic-R-06", "Diagnostic-R-07", "Diagnostic-R-08")
def test_list_diagnostics_contains_owned_diagnostic(app_client, owned_diagnostic):
    """
    GIVEN an authenticated doctor with at least one authored diagnostic
    WHEN GET /diagnostics is requested
    THEN the API returns a paginated response containing that diagnostic.
    """
    response = app_client.get("/diagnostics/?limit=20&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body["data"]} >= {str(owned_diagnostic.id)}
    assert body["limit"] == 20
    assert body["offset"] == 0
