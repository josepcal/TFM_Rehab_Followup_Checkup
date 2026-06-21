import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import require_role
from app.recording import router


def test_run_recording_analysis_enqueues_with_override(monkeypatch):
    recording_id = uuid.uuid4()
    recording = SimpleNamespace(recording_id=recording_id, program_exercise_id=uuid.uuid4())
    job_id = uuid.uuid4()
    captured = {}

    monkeypatch.setattr(router, "_require_authorized_recording", lambda rid, principal, db: recording)
    monkeypatch.setattr(router, "_configured_function_name", lambda program_exercise_id, db: pytest.fail("override should be used"))

    def fake_enqueue(db, rec_id, function_name):
        captured["recording_id"] = rec_id
        captured["function_name"] = function_name
        return SimpleNamespace(id=job_id, status="pending")

    monkeypatch.setattr(router, "enqueue", fake_enqueue)

    result = router.run_recording_analysis(
        recording_id,
        router.RunAnalysisIn(function_name="override_metric_v1"),
        {"role": "patient", "sub": "patient-sub"},
        object(),
    )

    assert result.job_id == job_id
    assert result.recording_id == recording_id
    assert result.function_name == "override_metric_v1"
    assert result.status == "pending"
    assert captured == {"recording_id": recording_id, "function_name": "override_metric_v1"}


def test_run_recording_analysis_uses_configured_function_when_no_override(monkeypatch):
    recording_id = uuid.uuid4()
    program_exercise_id = uuid.uuid4()
    recording = SimpleNamespace(recording_id=recording_id, program_exercise_id=program_exercise_id)
    job_id = uuid.uuid4()

    monkeypatch.setattr(router, "_require_authorized_recording", lambda rid, principal, db: recording)
    monkeypatch.setattr(router, "_configured_function_name", lambda pe_id, db: "configured_metric_v1")
    monkeypatch.setattr(router, "enqueue", lambda db, rec_id, fn: SimpleNamespace(id=job_id, status="pending"))

    result = router.run_recording_analysis(
        recording_id,
        None,
        {"role": "medical", "sub": "doctor-sub"},
        object(),
    )

    assert result.function_name == "configured_metric_v1"
    assert result.status == "pending"


def test_run_recording_analysis_rejects_missing_function_configuration(monkeypatch):
    recording_id = uuid.uuid4()
    recording = SimpleNamespace(recording_id=recording_id, program_exercise_id=uuid.uuid4())

    monkeypatch.setattr(router, "_require_authorized_recording", lambda rid, principal, db: recording)
    monkeypatch.setattr(router, "_configured_function_name", lambda pe_id, db: None)

    with pytest.raises(HTTPException) as exc_info:
        router.run_recording_analysis(
            recording_id,
            None,
            {"role": "patient", "sub": "patient-sub"},
            object(),
        )

    assert exc_info.value.status_code == 400


def test_technician_role_is_denied_for_analysis_run_dependency():
    dependency = require_role("patient", "medical")

    with pytest.raises(HTTPException) as exc_info:
        dependency({"role": "technician", "sub": "tech-sub"})

    assert exc_info.value.status_code == 403


def test_get_recording_metrics_returns_current_success_or_error_state(monkeypatch):
    recording_id = uuid.uuid4()
    result_id = uuid.uuid4()
    metric_result = SimpleNamespace(
        result_id=result_id,
        recording_id=recording_id,
        function_name="metric_v1",
        function_version="1.0.0",
        code_sha="abc123",
        status="success",
        error_detail=None,
        raw_json={"jitter": 0.1},
        extracted_at=datetime.now(timezone.utc),
    )

    class FakeSession:
        def scalar(self, statement):
            return metric_result

    monkeypatch.setattr(router, "_require_authorized_recording", lambda rid, principal, db: object())

    response = router.get_recording_metrics(
        recording_id,
        {"role": "medical", "sub": "doctor-sub"},
        FakeSession(),
    )

    assert response.result_id == result_id
    assert response.recording_id == recording_id
    assert response.status == "success"
    assert response.raw_json == {"jitter": 0.1}


def test_get_recording_metrics_404_when_worker_has_not_persisted_result(monkeypatch):
    recording_id = uuid.uuid4()

    class FakeSession:
        def scalar(self, statement):
            return None

    monkeypatch.setattr(router, "_require_authorized_recording", lambda rid, principal, db: object())

    with pytest.raises(HTTPException) as exc_info:
        router.get_recording_metrics(
            recording_id,
            {"role": "patient", "sub": "patient-sub"},
            FakeSession(),
        )

    assert exc_info.value.status_code == 404
