import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth import require_role
from app.db import get_db
from app.recording.models import ExerciseRecording
from app.storage import get_storage

router = APIRouter(tags=["recording"])


class UploadUrlIn(BaseModel):
    program_exercise_id: uuid.UUID


@router.post("/recordings/upload-url")
def upload_url(body: UploadUrlIn, _=Depends(require_role("patient", "medical")),
               db=Depends(get_db)):
    key = f"{body.program_exercise_id}/{uuid.uuid4()}.wav"
    return {"key": key, "url": get_storage().upload_url(key)}


class RecordingIn(BaseModel):
    program_exercise_id: uuid.UUID
    storage_uri: str


@router.post("/recordings")
def register_recording(body: RecordingIn, _=Depends(require_role("patient", "medical")),
                       db=Depends(get_db)):
    rec = ExerciseRecording(program_exercise_id=body.program_exercise_id,
                            storage_uri=body.storage_uri)
    db.add(rec)
    db.flush()
    return {"recording_id": str(rec.id)}


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
