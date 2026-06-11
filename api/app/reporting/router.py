import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import require_role
from app.db import get_db
from app.reporting.models import ExerciseReport, FollowupCheckup

router = APIRouter(tags=["reporting"])


class ReportIn(BaseModel):
    recording_id: uuid.UUID
    metrics_id: uuid.UUID | None = None
    insight_id: uuid.UUID | None = None
    resumen: str | None = None


@router.post("/reports")
def create_report(body: ReportIn, _=Depends(require_role("medical")), db=Depends(get_db)):
    r = ExerciseReport(**body.model_dump())
    db.add(r)
    db.flush()
    return {"report_id": str(r.id)}


@router.get("/followups/{patient_id}")
def followups(patient_id: uuid.UUID, _=Depends(require_role("medical", "patient")),
              db=Depends(get_db)):
    rows = db.scalars(select(FollowupCheckup).where(
        FollowupCheckup.patient_id == patient_id)).all()
    return [{"id": str(f.id), "periodo": f.periodo} for f in rows]
