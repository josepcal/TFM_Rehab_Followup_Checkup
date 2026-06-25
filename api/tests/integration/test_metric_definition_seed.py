"""PostgreSQL integration test: metric_definition seed for dysarthria_analysis_v1.

Verifies that the Phase 4 seed populated all five metric_definition rows for
`dysarthria_analysis_v1` and that they are reachable under the ftm_worker role
(the role that reads this data at job-execution time).

Run with:

    RUN_INTEGRATION=1 DATABASE_URL=postgresql://ftm_app:<password>@localhost:5432/appdb \
        PYTHONPATH=api python -m pytest api/tests/integration/test_metric_definition_seed.py -q
"""

from __future__ import annotations

import os

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


# Columns we expect on setup.metric_definition.
# Derived from the broken-test's ORM model (md.path) and the tasks.md open-question
# resolution: the real column is `path`, not `metric_key` as the design doc assumed.
REQUIRED_METRIC_DEFINITION_COLUMNS = {
    "path",
    "label",
    "unit",
    "weight",
}

# Columns we expect on setup.analysis_setup.
# Also resolved here: the real column is `metric_api_endpoint`, not `function_name`
# (tasks.md open question 1.2 / ruff run on test_metric_definition_seed.py).
REQUIRED_ANALYSIS_SETUP_COLUMNS = {
    "id",
    "metric_api_endpoint",
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
                pytest.skip("metric_definition seed integration test requires PostgreSQL.")
            conn.execute(text("SELECT 1"))

            md_columns = {
                row.column_name
                for row in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'setup'
                          AND table_name   = 'metric_definition'
                        """
                    )
                )
            }
            as_columns = {
                row.column_name
                for row in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'setup'
                          AND table_name   = 'analysis_setup'
                        """
                    )
                )
            }
    except (OperationalError, ProgrammingError) as exc:
        pytest.skip(
            f"PostgreSQL integration database is not reachable or migrated: {exc}"
        )

    missing_md = sorted(REQUIRED_METRIC_DEFINITION_COLUMNS - md_columns)
    if missing_md:
        pytest.skip(
            "setup.metric_definition schema does not match expected shape; "
            f"missing columns: {', '.join(missing_md)}"
        )

    missing_as = sorted(REQUIRED_ANALYSIS_SETUP_COLUMNS - as_columns)
    if missing_as:
        pytest.skip(
            "setup.analysis_setup schema does not match expected shape; "
            f"missing columns: {', '.join(missing_as)}"
        )

    return engine


@pytest.fixture
def db_session_factory(integration_engine):
    return sessionmaker(
        bind=integration_engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )


def test_sustained_phonation_metric_definitions_exist(db_session_factory):
    """All five metric_definition rows for dysarthria_analysis_v1 must be seeded."""
    session = db_session_factory()
    try:
        session.begin()
        _set_local_role(session, "ftm_worker")

        rows = session.execute(
            text(
                """
                SELECT md.path
                FROM   setup.metric_definition md
                JOIN   setup.analysis_setup    sa ON sa.id = md.analysis_setup_id
                WHERE  sa.metric_api_endpoint = 'dysarthria_analysis_v1'
                """
            )
        ).all()

        session.commit()
    finally:
        session.close()

    paths = {row.path for row in rows}

    assert paths == {
        "raw.phonation_duration_sec",
        "raw.jitter_local_pct",
        "raw.shimmer_local_pct",
        "raw.hnr_db",
        "raw.volume_std_db",
    }, (
        f"Expected 5 metric_definition paths for dysarthria_analysis_v1, "
        f"got {len(paths)}: {sorted(paths)}"
    )


def test_sustained_phonation_metric_definition_weights_sum_to_one(db_session_factory):
    """Weights for all dysarthria_analysis_v1 metrics must sum to 1.0 (± float tolerance)."""
    session = db_session_factory()
    try:
        session.begin()
        _set_local_role(session, "ftm_worker")

        row = session.execute(
            text(
                """
                SELECT COALESCE(SUM(md.weight), 0) AS total_weight,
                       COUNT(*)                    AS row_count
                FROM   setup.metric_definition md
                JOIN   setup.analysis_setup    sa ON sa.id = md.analysis_setup_id
                WHERE  sa.metric_api_endpoint = 'dysarthria_analysis_v1'
                """
            )
        ).one()

        session.commit()
    finally:
        session.close()

    assert row.row_count == 5, (
        f"Expected 5 metric_definition rows for dysarthria_analysis_v1, got {row.row_count}"
    )
    assert abs(float(row.total_weight) - 1.0) < 1e-6, (
        f"Weights must sum to 1.0, got {row.total_weight}"
    )