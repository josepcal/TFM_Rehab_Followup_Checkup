"""DB-backed tests for the clinical service the worker uses to read a recording's context.

The worker used to reach into `clinical` with raw SQL to answer two questions before
processing a recording: what is the patient's pseudonym, and is consent still active. That
walk now lives in `RecordingContextService`, inside the domain that owns those tables —
`pseudonym_map` in particular, the map between a patient and their pseudonym.

These tests run against a real PostgreSQL under the `ftm_worker` role, because that is the
only place the behaviour is real: the unit tests for the worker use fakes and would not
notice an ORM query that quietly diverges from the SQL it replaced.

Run with a migrated test database:

    RUN_INTEGRATION=1 DATABASE_URL=postgresql://ftm_app:...@localhost:5432/appdb \
        api/.venv/bin/python -m pytest api/tests/integration/test_recording_context_service.py -q
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

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.clinical.recording_context_service import RecordingContextService  # noqa: E402


@pytest.fixture(scope="module")
def worker_session():
    """A session holding ftm_worker, rolled back at the end."""
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL or DATABASE_URL for integration tests.")
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    try:
        connection = engine.connect()
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL integration database is not reachable: {exc}")

    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    session.execute(text("SET ROLE ftm_worker"))
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module")
def a_recording(worker_session):
    recording_id = worker_session.execute(
        text("SELECT recording_id FROM recording.exercise_recording LIMIT 1")
    ).scalar()
    if recording_id is None:
        pytest.skip("No recordings in this database.")
    return recording_id


def test_pseudonym_matches_the_mapping_table(worker_session, a_recording):
    """The service must return the pseudonym clinical.pseudonym_map actually holds."""
    expected = worker_session.execute(
        text(
            """
            SELECT pm.pseudonym_id
            FROM recording.exercise_recording r
            JOIN clinical.program_exercise pe ON pe.program_exercise_id = r.program_exercise_id
            JOIN clinical.rehab_program rp    ON rp.rehab_program_id = pe.rehab_program_id
            JOIN clinical.diagnostic d        ON d.diagnostic_id = rp.diagnostic_id
            JOIN clinical.pseudonym_map pm    ON pm.patient_id = d.patient_id
            WHERE r.recording_id = :rid
            """
        ),
        {"rid": str(a_recording)},
    ).scalar()

    assert RecordingContextService(worker_session).pseudonym_for(a_recording) == expected


def test_consent_follows_the_most_recent_row(worker_session, a_recording):
    """patient_consent is append-only: the latest row decides, not "any active row".

    Reading it the other way lets an orphaned active row mask a later withdrawal, which
    would mean processing a patient's voice after they revoked consent (RGPD art. 7.3).
    """
    expected = bool(
        worker_session.execute(
            text(
                """
                SELECT pc.withdrawn_at IS NULL
                FROM recording.exercise_recording r
                JOIN clinical.program_exercise pe ON pe.program_exercise_id = r.program_exercise_id
                JOIN clinical.rehab_program rp    ON rp.rehab_program_id = pe.rehab_program_id
                JOIN clinical.diagnostic d        ON d.diagnostic_id = rp.diagnostic_id
                JOIN clinical.patient_consent pc
                  ON pc.patient_id = d.patient_id
                 AND pc.rehab_program_id = rp.rehab_program_id
                WHERE r.recording_id = :rid
                ORDER BY pc.granted_at DESC
                LIMIT 1
                """
            ),
            {"rid": str(a_recording)},
        ).scalar()
    )

    assert RecordingContextService(worker_session).has_active_consent(a_recording) == expected


def test_unknown_recording_has_no_pseudonym_and_no_consent(worker_session):
    """A missing recording must not be treated as consented."""
    service = RecordingContextService(worker_session)
    unknown = uuid.uuid4()
    assert service.pseudonym_for(unknown) is None
    assert service.has_active_consent(unknown) is False


def test_service_agrees_with_the_sql_it_replaced(worker_session):
    """Regression net for the refactor: same answers across every recording in the DB."""
    recordings = [
        row[0]
        for row in worker_session.execute(
            text("SELECT recording_id FROM recording.exercise_recording LIMIT 50")
        )
    ]
    if not recordings:
        pytest.skip("No recordings in this database.")

    service = RecordingContextService(worker_session)
    for recording_id in recordings:
        legacy_pseudonym = worker_session.execute(
            text(
                """
                SELECT pm.pseudonym_id
                FROM recording.exercise_recording r
                JOIN clinical.program_exercise pe ON pe.program_exercise_id = r.program_exercise_id
                JOIN clinical.rehab_program rp    ON rp.rehab_program_id = pe.rehab_program_id
                JOIN clinical.diagnostic d        ON d.diagnostic_id = rp.diagnostic_id
                JOIN clinical.pseudonym_map pm    ON pm.patient_id = d.patient_id
                WHERE r.recording_id = :rid
                """
            ),
            {"rid": str(recording_id)},
        ).scalar()
        assert service.pseudonym_for(recording_id) == legacy_pseudonym, recording_id
