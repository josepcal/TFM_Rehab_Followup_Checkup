import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.auth import require_role
from app.db import get_db
from app.recording.models import ExerciseRecording
from app.storage import get_storage

router = APIRouter(tags=["recording"])


class UploadUrlIn(BaseModel):
    program_exercise_id: uuid.UUID
    content_type: str = "audio/wav"


@router.post("/recordings/upload-url")
def upload_url(body: UploadUrlIn, _=Depends(require_role("patient", "medical")),
               db=Depends(get_db)):
    if not (body.content_type.startswith("audio/") or body.content_type.startswith("video/")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "recording content_type must be audio/* or video/*")
    key = f"{body.program_exercise_id}/{uuid.uuid4()}{_extension_for_content_type(body.content_type)}"
    return {"key": key, "url": get_storage().upload_url(key), "content_type": body.content_type}


class RecordingIn(BaseModel):
    program_exercise_id: uuid.UUID
    storage_uri: str
    content_type: str = "audio/wav"
    duration_seconds: float | None = Field(default=None, ge=0)
    sample_rate: int | None = Field(default=None, gt=0)
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")


@router.post("/recordings")
def register_recording(body: RecordingIn, principal=Depends(require_role("patient", "medical")),
                       db=Depends(get_db)):
    if not (body.content_type.startswith("audio/") or body.content_type.startswith("video/")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "recording content_type must be audio/* or video/*")
    recorded_by = db.info.get("identity_id")
    if recorded_by is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "authenticated user is not registered")
    rec = ExerciseRecording(
        program_exercise_id=body.program_exercise_id,
        recorded_by=uuid.UUID(str(recorded_by)),
        media_uri=body.storage_uri,
        content_type=body.content_type,
        media_kind=_media_kind_for_content_type(body.content_type),
        duration_seconds=body.duration_seconds,
        sample_rate=body.sample_rate,
        size_bytes=body.size_bytes,
        sha256=body.sha256.lower() if body.sha256 else None,
    )
    db.add(rec)
    db.flush()
    return {"recording_id": str(rec.recording_id)}


@router.get("/program-exercises/{program_exercise_id}/recordings")
def list_exercise_recordings(program_exercise_id: uuid.UUID, _=Depends(require_role("patient", "medical")),
                             db=Depends(get_db)):
    rows = db.scalars(
        select(ExerciseRecording)
        .where(ExerciseRecording.program_exercise_id == program_exercise_id)
        .where(ExerciseRecording.is_deleted.is_(False))
        .order_by(ExerciseRecording.created_at.desc())
    ).all()
    return [
        {
            "recording_id": str(row.recording_id),
            "program_exercise_id": str(row.program_exercise_id),
            "recorded_by": str(row.recorded_by) if row.recorded_by else None,
            "storage_uri": row.media_uri,
            "content_type": row.content_type,
            "media_kind": row.media_kind,
            "media_status": row.media_status,
            "recording_date": row.recording_date.isoformat() if row.recording_date else None,
            "duration_seconds": row.duration_seconds,
            "sample_rate": row.sample_rate,
            "size_bytes": row.size_bytes,
            "sha256": row.sha256,
            "notes": "Progress recording saved",
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.put("/recordings/_local-upload/{key:path}")
async def local_upload(key: str, request: Request,
                       _=Depends(require_role("patient", "medical"))):
    """Solo dev (LocalStorage): recibe el WAV y lo guarda en disco."""
    from app.storage import LocalStorage, get_storage
    st = get_storage()
    if not isinstance(st, LocalStorage):
        return {"error": "solo disponible en almacenamiento local (dev)"}
    with open(st.path(key), "wb") as f:
        f.write(await request.body())
    return {"stored": key}


def _extension_for_content_type(content_type: str) -> str:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/webm": ".webm",
        "audio/mp4": ".m4a",
        "video/webm": ".webm",
        "video/mp4": ".mp4",
    }.get(normalized, ".bin")


def _media_kind_for_content_type(content_type: str) -> str:
    normalized = content_type.split(";", 1)[0].strip().lower()
    return "video" if normalized.startswith("video/") else "audio"
