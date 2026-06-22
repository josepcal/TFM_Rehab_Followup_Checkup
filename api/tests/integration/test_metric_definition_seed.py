"""DB-backed integration test for AnalysisSetup metric definitions seed.

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

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import sessionmaker, Session  # noqa: E402

from app.analysis.models import AnalysisSetup  # noqa: E402


@pytest.fixture(scope="module")
def integration_engine():
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL or DATABASE_URL for integration tests.")

    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    return engine


@pytest.fixture
def db_session(integration_engine) -> Session:
    """Provide a SQLAlchemy session for the integration test."""
    SessionLocal = sessionmaker(bind=integration_engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_sustained_phonation_metric_definitions_exist(db_session):
    setup = (
        db_session.query(AnalysisSetup)
        .filter(
            AnalysisSetup.metric_api_endpoint == "sustained_phonation_v1"
        )
        .one()
    )

    paths = {md.path for md in setup.metric_definitions}

    assert paths == {
        "raw.phonation_duration_sec",
        "raw.jitter_local_pct",
        "raw.shimmer_local_pct",
        "raw.hnr_db",
        "raw.volume_std_db",
    }
