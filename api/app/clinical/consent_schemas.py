"""Pydantic v2 schemas for the RGPD consent endpoints (UC-05)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConsentIn(BaseModel):
    """Request body for POST /programs/{program_id}/consent/grant."""

    consent_text: str  # Required: RGPD text string accepted by the patient at grant time


class ConsentOut(BaseModel):
    """Full response including consent_text — returned after grant."""

    model_config = ConfigDict(from_attributes=True)

    consent_id: uuid.UUID | None
    program_id: uuid.UUID
    granted: bool
    granted_at: datetime | None
    withdrawn_at: datetime | None
    consent_text: str | None  # May be None for rows migrated before this column was added


class ConsentStatus(BaseModel):
    """Consent status response — used for GET and withdraw responses."""

    model_config = ConfigDict(from_attributes=True)

    consent_id: uuid.UUID | None
    program_id: uuid.UUID
    granted: bool
    granted_at: datetime | None
    withdrawn_at: datetime | None
