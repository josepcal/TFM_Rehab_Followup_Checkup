import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.recording import router


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
        self.added.recording_id = uuid.uuid4()


class FakeStorage:
    def upload_url(self, key, content_type):
        return f"https://storage.test/{key}?content-type={content_type}"


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
    session = FakeSession(scalar_values=[program_exercise_id])
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
    session = FakeSession(identity_id, scalar_values=[program_exercise_id])
    digest = "A1" * 32

    result = router.register_recording(
        router.RecordingIn(
            program_exercise_id=program_exercise_id,
            storage_uri=recording_key_for(program_exercise_id),
            content_type="audio/webm;codecs=opus",
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
    program_exercise_id = uuid.uuid4()
    session = FakeSession(uuid.uuid4(), scalar_values=[program_exercise_id])

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


def test_register_recording_rejects_unmapped_authenticated_subject():
    program_exercise_id = uuid.uuid4()
    session = FakeSession(scalar_values=[program_exercise_id])

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
