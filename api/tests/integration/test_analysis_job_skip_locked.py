"""PostgreSQL integration test for the UC-06 analysis job queue.

This test is opt-in because it needs a migrated PostgreSQL database and the
application DB roles/grants created by the SQL-first migrations.

Run it with, for example:

    RUN_INTEGRATION=1 DATABASE_URL=postgresql://ftm_app:thisIsMyFTMAppDBPassword123@localhost:5432/appdb \
        PYTHONPATH=api python -m pytest api/tests/integration/test_analysis_job_skip_locked.py -q
"""

from __future__ import annotations

import os
import threading
from queue import Queue
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.integration

if os.getenv("RUN_INTEGRATION") != "1":
    pytest.skip(
        "Set RUN_INTEGRATION=1 with a migrated PostgreSQL test DB to run.",
        allow_module_level=True,
    )

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import OperationalError, ProgrammingError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.jobs import AnalysisJob, claim_one  # noqa: E402


REQUIRED_ANALYSIS_JOB_COLUMNS = {
    "id",
    "recording_id",
    "function_name",
    "status",
    "attempts",
    "locked_at",
    "updated_at",
}


def _set_local_role(conn_or_session, role: str) -> None:
    """Apply the DB role used by the SQL-first RLS/grant model."""
    conn_or_session.execute(text("SELECT set_config('app.user', 'integration-test', true)"))
    conn_or_session.execute(text("SELECT set_config('app.role', :role, true)"), {"role": role})
    conn_or_session.execute(text(f"SET LOCAL ROLE {role}"))


@pytest.fixture(scope="session")
def integration_engine():
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL or DATABASE_URL for integration tests.")

    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    try:
        with engine.connect() as conn:
            if conn.dialect.name != "postgresql":
                pytest.skip("SKIP LOCKED integration test requires PostgreSQL.")
            conn.execute(text("SELECT 1"))
            existing_columns = {
                row.column_name
                for row in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'metrics'
                          AND table_name = 'analysis_job'
                        """
                    )
                )
            }
    except (OperationalError, ProgrammingError) as exc:
        pytest.skip(f"PostgreSQL integration database is not reachable or migrated: {exc}")

    missing_columns = sorted(REQUIRED_ANALYSIS_JOB_COLUMNS - existing_columns)
    if missing_columns:
        pytest.skip(
            "PostgreSQL schema does not match the UC-06 analysis_job queue; "
            f"missing columns: {', '.join(missing_columns)}"
        )

    return engine


@pytest.fixture
def db_session_factory(integration_engine):
    return sessionmaker(bind=integration_engine, autoflush=False, expire_on_commit=False, future=True)


def _insert_minimal_recording_graph(conn) -> UUID:
    """Create the minimal FK graph needed by metrics.analysis_job.recording_id.

    The current SQL-first schema links analysis_job -> exercise_recording ->
    program_exercise -> rehab_program -> diagnostic -> patient/doctor. Keeping
    the setup here makes the concurrency test independent from seed data.
    """
    suffix = uuid4().hex
    patient_identity_id = uuid4()
    doctor_identity_id = uuid4()
    patient_id = uuid4()
    doctor_id = uuid4()
    diagnostic_id = uuid4()
    exercise_id = uuid4()
    program_id = uuid4()
    program_exercise_id = uuid4()
    recording_id = uuid4()

    _set_local_role(conn, "ftm_medical_specialist")

    conn.execute(
        text(
            """
            INSERT INTO clinical.app_user (identity_id, role, external_subject)
            VALUES
              (:patient_identity_id, 'patient', :patient_subject),
              (:doctor_identity_id, 'medical', :doctor_subject)
            """
        ),
        {
            "patient_identity_id": patient_identity_id,
            "doctor_identity_id": doctor_identity_id,
            "patient_subject": f"skip-locked-patient-{suffix}",
            "doctor_subject": f"skip-locked-doctor-{suffix}",
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO clinical.patient
              (patient_id, identity_id, national_id, first_name, last_name)
            VALUES
              (:patient_id, :patient_identity_id, :national_id, 'Paciente', 'SkipLocked')
            """
        ),
        {
            "patient_id": patient_id,
            "patient_identity_id": patient_identity_id,
            "national_id": f"SKIP-{suffix}",
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO clinical.doctor
              (doctor_id, identity_id, colegiado_id, doctor_type, first_name, last_name)
            VALUES
              (:doctor_id, :doctor_identity_id, :colegiado_id, 'gp', 'Doctor', 'SkipLocked')
            """
        ),
        {
            "doctor_id": doctor_id,
            "doctor_identity_id": doctor_identity_id,
            "colegiado_id": f"COL-SKIP-{suffix}",
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO clinical.diagnostic
              (diagnostic_id, patient_id, doctor_id, dolencia, description, signature)
            VALUES
              (:diagnostic_id, :patient_id, :doctor_id, 'Concurrencia', 'SKIP LOCKED test', :signature)
            """
        ),
        {
            "diagnostic_id": diagnostic_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "signature": f"skip-locked-{suffix}",
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO clinical.rehab_exercise (rh_exercise_id, type, description)
            VALUES (:exercise_id, 'voice-test', 'UC-06 SKIP LOCKED integration test')
            """
        ),
        {"exercise_id": exercise_id},
    )
    conn.execute(
        text(
            """
            INSERT INTO clinical.rehab_program (rehab_program_id, diagnostic_id, status)
            VALUES (:program_id, :diagnostic_id, 'active')
            """
        ),
        {"program_id": program_id, "diagnostic_id": diagnostic_id},
    )
    conn.execute(
        text(
            """
            INSERT INTO clinical.program_exercise
              (program_exercise_id, rehab_program_id, rh_exercise_id, status)
            VALUES
              (:program_exercise_id, :program_id, :exercise_id, 'active')
            """
        ),
        {
            "program_exercise_id": program_exercise_id,
            "program_id": program_id,
            "exercise_id": exercise_id,
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO recording.exercise_recording
              (recording_id, program_exercise_id, recorded_by, media_kind, media_uri, recording_date)
            VALUES
              (:recording_id, :program_exercise_id, :patient_identity_id, 'audio', :media_uri, CURRENT_DATE)
            """
        ),
        {
            "recording_id": recording_id,
            "program_exercise_id": program_exercise_id,
            "patient_identity_id": patient_identity_id,
            "media_uri": f"integration/skip-locked/{suffix}.wav",
        },
    )

    return recording_id


