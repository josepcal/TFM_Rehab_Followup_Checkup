"""DB-backed proof that the anonymisation boundary is enforced, not just documented.

The `ftm_ai` role is the system's privacy-by-design control: whatever assembles a payload
for the LLM must be unable to reach identity data *at the database*, so a future change
cannot quietly widen the payload. That guarantee is worthless unless the role is actually
assumed at runtime and its limits are tested against a real PostgreSQL.

These tests assert both halves:

1. Under `ftm_ai`, identity is unreachable — `clinical.pseudonym_map`, `clinical.patient`,
   and even the raw `metrics.metric_result` are denied by the grants.
2. `load_ai_payload` still works through the narrow door (`metrics.v_ai_payload`) and the
   payload it produces carries no identifying field.

Run with a migrated test database:

    RUN_INTEGRATION=1 DATABASE_URL=postgresql://ftm_app:...@localhost:5432/appdb \
        api/.venv/bin/python -m pytest api/tests/integration/test_ai_boundary.py -q
"""

import json
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
from sqlalchemy.exc import OperationalError, ProgrammingError  # noqa: E402

from app.ai.payload_service import load_ai_payload  # noqa: E402
from app.db import ai_session  # noqa: E402

# Tables that identify a patient, or that would let the AI side re-identify one.
# metric_result is included on purpose: it is the raw table behind v_ai_payload and
# carries result_id, the key that links a metric back to a recording and a patient.
FORBIDDEN_TO_AI = [
    "clinical.pseudonym_map",
    "clinical.patient",
    "clinical.app_user",
    "clinical.diagnostic",
    "clinical.doctor",
    "recording.exercise_recording",
    "metrics.metric_result",
]

IDENTIFYING_SUBSTRINGS = [
    "patient",
    "national",
    "first_name",
    "last_name",
    "identity",
    "doctor",
    "recording_id",
    "result_id",
]


@pytest.fixture(scope="module")
def engine():
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL or DATABASE_URL for integration tests.")
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL integration database is not reachable: {exc}")
    return engine


class TestBoundaryDeniesIdentity:
    """Under ftm_ai the database itself must refuse identity data."""

    @pytest.mark.parametrize("table", FORBIDDEN_TO_AI)
    def test_ai_role_cannot_read(self, table):
        session = ai_session()
        try:
            with pytest.raises(ProgrammingError) as exc:
                session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
            assert "permission denied" in str(exc.value).lower(), (
                f"{table} did not deny ftm_ai — the anonymisation boundary is open"
            )
        finally:
            session.rollback()
            session.close()

    def test_ai_role_is_actually_assumed(self):
        """A session that silently stayed on ftm_app would pass the tests above by luck."""
        session = ai_session()
        try:
            assert session.execute(text("SELECT current_user")).scalar() == "ftm_ai"
        finally:
            session.rollback()
            session.close()


class TestBoundaryAllowsMetrics:
    """The narrow door must stay open, or the boundary is just a wall."""

    def test_ai_role_can_read_the_view(self):
        session = ai_session()
        try:
            session.execute(text("SELECT 1 FROM metrics.v_ai_payload LIMIT 1"))
        finally:
            session.rollback()
            session.close()

    def test_payload_has_no_identifying_field(self, engine):
        with engine.connect() as conn:
            conn.execute(text("SET ROLE ftm_ai"))
            row = conn.execute(
                text(
                    "SELECT pseudonym_id, exercise FROM metrics.v_ai_payload "
                    "GROUP BY 1, 2 LIMIT 1"
                )
            ).one_or_none()
        if row is None:
            pytest.skip("No analysed metrics in this database to build a payload from.")

        payload = load_ai_payload(uuid.UUID(str(row.pseudonym_id)), row.exercise)
        assert payload is not None
        assert payload["pseudonym_id"] == str(row.pseudonym_id)
        assert payload["current_metrics"], "payload carries no metrics"

        blob = json.dumps(payload).lower()
        leaked = [term for term in IDENTIFYING_SUBSTRINGS if term in blob]
        assert not leaked, f"payload leaks identifying fields: {leaked}"

    def test_unknown_pseudonym_yields_none(self):
        assert load_ai_payload(uuid.uuid4(), "dysarthria_analysis_v1") is None
