"""Pydantic v2 response schemas for norms endpoints (UC-09 extension)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MetricNormOut(BaseModel):
    """Response schema for a single metric norm."""

    model_config = ConfigDict(from_attributes=True)

    norm_id: uuid.UUID
    metric_code: str
    label: str | None = None
    unit: str | None = None
    direction: str
    sex: str | None = None
    age_min: int | None = None
    age_max: int | None = None
    good_min: float | None = None
    good_max: float | None = None
    poor_min: float | None = None
    poor_max: float | None = None
    source: str | None = None
    version: int
    created_at: datetime | None = None
