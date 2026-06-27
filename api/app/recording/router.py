import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.analysis.models import AnalysisSetup

from app.auth import require_role
from app.clinical.program_access_service import ProgramExerciseAccessService
from app.db import get_db
from app.metrics.models import MetricResult
from app.recording.models import ExerciseRecording
from app.reporting.models import AiInsight
from app.reporting.schemas import InsightOut
from app.jobs import enqueue
from app.storage import (
    LocalStorage,
    get_storage,
    normalize_content_type,
    recording_key,
    recording_program_exercise_id,
    validate_recording_key,
)

router = APIRouter(tags=["recording"])


class UploadUrlIn(BaseModel):
    program_exercise_id: uuid.UUID
    content_type: str = "audio/wav"


class UploadUrlOut(BaseModel):
    key: str
    url: str
    content_type: str


class RecordingIn(BaseModel):
    program_exercise_id: uuid.UUID
    storage_uri: str
    content_type: str = "audio/wav"
    recording_date: date | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    sample_rate: int | None = Field(default=None, gt=0)
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")


class RecordingCreatedOut(BaseModel):
    recording_id: uuid.UUID




class RunAnalysisIn(BaseModel):
    function_name: str | None = Field(
        default=None,
        description="Optional override. When omitted, the exercise analysis setup is used.",
    )


class RunAnalysisOut(BaseModel):
    job_id: uuid.UUID
    recording_id: uuid.UUID
    function_name: str
    status: str


class MetricResultOut(BaseModel):
    result_id: uuid.UUID
    recording_id: uuid.UUID
    function_name: str | None
    function_version: str | None
    code_sha: str | None
    status: str
    error_detail: str | None
    note: str | None
    raw_json: dict | None
    extracted_at: datetime

class RecordingOut(BaseModel):
    recording_id: uuid.UUID
    program_exercise_id: uuid.UUID
    recorded_by: uuid.UUID | None
    storage_uri: str | None
    content_type: str
    media_kind: str
    media_status: str
    recording_date: date
    duration_seconds: float | None
    sample_rate: int | None
    size_bytes: int | None
    sha256: str | None
    created_at: datetime


@router.post("/recordings/upload-url", response_model=UploadUrlOut)
def upload_url(
    body: UploadUrlIn,
    principal=Depends(require_role("patient", "medical")),
    db=Depends(get_db),
):
    content_type = _require_supported_content_type(body.content_type)
    ProgramExerciseAccessService(db).require_access(body.program_exercise_id, principal)
    key = recording_key(body.program_exercise_id, content_type)
    return UploadUrlOut(
        key=key,
        url=get_storage().upload_url(key, content_type),
        content_type=content_type,
    )


@router.post(
    "/recordings",
    response_model=RecordingCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
def register_recording(
    body: RecordingIn,
    principal=Depends(require_role("patient", "medical")),
    db=Depends(get_db),
):
    content_type = _require_supported_content_type(body.content_type)
    ProgramExerciseAccessService(db).require_access(body.program_exercise_id, principal)
    if not validate_recording_key(body.storage_uri, body.program_exercise_id, content_type):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid recording storage_uri namespace")

    recorded_by = db.info.get("identity_id")
    if recorded_by is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "authenticated user is not registered")
    rec = ExerciseRecording(
        program_exercise_id=body.program_exercise_id,
        recorded_by=uuid.UUID(str(recorded_by)),
        media_uri=body.storage_uri,
        content_type=content_type,
        media_kind=_media_kind_for_content_type(content_type),
        recording_date=body.recording_date or date.today(),
        duration_seconds=body.duration_seconds,
        sample_rate=body.sample_rate,
        size_bytes=body.size_bytes,
        sha256=body.sha256.lower() if body.sha256 else None,
    )
    db.add(rec)
    db.flush()
    return RecordingCreatedOut(recording_id=rec.recording_id)


@router.get(
    "/program-exercises/{program_exercise_id}/recordings",
    response_model=list[RecordingOut],
)
def list_exercise_recordings(
    program_exercise_id: uuid.UUID,
    principal=Depends(require_role("patient", "medical")),
    db=Depends(get_db),
):
    ProgramExerciseAccessService(db).require_access(program_exercise_id, principal)
    rows = db.scalars(
        select(ExerciseRecording)
        .where(ExerciseRecording.program_exercise_id == program_exercise_id)
        .where(ExerciseRecording.is_deleted.is_(False))
        .order_by(ExerciseRecording.created_at.desc())
    ).all()
    return [_recording_out(row) for row in rows]


@router.get("/recordings/{recording_id}", response_model=RecordingOut)
def get_recording(
    recording_id: uuid.UUID,
    principal=Depends(require_role("patient", "medical")),
    db=Depends(get_db),
):
    return _recording_out(_require_authorized_recording(recording_id, principal, db))



@router.delete("/recordings/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recording(
    recording_id: uuid.UUID,
    principal=Depends(require_role("patient", "medical")),
    db=Depends(get_db),
):
    """Delete a recording according to UC-13.

    The raw media object is purged from storage and the database row is kept
    as a soft-deleted clinical audit anchor so metrics/reports can remain.
    """
    recording = _require_authorized_recording(recording_id, principal, db)
    if recording.media_uri:
        get_storage().delete(recording.media_uri)
    recording.media_uri = None
    recording.media_status = "purged"
    recording.is_deleted = True
    recording.deleted_at = datetime.now(UTC)
    db.flush()
    return None



