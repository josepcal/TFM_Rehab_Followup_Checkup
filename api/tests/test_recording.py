import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.recording import router


# ---------------------------------------------------------------------------
# Consent-related fake rows (needed for write path guard, UC-05)
# ---------------------------------------------------------------------------

def _pe_row(program_exercise_id: uuid.UUID, program_id: uuid.UUID):
    """Fake ProgramExercise row — consumed by require_active_consent."""
    return type(
        "PE",
        (),
        {"id": program_exercise_id, "program_id": program_id},
    )()


def _app_user_row(identity_id: uuid.UUID):
    return type("AppUser", (), {"identity_id": identity_id, "external_subject": "patient-sub"})()


def _patient_row(patient_id: uuid.UUID, identity_id: uuid.UUID):
    return type("Patient", (), {"id": patient_id, "identity_id": identity_id})()


def _active_consent_row(patient_id: uuid.UUID, program_id: uuid.UUID):
    return type(
        "PatientConsent",
        (),
        {
            "consent_id": uuid.uuid4(),
            "patient_id": patient_id,
            "rehab_program_id": program_id,
            "granted": True,
            "granted_at": datetime.now(timezone.utc),
            "withdrawn_at": None,
            "consent_text": "I consent",
        },
    )()


def _write_guard_scalars(
    program_exercise_id: uuid.UUID,
    program_id: uuid.UUID,
    identity_id: uuid.UUID,
    patient_id: uuid.UUID,
    access_result=None,
):
    """Build scalar_values list for patient write paths with active consent.

    Order matches the call sequence in the recording router:
    1. require_active_consent → ProgramExercise (for program_id)
    2. require_active_consent → ConsentService._resolve_patient_id → AppUser
    3. require_active_consent → ConsentService._resolve_patient_id → Patient
    4. require_active_consent → ConsentService.get_active → PatientConsent
    5. ProgramExerciseAccessService.require_access → authorized id
    """
    return [
        _pe_row(program_exercise_id, program_id),
        _app_user_row(identity_id),
        _patient_row(patient_id, identity_id),
        _active_consent_row(patient_id, program_id),
        access_result if access_result is not None else program_exercise_id,
    ]


class FakeScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, identity_id=None, scalar_values=None, rows=None):
        self.added = None
        self.info = {"identity_id": str(identity_id)} if identity_id else {}
        self.scalar_values = list(scalar_values or [])
        self.rows = rows or []

    def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def scalars(self, _statement):
        return FakeScalarResult(self.rows)

    def add(self, value):
        self.added = value

    def flush(self):
        if self.added is not None:
            self.added.recording_id = uuid.uuid4()


class FakeStorage:
    def __init__(self):
        self.deleted = []

    def upload_url(self, key, content_type):
        return f"https://storage.test/{key}?content-type={content_type}"

    def delete(self, key):
        self.deleted.append(key)


def recording_key_for(program_exercise_id, extension=".webm"):
    return f"recordings/{program_exercise_id}/{uuid.uuid4()}{extension}"


def recording_row(program_exercise_id):
    return type(
        "RecordingRow",
        (),
        {
            "recording_id": uuid.uuid4(),
            "program_exercise_id": program_exercise_id,
            "recorded_by": uuid.uuid4(),
            "media_uri": recording_key_for(program_exercise_id),
            "content_type": "audio/webm",
            "media_kind": "audio",
            "media_status": "available",
            "recording_date": date.today(),
            "duration_seconds": 4.25,
            "sample_rate": 48_000,
            "size_bytes": 123_456,
            "sha256": "a1" * 32,
            "created_at": datetime.now(timezone.utc),
        },
    )()


def test_upload_url_authorizes_and_returns_namespaced_key(monkeypatch):
    program_exercise_id = uuid.uuid4()
    program_id = uuid.uuid4()
    identity_id = uuid.uuid4()
    patient_id = uuid.uuid4()
    session = FakeSession(
        identity_id=identity_id,
        scalar_values=_write_guard_scalars(program_exercise_id, program_id, identity_id, patient_id),
    )
    monkeypatch.setattr(router, "get_storage", lambda: FakeStorage())

    result = router.upload_url(
        router.UploadUrlIn(program_exercise_id=program_exercise_id, content_type="audio/webm;codecs=opus"),
        {"sub": "patient-sub", "role": "patient"},
        session,
    )

    assert result.key.startswith(f"recordings/{program_exercise_id}/")
    assert result.key.endswith(".webm")
    assert result.content_type == "audio/webm"
    assert result.url.startswith("https://storage.test/")


