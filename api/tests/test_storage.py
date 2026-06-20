import uuid

import pytest

from app.storage import LocalStorage, S3Storage, recording_key, validate_recording_key


class FakeS3Client:
    def __init__(self):
        self.calls = []

    def generate_presigned_url(self, operation, **kwargs):
        self.calls.append((operation, kwargs))
        return "https://minio.test/presigned"


def test_s3_storage_generates_content_type_bound_presigned_put():
    client = FakeS3Client()
    storage = S3Storage(bucket="ftm-recordings", client=client)

    url = storage.upload_url("recordings/exercise/file.webm", "audio/webm")

    assert url == "https://minio.test/presigned"
    operation, kwargs = client.calls[0]
    assert operation == "put_object"
    assert kwargs["Params"] == {
        "Bucket": "ftm-recordings",
        "Key": "recordings/exercise/file.webm",
        "ContentType": "audio/webm",
    }
    assert kwargs["ExpiresIn"] == 900


def test_recording_key_is_namespaced_and_validated():
    program_exercise_id = uuid.uuid4()
    key = recording_key(program_exercise_id, "video/mp4")

    assert key.startswith(f"recordings/{program_exercise_id}/")
    assert validate_recording_key(key, program_exercise_id, "video/mp4")
    assert not validate_recording_key(key, uuid.uuid4(), "video/mp4")
    assert not validate_recording_key(key, program_exercise_id, "audio/wav")


def test_local_storage_rejects_path_traversal(tmp_path):
    storage = LocalStorage(str(tmp_path))

    with pytest.raises(ValueError):
        storage.path("../outside.wav")
