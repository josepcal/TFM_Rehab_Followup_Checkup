"""DB-backed object-level authorization tests for reports and follow-up check-ups.

Regression cover for a real BOLA (OWASP A01): before ``ProgramAccessService`` was
wired in, any authenticated doctor could read, modify and delete the clinical
reports of patients belonging to another doctor. RLS does not stop this — the
staff policies on ``exercise_report`` and ``followup_checkup`` are ``USING (true)``
— so the guard in the routers is the only control, and it needs a real database
to be tested honestly.

Run with a migrated test database:

    RUN_INTEGRATION=1 DATABASE_URL=postgresql://ftm_app:...@localhost:5432/appdb \
        api/.venv/bin/python -m pytest api/tests/integration -q
"""

import os
import uuid

import pytest

pytestmark = pytest.mark.integration

if os.getenv("RUN_INTEGRATION") != "1":
    pytest.skip(
        "Set RUN_INTEGRATION=1 with a migrated PostgreSQL test DB to run.",
        allow_module_level=True,
    )

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.db as app_db  # noqa: E402
from app.auth import current_principal  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def connection():
    """A single transaction, rolled back at the end — the DB is left untouched."""
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL or DATABASE_URL for integration tests.")

    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    try:
        conn = engine.connect()
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL integration database is not reachable: {exc}")

    transaction = conn.begin()
    conn.execute(text("SET ROLE ftm_medical_specialist"))
    yield conn
    transaction.rollback()
    conn.close()


@pytest.fixture(scope="module")
def fixture_data(connection):
    """One patient with a report and a check-up, owned by doctor A.

    Doctor B exists but is linked to nothing: no diagnostic, no program.
    """
    conn = connection

    def new_doctor(tag: str) -> uuid.UUID:
        identity_id = conn.execute(text("""
            INSERT INTO clinical.app_user (role, external_subject, status)
            VALUES ('medical', :sub, 'active') RETURNING identity_id
        """), {"sub": f"idp|{tag}-{uuid.uuid4().hex[:8]}"}).scalar_one()
        doctor_id = conn.execute(text("""
            INSERT INTO clinical.doctor (identity_id, colegiado_id, doctor_type, first_name, last_name)
            VALUES (:iid, :col, 'medical_specialist', :tag, 'Test')
            RETURNING doctor_id
        """), {"iid": identity_id, "col": f"COL{uuid.uuid4().hex[:8]}", "tag": tag}).scalar_one()
        subject = conn.execute(text(
            "SELECT external_subject FROM clinical.app_user WHERE identity_id = :i"
        ), {"i": identity_id}).scalar_one()
        return doctor_id, subject

    owner_id, owner_sub = new_doctor("owner")
    intruder_id, intruder_sub = new_doctor("intruder")

    patient_identity = conn.execute(text("""
        INSERT INTO clinical.app_user (role, external_subject, status)
        VALUES ('patient', :sub, 'active') RETURNING identity_id
    """), {"sub": f"idp|patient-{uuid.uuid4().hex[:8]}"}).scalar_one()
    # national_id is a Fernet-encrypted column; its plaintext is irrelevant to
    # authorization, so any opaque value satisfies the NOT NULL constraint here.
    patient_id = conn.execute(text("""
        INSERT INTO clinical.patient (identity_id, first_name, last_name, national_id)
        VALUES (:i, 'Patient', 'Test', :nid) RETURNING patient_id
    """), {"i": patient_identity, "nid": f"enc-{uuid.uuid4().hex}"}).scalar_one()

    diagnostic_id = conn.execute(text("""
        INSERT INTO clinical.diagnostic (patient_id, doctor_id, dolencia, signature)
        VALUES (:p, :d, 'test', :sig) RETURNING diagnostic_id
    """), {"p": patient_id, "d": owner_id, "sig": f"sig-{uuid.uuid4().hex}"}).scalar_one()
    program_id = conn.execute(text("""
        INSERT INTO clinical.rehab_program (diagnostic_id, physiotherapist_id)
        VALUES (:dg, :d) RETURNING rehab_program_id
    """), {"dg": diagnostic_id, "d": owner_id}).scalar_one()
    exercise_id = conn.execute(text(
        "SELECT rh_exercise_id FROM clinical.rehab_exercise LIMIT 1"
    )).scalar_one_or_none()
    if exercise_id is None:
        pytest.skip("No seeded rehab_exercise to attach the program to.")
    program_exercise_id = conn.execute(text("""
        INSERT INTO clinical.program_exercise (rehab_program_id, rh_exercise_id)
        VALUES (:p, :e) RETURNING program_exercise_id
    """), {"p": program_id, "e": exercise_id}).scalar_one()

    report_id = conn.execute(text("""
        INSERT INTO clinical.exercise_report
            (rehab_program_id, program_exercise_id, period_start, period_end, summary, created_by)
        VALUES (:p, :pe, '2026-01-01', '2026-03-31', 'owner summary', :d)
        RETURNING exercise_report_id
    """), {"p": program_id, "pe": program_exercise_id, "d": owner_id}).scalar_one()
    checkup_id = conn.execute(text("""
        INSERT INTO clinical.followup_checkup
            (rehab_program_id, patient_id, period_start, period_end, summary, created_by)
        VALUES (:p, :pat, '2026-01-01', '2026-03-31', 'owner checkup', :d)
        RETURNING followup_checkup_id
    """), {"p": program_id, "pat": patient_id, "d": owner_id}).scalar_one()

    return {
        "owner_sub": owner_sub,
        "intruder_sub": intruder_sub,
        "program_id": program_id,
        "report_id": report_id,
        "checkup_id": checkup_id,
        "program_exercise_id": program_exercise_id,
    }


