"""Pydantic v2 request/response schemas for the reporting endpoints (UC-07/UC-08)."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ReportIn(BaseModel):
    """Request body for POST /reports."""

    program_exercise_id: uuid.UUID
    recording_ids: list[uuid.UUID]
    period_start: date
    period_end: date
    summary: str | None = None

    @field_validator("recording_ids")
    @classmethod
    def recording_ids_not_empty(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(v) < 1:
            raise ValueError("recording_ids must contain at least one entry")
        return v

    @model_validator(mode="after")
    def period_end_not_before_start(self) -> "ReportIn":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be >= period_start")
        return self


class ReportCreatedOut(BaseModel):
    """Response body for POST /reports — returns the new report id."""

    exercise_report_id: uuid.UUID


class ReportListItem(BaseModel):
    """One item in the GET /programs/{program_id}/reports response."""

    model_config = ConfigDict(from_attributes=True)

    exercise_report_id: uuid.UUID
    program_exercise_id: uuid.UUID | None
    period_start: date
    period_end: date
    summary: str | None
    created_by: uuid.UUID | None
    attested_at: datetime | None
    recording_count: int


class RecordingInsightOut(BaseModel):
    """One recording entry inside a full report detail response."""

    recording_id: uuid.UUID
    recording_date: date
    duration_seconds: float | None
    media_status: str
    metrics_status: str | None
    raw_json: dict[str, Any] | None
    insight_text: str | None
    model_used: str | None


class ReportDetailOut(BaseModel):
    """Response body for GET /reports/{report_id}."""

    model_config = ConfigDict(from_attributes=True)

    exercise_report_id: uuid.UUID
    program_exercise_id: uuid.UUID | None
    period_start: date
    period_end: date
    summary: str | None
    created_by: uuid.UUID | None
    attested_at: datetime | None
    recordings: list[RecordingInsightOut]


class InsightOut(BaseModel):
    """Response body for GET /recordings/{recording_id}/insight."""

    insight_id: uuid.UUID
    recording_id: uuid.UUID
    insight_text: str
    model_used: str | None
    generated_at: datetime
