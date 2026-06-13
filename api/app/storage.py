import os
from datetime import timedelta

from app.config import get_settings

settings = get_settings()


class LocalStorage:
    """Dev: los WAV se guardan en disco; la 'upload URL' es un endpoint local."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def upload_url(self, key: str) -> str:
        return f"/api/recordings/_local-upload/{key}"

    def path(self, key: str) -> str:
        p = os.path.join(self.base_dir, key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def download_to_tmp(self, key: str) -> str:
        return os.path.join(self.base_dir, key)


class GcsStorage:
    """Prod: bucket privado + signed URLs (PUT para subir, GET para el worker)."""

    def __init__(self, bucket: str):
        from google.cloud import storage  # import perezoso

        self._bucket = storage.Client().bucket(bucket)

    def upload_url(self, key: str) -> str:
        return self._bucket.blob(key).generate_signed_url(
            version="v4", expiration=timedelta(minutes=15), method="PUT",
            content_type="audio/wav",
        )

    def download_to_tmp(self, key: str) -> str:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self._bucket.blob(key).download_to_filename(tmp.name)
        return tmp.name


def get_storage():
    if settings.wav_bucket:
        return GcsStorage(settings.wav_bucket)
    return LocalStorage(settings.wav_local_dir)