@pytest.fixture
def client_as(connection):
    """TestClient bound to the fixture transaction, acting as a given principal."""
    TestSession = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    sessions = []

    def _client(subject: str, role: str) -> TestClient:
        session = TestSession()
        app_db._apply_rls(session, {"sub": subject, "role": role})
        sessions.append(session)
        app.dependency_overrides[app_db.get_db] = lambda: session
        app.dependency_overrides[current_principal] = lambda: {"sub": subject, "role": role}
        return TestClient(app, raise_server_exceptions=False)

    yield _client
    app.dependency_overrides.clear()
    for session in sessions:
        session.close()


class TestUnlinkedDoctorIsRejected:
    """A doctor with no link to the program must not reach its clinical data."""

    def test_cannot_read_report(self, client_as, fixture_data):
        client = client_as(fixture_data["intruder_sub"], "medical")
        assert client.get(f"/reports/{fixture_data['report_id']}").status_code == 404

    def test_cannot_modify_report(self, client_as, fixture_data, connection):
        client = client_as(fixture_data["intruder_sub"], "medical")
        response = client.patch(
            f"/reports/{fixture_data['report_id']}", json={"summary": "tampered"}
        )
        assert response.status_code == 404

        summary = connection.execute(text(
            "SELECT summary FROM clinical.exercise_report WHERE exercise_report_id = :r"
        ), {"r": fixture_data["report_id"]}).scalar_one()
        assert summary == "owner summary"

    def test_cannot_delete_report(self, client_as, fixture_data):
        client = client_as(fixture_data["intruder_sub"], "medical")
        assert client.delete(f"/reports/{fixture_data['report_id']}").status_code == 404

    def test_cannot_list_program_reports(self, client_as, fixture_data):
        client = client_as(fixture_data["intruder_sub"], "medical")
        assert client.get(
            f"/programs/{fixture_data['program_id']}/reports"
        ).status_code == 404

    def test_cannot_read_checkup(self, client_as, fixture_data):
        client = client_as(fixture_data["intruder_sub"], "medical")
        assert client.get(
            f"/followup-checkups/{fixture_data['checkup_id']}"
        ).status_code == 404

    def test_cannot_create_report_on_someone_elses_program(self, client_as, fixture_data):
        client = client_as(fixture_data["intruder_sub"], "medical")
        response = client.post("/reports", json={
            "program_exercise_id": str(fixture_data["program_exercise_id"]),
            # A non-empty list: ReportIn rejects an empty one at validation time,
            # which would mask the authorization check under a 422.
            "recording_ids": [str(uuid.uuid4())],
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "summary": "intruder report",
        })
        assert response.status_code == 404


class TestOwningDoctorStillHasAccess:
    """The guard must not lock out the doctor who owns the case."""

    def test_can_read_report(self, client_as, fixture_data):
        client = client_as(fixture_data["owner_sub"], "medical")
        response = client.get(f"/reports/{fixture_data['report_id']}")
        assert response.status_code == 200
        assert response.json()["summary"] == "owner summary"

    def test_can_list_program_reports(self, client_as, fixture_data):
        client = client_as(fixture_data["owner_sub"], "medical")
        response = client.get(f"/programs/{fixture_data['program_id']}/reports")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_can_read_checkup(self, client_as, fixture_data):
        client = client_as(fixture_data["owner_sub"], "medical")
        response = client.get(f"/followup-checkups/{fixture_data['checkup_id']}")
        assert response.status_code == 200


class TestReadsAreAudited:
    """Marked GETs write a 'read' row: served → success, snooping (404) → denied."""

    @staticmethod
    def _count(connection, path: str, outcome: str) -> int:
        # SELECT on audit.event_log is granted to the medical role (migration 0013).
        connection.execute(text("SET ROLE ftm_medical_specialist"))
        n = connection.execute(text("""
            SELECT count(*) FROM audit.event_log
            WHERE entity_type = :p AND action = 'read' AND outcome = :o
        """), {"p": path, "o": outcome}).scalar_one()
        return n

    def test_served_read_is_audited_success(self, client_as, fixture_data, connection):
        path = f"/reports/{fixture_data['report_id']}"
        before = self._count(connection, path, "success")
        client = client_as(fixture_data["owner_sub"], "medical")
        assert client.get(path).status_code == 200
        assert self._count(connection, path, "success") == before + 1

    def test_snooping_read_is_audited_denied(self, client_as, fixture_data, connection):
        path = f"/reports/{fixture_data['report_id']}"
        before = self._count(connection, path, "denied")
        client = client_as(fixture_data["intruder_sub"], "medical")
        assert client.get(path).status_code == 404
        assert self._count(connection, path, "denied") == before + 1
