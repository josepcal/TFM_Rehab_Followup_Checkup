"""Pydantic schemas for the IAM domain (UC-15)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventLogEntry(BaseModel):
    event_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    actor_id: uuid.UUID | None
    payload: dict | None
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)
