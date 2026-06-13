import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
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
