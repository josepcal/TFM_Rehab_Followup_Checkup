from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.auth import current_principal
from app.config import get_settings
from app.context import current_user, current_role

settings = get_settings()
try:
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
except ModuleNotFoundError:  # pragma: no cover - lets isolated unit tests import models without psycopg2
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

DB_ROLE_BY_APP_ROLE = {
    "medical": "ftm_medical_specialist",
    "admin": "ftm_medical_specialist",
    "patient": "ftm_patient",
    "technician": "ftm_technician",
}


class Base(DeclarativeBase):
    pass


def _resolve_identity_id(session, external_subject: str) -> str | None:
    """Map the IdP subject to the internal identity_id expected by RLS.

    The SQL RLS policies are written against ``app.identity_id`` (a UUID from
    ``clinical.app_user.identity_id``), while the JWT exposes an external
    subject.  Resolve it once at session start and keep the setting local to
    the transaction.
    """
    return session.execute(
        text("SELECT clinical.identity_id_for_subject(:external_subject)::text"),
        {"external_subject": external_subject},
    ).scalar_one_or_none()


def _apply_rls(session, principal: dict | None = None) -> None:
    """Inyecta el contexto de autorización como variables LOCALES a la transacción.

    ``is_local=true`` hace que se limpien solas al cerrar la transacción (a
    prueba de pooling). Las policies de Postgres usan ``app.identity_id``; se
    mantienen ``app.user``/``app.role`` por compatibilidad y trazabilidad.
    """
    uid = principal.get("sub") if principal is not None else current_user.get()
    role = principal.get("role") if principal is not None else current_role.get()
    if uid is not None:
        session.execute(text("SELECT set_config('app.user', :u, true)"), {"u": uid})
        identity_id = _resolve_identity_id(session, uid)
        if identity_id is not None:
            session.info["identity_id"] = identity_id
            session.execute(
                text("SELECT set_config('app.identity_id', :identity_id, true)"),
                {"identity_id": identity_id},
            )
    if role is not None:
        session.execute(text("SELECT set_config('app.role', :r, true)"), {"r": role})
        db_role = DB_ROLE_BY_APP_ROLE.get(role)
        if db_role is not None:
            session.execute(text(f"SET LOCAL ROLE {db_role}"))


# Depende de current_principal => garantiza que los contextvars están fijados
# ANTES de abrir la transacción y ejecutar cualquier query.
def get_db(principal: dict = Depends(current_principal)):
    session = SessionLocal()
    try:
        with session.begin():
            _apply_rls(session, principal)
            yield session
    finally:
        session.close()


def system_session():
    """Sesión para el worker (sin petición HTTP): contexto de sistema."""
    session = SessionLocal()
    session.begin()
    session.execute(text("SELECT set_config('app.user', 'system', true)"))
    session.execute(text("SELECT set_config('app.role', 'system', true)"))
    session.execute(text("SET LOCAL ROLE ftm_worker"))
    return session