def test_upload_url_rejects_unsupported_content_type_before_storage(monkeypatch):
    monkeypatch.setattr(router, "get_storage", lambda: pytest.fail("storage must not be called"))

    with pytest.raises(HTTPException) as exc_info:
        router.upload_url(
            router.UploadUrlIn(program_exercise_id=uuid.uuid4(), content_type="application/pdf"),
            {"sub": "patient-sub", "role": "patient"},
            FakeSession(),
        )

    assert exc_info.value.status_code == 400


def test_register_recording_persists_capture_metadata_and_principal():
    identity_id = uuid.uuid4()
    program_exercise_id = uuid.uuid4()
    program_id = uuid.uuid4()
    patient_id = uuid.uuid4()
    session = FakeSession(
        identity_id,
        scalar_values=_write_guard_scalars(program_exercise_id, program_id, identity_id, patient_id),
    )
    digest = "A1" * 32

    result = router.register_recording(
        router.RecordingIn(
            program_exercise_id=program_exercise_id,
            storage_uri=recording_key_for(program_exercise_id),
            content_type="audio/webm;codecs=opus",
            recording_date=date(2026, 6, 1),
            duration_seconds=4.25,
            sample_rate=48_000,
            size_bytes=123_456,
            sha256=digest,
        ),
        {"sub": "idp|patient", "role": "patient"},
        session,
    )

    assert result.recording_id
    assert session.added.recorded_by == identity_id
    assert session.added.recording_date == date(2026, 6, 1)
    assert session.added.duration_seconds == 4.25
    assert session.added.sample_rate == 48_000
    assert session.added.size_bytes == 123_456
    assert session.added.sha256 == digest.lower()


@pytest.mark.parametrize(
    "storage_uri",
    [
        "not-a-recording-key.webm",
        f"recordings/{uuid.uuid4()}/{uuid.uuid4()}.webm",
        f"recordings/{uuid.uuid4()}/not-a-uuid.webm",
    ],
)
def test_register_recording_rejects_malformed_or_unrelated_storage_uri(storage_uri):
    identity_id = uuid.uuid4()
    program_exercise_id = uuid.uuid4()
    program_id = uuid.uuid4()
    patient_id = uuid.uuid4()
    session = FakeSession(
        identity_id,
        scalar_values=_write_guard_scalars(program_exercise_id, program_id, identity_id, patient_id),
    )

    with pytest.raises(HTTPException) as exc_info:
        router.register_recording(
            router.RecordingIn(
                program_exercise_id=program_exercise_id,
                storage_uri=storage_uri,
                content_type="audio/webm",
            ),
            {"sub": "idp|patient", "role": "patient"},
            session,
        )

    assert exc_info.value.status_code == 400
    assert session.added is None


def test_recording_access_rejects_unowned_program_exercise():
    with pytest.raises(HTTPException) as exc_info:
        router.list_exercise_recordings(
            uuid.uuid4(),
            {"sub": "patient-sub", "role": "patient"},
            FakeSession(scalar_values=[None]),
        )

    assert exc_info.value.status_code == 404


def test_list_and_detail_recordings_return_metadata():
    program_exercise_id = uuid.uuid4()
    row = recording_row(program_exercise_id)
    list_session = FakeSession(scalar_values=[program_exercise_id], rows=[row])

    listed = router.list_exercise_recordings(
        program_exercise_id,
        {"sub": "patient-sub", "role": "patient"},
        list_session,
    )
    detail_session = FakeSession(scalar_values=[row, program_exercise_id])
    detailed = router.get_recording(
        row.recording_id,
        {"sub": "patient-sub", "role": "patient"},
        detail_session,
    )

    assert listed[0].recording_id == row.recording_id
    assert listed[0].sha256 == row.sha256
    assert detailed.recording_id == row.recording_id
    assert detailed.storage_uri == row.media_uri


def test_delete_recording_purges_media_and_soft_deletes_row(monkeypatch):
    program_exercise_id = uuid.uuid4()
    row = recording_row(program_exercise_id)
    media_uri = row.media_uri
    storage = FakeStorage()
    monkeypatch.setattr(router, "get_storage", lambda: storage)
    session = FakeSession(scalar_values=[row, program_exercise_id])

    result = router.delete_recording(
        row.recording_id,
        {"sub": "patient-sub", "role": "patient"},
        session,
    )

    assert result is None
    assert storage.deleted == [media_uri]
    assert row.media_uri is None
    assert row.media_status == "purged"
    assert row.is_deleted is True
    assert row.deleted_at is not None


def test_delete_recording_rejects_missing_or_deleted_recording(monkeypatch):
    monkeypatch.setattr(router, "get_storage", lambda: pytest.fail("storage must not be called"))

    with pytest.raises(HTTPException) as exc_info:
        router.delete_recording(
            uuid.uuid4(),
            {"sub": "patient-sub", "role": "patient"},
            FakeSession(scalar_values=[None]),
        )

    assert exc_info.value.status_code == 404


