"""IAM router — UC-15 audit log endpoint."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.iam.models import EventLog
from app.iam.schemas import EventLogEntry

router = APIRouter(prefix="/iam", tags=["iam"])


@router.get("/audit-log", response_model=list[EventLogEntry])
def get_audit_log(
    actor_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _principal: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[EventLogEntry]:
    """Return audit log entries ordered by occurred_at descending.

    Restricted to the admin role.
    Requires migration 0013 (GRANT SELECT ON audit.event_log TO ftm_medical_specialist).
    """
    stmt = select(EventLog).order_by(EventLog.occurred_at.desc())

    if actor_id is not None:
        stmt = stmt.where(EventLog.actor_id == actor_id)
    if entity_type is not None:
        stmt = stmt.where(EventLog.entity_type == entity_type)
    if from_ts is not None:
        stmt = stmt.where(EventLog.occurred_at >= from_ts)
    if to_ts is not None:
        stmt = stmt.where(EventLog.occurred_at <= to_ts)

    stmt = stmt.limit(limit).offset(offset)

    rows = db.scalars(stmt).all()
    return [EventLogEntry.model_validate(row) for row in rows]
