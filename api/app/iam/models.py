import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class UserRef(Base):
    __tablename__ = "user_ref"
    __table_args__ = {"schema": "iam"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_id = Column(String, unique=True, index=True, nullable=False)
    perfil = Column(String, nullable=False)


class Consent(Base):
    __tablename__ = "consent"
    __table_args__ = {"schema": "iam"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    tipo = Column(String, nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "iam"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(String)
    accion = Column(String)
    recurso = Column(String)
    ts = Column(DateTime, default=datetime.utcnow)
    ip = Column(String, nullable=True)


class EventLog(Base):
    """ORM model for audit.event_log — maps to the table created in ftm_schema.sql (0001_baseline).

    Uses a plain SessionLocal() connection (pool login user, no SET LOCAL ROLE) so the pool's
    ftm_app user — which owns the audit schema — can INSERT without any RLS grant.
    """

    __tablename__ = "event_log"
    __table_args__ = {"schema": "audit"}

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String, nullable=False)
    # actor_id is a UUID FK to clinical.app_user.identity_id in PostgreSQL,
    # but declared as plain UUID here to avoid cross-schema ORM complexity.
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    payload = Column(JSON, nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=datetime.utcnow)
