import tempfile
from datetime import timedelta
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from app.config import get_settings

settings = get_settings()


CONTENT_TYPE_EXTENSIONS = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
    "audio/mp4": ".m4a",
    "video/webm": ".webm",
    "video/mp4": ".mp4",
}


def normalize_content_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def recording_key(program_exercise_id: UUID, content_type: str) -> str:
    extension = CONTENT_TYPE_EXTENSIONS.get(normalize_content_type(content_type), ".bin")
    return f"recordings/{program_exercise_id}/{uuid4()}{extension}"


def validate_recording_key(key: str, program_exercise_id: UUID, content_type: str) -> bool:
    path = PurePosixPath(key)
    parts = path.parts
    if len(parts) != 3 or parts[0] != "recordings" or parts[1] != str(program_exercise_id):
        return False
    try:
        UUID(path.stem)
    except ValueError:
        return False
    expected_extension = CONTENT_TYPE_EXTENSIONS.get(normalize_content_type(content_type), ".bin")
    return path.suffix.lower() == expected_extension


def recording_program_exercise_id(key: str) -> UUID | None:
    parts = PurePosixPath(key).parts
    if len(parts) != 3 or parts[0] != "recordings":
        return None
    try:
        return UUID(parts[1])
    except ValueError:
        return None


class LocalStorage:
    """Local-dev storage through an authenticated FastAPI PUT endpoint."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload_url(self, key: str, content_type: str) -> str:
        return f"/api/recordings/_local-upload/{key}"

    def path(self, key: str) -> str:
        path = (self.base_dir / key).resolve()
        if self.base_dir not in path.parents:
            raise ValueError("recording key escapes local storage root")
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def download_to_tmp(self, key: str) -> str:
        return self.path(key)

    def delete(self, key: str) -> None:
        Path(self.path(key)).unlink(missing_ok=True)


class S3Storage:
    """Private S3/MinIO-compatible object storage using presigned PUT URLs."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str = "",
        access_key_id: str = "",
        secret_access_key: str = "",
        region: str = "eu-west-1",
        force_path_style: bool = False,
        client=None,
    ):
        self.bucket = bucket
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url or None,
                aws_access_key_id=access_key_id or None,
                aws_secret_access_key=secret_access_key or None,
                region_name=region,
                config=Config(s3={"addressing_style": "path" if force_path_style else "auto"}),
            )
        self.client = client

    def upload_url(self, key: str, content_type: str) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=900,
        )

    def download_to_tmp(self, key: str) -> str:
        suffix = PurePosixPath(key).suffix
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.close()
        self.client.download_file(self.bucket, key, tmp.name)
        return tmp.name

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


class GcsStorage:
    """Backward-compatible private GCS storage adapter."""

    def __init__(self, bucket: str):
        from google.cloud import storage

        self._bucket = storage.Client().bucket(bucket)

    def upload_url(self, key: str, content_type: str) -> str:
        return self._bucket.blob(key).generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type=content_type,
        )

    def download_to_tmp(self, key: str) -> str:
        suffix = PurePosixPath(key).suffix
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.close()
        self._bucket.blob(key).download_to_filename(tmp.name)
        return tmp.name

    def delete(self, key: str) -> None:
        blob = self._bucket.blob(key)
        try:
            blob.delete()
        except Exception as exc:
            if exc.__class__.__name__ != "NotFound":
                raise


def get_storage():
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        return S3Storage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            region=settings.s3_region,
            force_path_style=settings.s3_force_path_style,
        )
    if settings.wav_bucket:
        return GcsStorage(settings.wav_bucket)
    return LocalStorage(settings.wav_local_dir)