def test_register_recording_rejects_unmapped_authenticated_subject():
    """Patient identity not in clinical.patient → 403 before any recording is added."""
    program_exercise_id = uuid.uuid4()
    program_id = uuid.uuid4()
    identity_id = uuid.uuid4()
    session = FakeSession(
        identity_id=identity_id,
        scalar_values=[
            # require_active_consent → ProgramExercise
            _pe_row(program_exercise_id, program_id),
            # ConsentService._resolve_patient_id → AppUser not found (returns None)
            None,
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        router.register_recording(
            router.RecordingIn(
                program_exercise_id=program_exercise_id,
                storage_uri=recording_key_for(program_exercise_id, ".wav"),
            ),
            {"sub": "idp|unknown", "role": "patient"},
            session,
        )

    assert exc_info.value.status_code == 403
    assert session.added is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("duration_seconds", -0.1),
        ("sample_rate", 0),
        ("size_bytes", -1),
        ("sha256", "not-a-sha256"),
    ],
)
def test_recording_metadata_rejects_invalid_values(field, value):
    payload = {
        "program_exercise_id": uuid.uuid4(),
        "storage_uri": "recordings/example.wav",
        field: value,
    }

    with pytest.raises(ValidationError):
        router.RecordingIn(**payload)


# ---------------------------------------------------------------------------
# Task 5.4: GET /recordings/{recording_id}/insight
# ---------------------------------------------------------------------------


def _make_insight(
    ai_insight_id=None,
    result_id=None,
    recording_id=None,
    insight_text="Stable phonation detected",
    model_used="gpt-4o",
    generated_at=None,
):
    from datetime import datetime, timezone

    _id = ai_insight_id or uuid.uuid4()
    return type(
        "AiInsight",
        (),
        {
            # analysis.AiInsight uses 'id' as the Python attr (maps to ai_insight_id column)
            "id": _id,
            "ai_insight_id": _id,
            "result_id": result_id or uuid.uuid4(),
            "insight_text": insight_text,
            "model_used": model_used,
            "generated_at": generated_at or datetime.now(timezone.utc),
        },
    )()


def _make_metric_result(recording_id=None, result_id=None):
    return type(
        "MetricResult",
        (),
        {
            "result_id": result_id or uuid.uuid4(),
            "recording_id": recording_id or uuid.uuid4(),
        },
    )()


def test_insight_exists_returns_200_with_all_fields():
    """REQ-5: insight exists → 200 + insight_id, recording_id, insight_text, model_used, generated_at."""
    program_exercise_id = uuid.uuid4()
    rec = recording_row(program_exercise_id)
    mr = _make_metric_result(recording_id=rec.recording_id)
    ai = _make_insight(result_id=mr.result_id)
    # scalars: (1) ExerciseRecording lookup in _require_authorized_recording,
    #          (2) program_exercise access check,
    #          (3) MetricResult lookup,
    #          (4) AiInsight lookup
    session = FakeSession(scalar_values=[rec, program_exercise_id, mr, ai])
    result = router.get_recording_insight(
        rec.recording_id,
        {"sub": "doc-sub", "role": "medical"},
        session,
    )
    assert result.insight_id == ai.ai_insight_id
    assert result.recording_id == rec.recording_id
    assert result.insight_text == ai.insight_text
    assert result.model_used == ai.model_used
    assert result.generated_at == ai.generated_at


def test_insight_no_metric_result_returns_404():
    """REQ-5: no metric_result → 404."""
    program_exercise_id = uuid.uuid4()
    rec = recording_row(program_exercise_id)
    # scalar_values: recording found, program_exercise check, then no metric_result
    session = FakeSession(scalar_values=[rec, program_exercise_id, None])
    with pytest.raises(HTTPException) as exc:
        router.get_recording_insight(
            rec.recording_id,
            {"sub": "doc-sub", "role": "medical"},
            session,
        )
    assert exc.value.status_code == 404


def test_insight_metric_result_exists_but_no_ai_insight_returns_404():
    """REQ-5: metric_result exists but no ai_insight yet → 404."""
    program_exercise_id = uuid.uuid4()
    rec = recording_row(program_exercise_id)
    mr = _make_metric_result(recording_id=rec.recording_id)
    session = FakeSession(scalar_values=[rec, program_exercise_id, mr, None])
    with pytest.raises(HTTPException) as exc:
        router.get_recording_insight(
            rec.recording_id,
            {"sub": "doc-sub", "role": "medical"},
            session,
        )
    assert exc.value.status_code == 404


def test_insight_technician_returns_403():
    """REQ-5: technician role denied."""
    with pytest.raises(HTTPException) as exc:
        router.get_recording_insight(
            uuid.uuid4(),
            {"sub": "tec-sub", "role": "technician"},
            FakeSession(),
        )
    assert exc.value.status_code == 403
