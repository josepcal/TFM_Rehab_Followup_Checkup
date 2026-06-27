"""Norms endpoints (UC-09 extension).

GET /norms               — list all metric norms
GET /norms/{metric_code} — get norm for a specific metric code

Authorization: all authenticated roles (medical, patient, technician, admin).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.auth import require_role
from app.db import get_db
from app.norms.models import MetricNorm
from app.norms.schemas import MetricNormOut

router = APIRouter(tags=["norms"])


@router.get("/norms", response_model=list[MetricNormOut])
def list_norms(
    principal: dict = Depends(require_role("medical", "patient", "technician", "admin")),
    db=Depends(get_db),
) -> list[MetricNormOut]:
    """Return all metric norms from reference.metric_norm."""
    rows = db.scalars(select(MetricNorm)).all()
    return [MetricNormOut.model_validate(row) for row in rows]


@router.get("/norms/{metric_code}", response_model=MetricNormOut)
def get_norm(
    metric_code: str,
    principal: dict = Depends(require_role("medical", "patient", "technician", "admin")),
    db=Depends(get_db),
) -> MetricNormOut:
    """Return a single norm by metric_code, or 404 if not found."""
    row = db.scalar(select(MetricNorm).where(MetricNorm.metric_code == metric_code))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"norm not found for metric_code '{metric_code}'",
        )
    return MetricNormOut.model_validate(row)
