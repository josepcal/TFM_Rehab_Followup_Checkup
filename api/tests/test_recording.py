import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.recording import router


class FakeSession:
    def __init__(self, identity_id):
        self.added = None
        self.info = {"identity_id": str(identity_id)}

    def add(self, value):
        self.added = value

    def flush(self):
        self.added.recording_id = uuid.uuid4()


def test_register_recording_persists_capture_metadata_and_principal():
    identity_id = uuid.uuid4()
    session = FakeSession(identity_id)
    digest = "A1" * 32

    result = router.register_recording(
        router.RecordingIn(
            program_exercise_id=uuid.uuid4(),
            storage_uri="exercise/recording.webm",
            content_type="audio/webm;codecs=opus",
            duration_seconds=4.25,
            sample_rate=48_000,
            size_bytes=123_456,
            sha256=digest,
        ),
        {"sub": "idp|patient", "role": "patient"},
        session,
    )

    assert result["recording_id"]
    assert session.added.recorded_by == identity_id
    assert session.added.duration_seconds == 4.25
    assert session.added.sample_rate == 48_000
    assert session.added.size_bytes == 123_456
    assert session.added.sha256 == digest.lower()


def test_register_recording_rejects_unmapped_authenticated_subject():
    session = FakeSession(uuid.uuid4())
    session.info.clear()

    with pytest.raises(HTTPException) as exc_info:
        router.register_recording(
            router.RecordingIn(
                program_exercise_id=uuid.uuid4(),
                storage_uri="exercise/recording.webm",
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
        "storage_uri": "exercise/recording.webm",
        field: value,
    }

    with pytest.raises(ValidationError):
        router.RecordingIn(**payload)
