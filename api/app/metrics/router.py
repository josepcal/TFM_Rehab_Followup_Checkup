import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import require_role
from app.db import get_db
from app.jobs import enqueue
from app.metrics.models import RecordingMetrics

router = APIRouter(tags=["metrics"])


class RunIn(BaseModel):
    function_name: str   # el medico pasa el WAV (grabacion) + el nombre de la funcion


@router.post("/recordings/{recording_id}/run")
def run_analysis(recording_id: uuid.UUID, body: RunIn,
                 _=Depends(require_role("medical", "technician")), db=Depends(get_db)):
    job = enqueue(db, recording_id, body.function_name)
    return {"job_id": str(job.id), "status": job.status}


@router.get("/recordings/{recording_id}/metrics")
def get_metrics(recording_id: uuid.UUID,
                _=Depends(require_role("medical", "patient")), db=Depends(get_db)):
    m = db.scalar(select(RecordingMetrics).where(RecordingMetrics.recording_id == recording_id))
    if m is None:
        raise HTTPException(404, "metricas no disponibles todavia")
    return {"function_name": m.function_name, "metrics": m.metrics}
