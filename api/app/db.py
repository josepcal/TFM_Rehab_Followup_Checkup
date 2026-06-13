from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.auth import current_principal
from app.config import get_settings
from app.context import current_user, current_role

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _apply_rls(session) -> None:
    """Inyecta los claims del token como variables LOCALES a la transacción.
    is_local=true => se limpian solas al cerrar la transacción (a prueba de pooling)."""
    uid, role = current_user.get(), current_role.get()
    if uid is not None:
        session.execute(text("SELECT set_config('app.user', :u, true)"), {"u": uid})
    if role is not None:
        session.execute(text("SELECT set_config('app.role', :r, true)"), {"r": role})


# Depende de current_principal => garantiza que los contextvars están fijados
# ANTES de abrir la transacción y ejecutar cualquier query.
def get_db(principal: dict = Depends(current_principal)):
    session = SessionLocal()
    try:
        with session.begin():
            _apply_rls(session)
            yield session
    finally:
        session.close()


def system_session():
    """Sesión para el worker (sin petición HTTP): contexto de sistema."""
    session = SessionLocal()
    session.begin()
    session.execute(text("SELECT set_config('app.user', 'system', true)"))
    session.execute(text("SELECT set_config('app.role', 'system', true)"))
    return session
