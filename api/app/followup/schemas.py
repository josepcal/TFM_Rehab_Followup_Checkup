"""Pydantic v2 request/response schemas for follow-up checkup endpoints (UC-09)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class CheckupIn(BaseModel):
    """Request body for POST /followup-checkups."""

    rehab_program_id: uuid.UUID
    exercise_report_ids: list[uuid.UUID]
    period_start: date
    period_end: date
    summary: str | None = None

    @field_validator("exercise_report_ids")
    @classmethod
    def report_ids_not_empty(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(v) < 1:
            raise ValueError("exercise_report_ids must contain at least one entry")
        return v

    @model_validator(mode="after")
    def period_end_not_before_start(self) -> "CheckupIn":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be >= period_start")
        return self


class CheckupCreatedOut(BaseModel):
    """Response body for POST /followup-checkups — returns the new checkup id."""

    followup_checkup_id: uuid.UUID


class CheckupPatchIn(BaseModel):
    """Request body for PATCH /followup-checkups/{id}."""

    summary: str | None = None


class CheckupListItem(BaseModel):
    """One item in the GET /programs/{program_id}/followup-checkups response."""

    model_config = ConfigDict(from_attributes=True)

    followup_checkup_id: uuid.UUID
    rehab_program_id: uuid.UUID
    period_start: date
    period_end: date
    summary: str | None
    created_by: uuid.UUID | None
    created_by_name: str | None
    report_count: int


class LinkedReportItem(BaseModel):
    """One linked exercise report inside a checkup detail response."""

    exercise_report_id: uuid.UUID
    period_start: date
    period_end: date
    summary: str | None


class CheckupDetailOut(BaseModel):
    """Response body for GET /followup-checkups/{id}."""

    model_config = ConfigDict(from_attributes=True)

    followup_checkup_id: uuid.UUID
    rehab_program_id: uuid.UUID
    period_start: date
    period_end: date
    summary: str | None
    created_by: uuid.UUID | None
    reports: list[LinkedReportItem]