@pytest.fixture
def pending_job_id(integration_engine) -> UUID:
    with integration_engine.begin() as conn:
        recording_id = _insert_minimal_recording_graph(conn)
        _set_local_role(conn, "ftm_worker")
        job_id = uuid4()
        conn.execute(
            text(
                """
                INSERT INTO metrics.analysis_job
                  (id, recording_id, function_name, status, attempts)
                VALUES
                  (:job_id, :recording_id, 'integration_skip_locked_v1', 'pending', 0)
                """
            ),
            {"job_id": job_id, "recording_id": recording_id},
        )
    return job_id


def test_skip_locked_allows_two_workers_to_claim_one_job_exactly_once(
    db_session_factory,
    pending_job_id: UUID,
):
    """Two real DB sessions race for one job; only one can lock and finish it."""
    start_together = threading.Barrier(2)
    both_attempted_claim = threading.Barrier(2)
    results: Queue[tuple[str, UUID | None] | BaseException] = Queue()

    def worker_claim(worker_name: str) -> None:
        session = db_session_factory()
        try:
            session.begin()
            _set_local_role(session, "ftm_worker")
            start_together.wait(timeout=5)

            job: AnalysisJob | None = claim_one(session)
            claimed_id = job.id if job is not None else None
            if job is not None:
                # Simulate the minimal successful state transition while the
                # row lock is still held. The other worker must still skip it.
                job.status = "done"
                session.flush()

            both_attempted_claim.wait(timeout=5)
            session.commit()
            results.put((worker_name, claimed_id))
        except BaseException as exc:  # noqa: BLE001 - propagate thread failures to pytest
            session.rollback()
            results.put(exc)
        finally:
            session.close()

    threads = [
        threading.Thread(target=worker_claim, args=("worker-a",)),
        threading.Thread(target=worker_claim, args=("worker-b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads), "worker threads did not finish"

    worker_results = [results.get_nowait() for _ in threads]
    failures = [result for result in worker_results if isinstance(result, BaseException)]
    assert not failures, failures

    claimed_ids = [claimed_id for _worker_name, claimed_id in worker_results if claimed_id is not None]
    assert claimed_ids == [pending_job_id]

    verification = db_session_factory()
    try:
        verification.begin()
        _set_local_role(verification, "ftm_worker")
        row = verification.execute(
            text(
                """
                SELECT status, attempts
                FROM metrics.analysis_job
                WHERE id = :job_id
                """
            ),
            {"job_id": pending_job_id},
        ).one()
        verification.commit()
    finally:
        verification.close()

    assert row.status == "done"
    assert row.attempts == 1
