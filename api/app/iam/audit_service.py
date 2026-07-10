"""Audit service for UC-15.

write_event_log inserts one row into audit.event_log using the caller-owned session.
The caller (AuditMiddleware) is responsible for opening/closing the session and
for wrapping the call in a transaction via db.begin().
"""

import uuid

from sqlalchemy.orm import Session

from app.iam.models import EventLog


def write_event_log(
    *,
    entity_type: str,
    entity_id: uuid.UUID | None,
    action: str,
    actor_id: uuid.UUID | None,
    payload: dict | None,
    db: Session,
    outcome: str = "success",
) -> None:
    """Insert one audit event row.

    ``outcome`` is ``'success'`` for a mutation that was carried out, or ``'denied'``
    for a rejected attempt recorded for intrusion detection (OWASP A09).

    Does NOT open or close its own session — the caller owns the session lifetime.
    The session MUST be a raw SessionLocal() (pool login user, no SET LOCAL ROLE)
    because the audit schema has no grants to any application RLS role.
    """
    entry = EventLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        payload=payload,
        outcome=outcome,
    )
    db.add(entry)
    db.flush()
