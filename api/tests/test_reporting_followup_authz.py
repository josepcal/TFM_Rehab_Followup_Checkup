"""HTTP-level authorization tests for the reporting and follow-up endpoints.

These tests exercise the endpoints through FastAPI (TestClient) so that the
``Depends(require_role(...))`` dependency actually runs. Calling the router
functions directly — as the sibling unit tests do — bypasses dependency
injection entirely and therefore cannot cover the role gate that protects
these endpoints in production.

The injected session raises on any attribute access: a request that is
correctly rejected at the auth boundary must never reach the handler body,
so any database access here means the role gate did not fire.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import current_principal
from app.db import get_db
from app.main import app

PROGRAM_ID = uuid.uuid4()
REPORT_ID = uuid.uuid4()
CHECKUP_ID = uuid.uuid4()

PATIENT = {"sub": "pat-sub", "role": "patient"}
TECHNICIAN = {"sub": "tec-sub", "role": "technician"}


class ExplodingSession:
    """Fails the test if the handler body is reached."""

    def __getattr__(self, name):
        raise AssertionError(
            f"handler body reached the database ({name}) — the role gate did not reject the request"
        )


@pytest.fixture
def client_as():
    def _client(principal: dict) -> TestClient:
        app.dependency_overrides[current_principal] = lambda: principal
        app.dependency_overrides[get_db] = lambda: ExplodingSession()
        return TestClient(app, raise_server_exceptions=False)

    yield _client
    app.dependency_overrides.clear()


REPORT_BODY = {
    "program_exercise_id": str(uuid.uuid4()),
    "recording_ids": [str(uuid.uuid4())],
    "period_start": "2026-06-01",
    "period_end": "2026-06-30",
    "summary": "s",
}

CHECKUP_BODY = {
    "rehab_program_id": str(PROGRAM_ID),
    "exercise_report_ids": [str(REPORT_ID)],
    "period_start": "2026-06-01",
    "period_end": "2026-06-30",
    "summary": "s",
}

# (method, path, json body) for endpoints restricted to the medical role.
MEDICAL_ONLY = [
    ("post", "/reports", REPORT_BODY),
    ("patch", f"/reports/{REPORT_ID}", {"summary": "s"}),
    ("delete", f"/reports/{REPORT_ID}", None),
    ("post", "/followup-checkups", CHECKUP_BODY),
    ("patch", f"/followup-checkups/{CHECKUP_ID}", {"summary": "s"}),
    ("delete", f"/followup-checkups/{CHECKUP_ID}", None),
]

# (method, path) for endpoints open to medical and patient but closed to technicians.
TECHNICIAN_DENIED = [
    ("get", f"/programs/{PROGRAM_ID}/reports"),
    ("get", f"/reports/{REPORT_ID}"),
    ("get", f"/programs/{PROGRAM_ID}/followup-checkups"),
    ("get", f"/followup-checkups/{CHECKUP_ID}"),
]


def _request(client: TestClient, method: str, path: str, body: dict | None):
    # TestClient.delete() takes no json= argument.
    kwargs = {} if body is None else {"json": body}
    return getattr(client, method)(path, **kwargs)


@pytest.mark.parametrize("method,path,body", MEDICAL_ONLY)
def test_medical_only_endpoints_reject_patient(client_as, method, path, body):
    assert _request(client_as(PATIENT), method, path, body).status_code == 403


@pytest.mark.parametrize("method,path,body", MEDICAL_ONLY)
def test_medical_only_endpoints_reject_technician(client_as, method, path, body):
    assert _request(client_as(TECHNICIAN), method, path, body).status_code == 403


@pytest.mark.parametrize("method,path", TECHNICIAN_DENIED)
def test_shared_read_endpoints_reject_technician(client_as, method, path):
    response = getattr(client_as(TECHNICIAN), method)(path)
    assert response.status_code == 403
