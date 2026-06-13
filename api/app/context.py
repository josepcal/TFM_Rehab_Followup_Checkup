from contextvars import ContextVar

# Identidad de la petición, derivada del token de Keycloak.
# get_db() las lee para alimentar la RLS de Postgres (set_config 'app.user'/'app.role').
current_user: ContextVar[str | None] = ContextVar("current_user", default=None)
current_role: ContextVar[str | None] = ContextVar("current_role", default=None)
