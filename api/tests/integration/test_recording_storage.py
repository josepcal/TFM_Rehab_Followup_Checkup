"""MinIO-backed integration tests for UC-05 recording uploads."""

import hashlib
import os
from uuid import uuid4

import httpx
import pytest

from app.storage import S3Storage, get_storage, recording_key


pytestmark = [pytest.mark.integration, pytest.mark.uc("UC-05")]


if os.getenv("RUN_INTEGRATION") != "1":
    pytest.skip(
        "Set RUN_INTEGRATION=1 with a configured MinIO instance to run.",
        allow_module_level=True,
    )


def test_presigned_recording_upload_round_trip_to_minio():
    """Upload recording bytes through the presigned URL and read them back."""
    if os.getenv("STORAGE_BACKEND") != "s3":
        pytest.skip("Set STORAGE_BACKEND=s3 and the S3_* variables for MinIO.")

    storage = get_storage()
    assert isinstance(storage, S3Storage)

    content_type = "audio/wav"
    payload = b"RIFF\x10\x00\x00\x00WAVEfmt ftm-uc5-minio-integration"
    expected_sha256 = hashlib.sha256(payload).hexdigest()
    key = recording_key(uuid4(), content_type)

    try:
        upload_url = storage.upload_url(key, content_type)
        with httpx.Client(trust_env=False, timeout=15) as client:
            response = client.put(
                upload_url,
                content=payload,
                headers={"Content-Type": content_type},
            )
        response.raise_for_status()

        metadata = storage.client.head_object(Bucket=storage.bucket, Key=key)
        assert metadata["ContentLength"] == len(payload)
        assert metadata["ContentType"] == content_type

        stored_object = storage.client.get_object(Bucket=storage.bucket, Key=key)
        try:
            stored_payload = stored_object["Body"].read()
        finally:
            stored_object["Body"].close()

        assert stored_payload == payload
        assert hashlib.sha256(stored_payload).hexdigest() == expected_sha256
    finally:
        storage.client.delete_object(Bucket=storage.bucket, Key=key)