@router.post("/recordings/{recording_id}/run", response_model=RunAnalysisOut, status_code=status.HTTP_202_ACCEPTED)
def run_recording_analysis(
    recording_id: uuid.UUID,
    body: RunAnalysisIn | None = None,
    principal=Depends(require_role("patient", "medical")),
    db=Depends(get_db),
):
    """Enqueue UC-06 analysis for a recording without executing it inline.

    Authorization is deliberately identical to recording read access: patients
    can trigger their own recordings, and medical users can trigger recordings
    for patients under their assigned programme. Technicians are not accepted at
    the dependency boundary and remain limited to deploy-time function changes.
    """
    recording = _require_authorized_recording(recording_id, principal, db)
    function_name = (body.function_name if body else None) or _configured_function_name(
        recording.program_exercise_id, db
    )
    if not function_name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "no analysis function configured for this recording",
        )

    job = enqueue(db, recording.recording_id, function_name)
    return RunAnalysisOut(
        job_id=job.id,
        recording_id=recording.recording_id,
        function_name=function_name,
        status=job.status,
    )


@router.get("/recordings/{recording_id}/metrics", response_model=MetricResultOut)
def get_recording_metrics(
    recording_id: uuid.UUID,
    principal=Depends(require_role("patient", "medical")),
    db=Depends(get_db),
):
    """Return the current UC-06 metric result for an authorized recording.

    The response intentionally exposes the worker state as stored: either a
    successful raw metric JSON or an error state. No semantic interpretation or
    LLM call happens here.
    """
    _require_authorized_recording(recording_id, principal, db)
    result = db.scalar(
        select(MetricResult).where(MetricResult.recording_id == recording_id)
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "metrics not available yet")
    return MetricResultOut(
        result_id=result.result_id,
        recording_id=result.recording_id,
        function_name=result.function_name,
        function_version=result.function_version,
        code_sha=result.code_sha,
        status=str(result.status),
        error_detail=result.error_detail,
        note=result.note,
        raw_json=result.raw_json,
        extracted_at=result.extracted_at,
    )

@router.get("/recordings/{recording_id}/insight", response_model=InsightOut)
def get_recording_insight(
    recording_id: uuid.UUID,
    principal=Depends(require_role("medical", "patient")),
    db=Depends(get_db),
) -> InsightOut:
    """Return the AI insight for an authorized recording (UC-08 REQ-5).

    Resolves via the recording's metric_result → ai_insight chain.
    Both missing metric_result and missing ai_insight yield 404.
    Technicians are denied (403); other patient's recordings → 404 via RLS.
    """
    if principal.get("role") == "technician":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "technicians cannot access insights")
    recording = _require_authorized_recording(recording_id, principal, db)

    metric = db.scalar(
        select(MetricResult).where(MetricResult.recording_id == recording.recording_id)
    )
    if metric is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "metrics not available yet")

    insight = db.scalar(
        select(AiInsight).where(AiInsight.result_id == metric.result_id)
    )
    if insight is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI insight not available yet")

    return InsightOut(
        insight_id=insight.id,  # analysis.AiInsight maps id → ai_insight_id column
        recording_id=recording.recording_id,
        insight_text=insight.insight_text,
        model_used=insight.model_used,
        generated_at=insight.generated_at,
    )


@router.put("/recordings/_local-upload/{key:path}")
async def local_upload(
    key: str,
    request: Request,
    principal=Depends(require_role("patient", "medical")),
    db=Depends(get_db),
):
    """Authenticated local-dev equivalent of a presigned object-storage PUT."""
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "local recording storage is disabled")
    content_type = _require_supported_content_type(request.headers.get("content-type", ""))
    program_exercise_id = recording_program_exercise_id(key)
    if program_exercise_id is None or not validate_recording_key(key, program_exercise_id, content_type):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid recording upload key")
    ProgramExerciseAccessService(db).require_access(program_exercise_id, principal)
    with open(storage.path(key), "wb") as file_handle:
        file_handle.write(await request.body())
    return {"stored": key}



def _require_authorized_recording(recording_id: uuid.UUID, principal: dict, db) -> ExerciseRecording:
    recording = db.scalar(
        select(ExerciseRecording).where(
            ExerciseRecording.recording_id == recording_id,
            ExerciseRecording.is_deleted.is_(False),
        )
    )
    if recording is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recording not found")
    ProgramExerciseAccessService(db).require_access(recording.program_exercise_id, principal)
    return recording


def _configured_function_name(program_exercise_id: uuid.UUID, db) -> str | None:
    return db.scalar(
        select(AnalysisSetup.metric_api_endpoint)
        .where(AnalysisSetup.program_exercise_id == program_exercise_id)
        .order_by(AnalysisSetup.version.desc(), AnalysisSetup.updated_at.desc())
        .limit(1)
    )

def _require_supported_content_type(content_type: str) -> str:
    normalized = normalize_content_type(content_type)
    if not (normalized.startswith("audio/") or normalized.startswith("video/")):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "recording content_type must be audio/* or video/*",
        )
    return normalized


def _media_kind_for_content_type(content_type: str) -> str:
    return "video" if normalize_content_type(content_type).startswith("video/") else "audio"


def _recording_out(row: ExerciseRecording) -> RecordingOut:
    return RecordingOut(
        recording_id=row.recording_id,
        program_exercise_id=row.program_exercise_id,
        recorded_by=row.recorded_by,
        storage_uri=row.media_uri,
        content_type=row.content_type,
        media_kind=str(row.media_kind),
        media_status=str(row.media_status),
        recording_date=row.recording_date,
        duration_seconds=row.duration_seconds,
        sample_rate=row.sample_rate,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        created_at=row.created_at,
    )
