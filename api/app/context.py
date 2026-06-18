from contextvars import ContextVar

# Identidad de la petición, derivada del token de Keycloak.
# get_db() las lee para alimentar la RLS de Postgres (set_config 'app.identity_id',
# mantiene 'app.user'/'app.role' como contexto auxiliar y hace SET LOCAL ROLE).
current_user: ContextVar[str | None] = ContextVar("current_user", default=None)
current_role: ContextVar[str | None] = ContextVar("current_role", default=None)
