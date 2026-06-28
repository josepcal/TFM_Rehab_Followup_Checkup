import logging

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

import app.analysis.functions  # noqa: F401  (registra las funciones de audio al arrancar)
from app.analysis.router import router as analysis_router
from app.catalog.router import router as catalog_router
from app.clinical.consent_router import router as consent_router
from app.clinical.diagnostic_router import router as diagnostic_router
from app.clinical.program_router import router as program_router
from app.clinical.router import router as clinical_router
from app.config import get_settings
from app.context import current_user
from app.db import AuditSessionLocal, SessionLocal, _resolve_identity_id
from app.iam.audit_service import write_event_log
from app.iam.router import router as iam_router
from app.metrics.router import router as metrics_router
from app.recording.router import router as recording_router
from app.followup.router import router as followup_router
from app.norms.router import router as norms_router
from app.reporting.router import router as reporting_router

logger = logging.getLogger(__name__)

settings = get_settings()

# root_path="/api": nginx enruta /api/ -> esta app (con trailing slash, ver CHANGES.md)
app = FastAPI(title="FTM API", root_path="/api")


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.app_env, "auth": settings.auth_mode}


for r in (clinical_router, catalog_router, analysis_router, diagnostic_router, program_router,
          recording_router, metrics_router, reporting_router, followup_router, norms_router,
          consent_router, iam_router):
    app.include_router(r)


class AuditMiddleware(BaseHTTPMiddleware):
    """Fire-and-forget audit middleware.

    Intercepts every mutating HTTP request (POST, PUT, PATCH, DELETE) and writes one row
    into audit.event_log AFTER the response has been produced.  Uses a raw SessionLocal()
    connection (pool login user — no SET LOCAL ROLE) because the audit schema has no grants
    to any application RLS role.

    Failures are swallowed and logged — an audit write error MUST NOT affect the HTTP response.

    Registered last (after all include_router calls) so it wraps the outermost layer and
    the auth middleware has already set the current_user ContextVar before dispatch runs.
    """

    EXCLUDED: frozenset = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})
    METHOD_TO_ACTION: dict = {
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }

    @staticmethod
    def _extract_sub(request: Request) -> str | None:
        """Extract Keycloak sub from the JWT without full validation.

        The token was already validated by current_principal() inside the handler.
        We only need the sub claim for audit attribution — re-parsing is safe here
        because we are not making authorization decisions, just recording who acted.
        """
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        try:
            import base64, json as _json
            token = auth.split(" ", 1)[1]
            payload_b64 = token.split(".")[1]
            # Add padding if needed
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            claims = _json.loads(base64.urlsafe_b64decode(payload_b64))
            return claims.get("sub")
        except Exception:
            return None

    async def dispatch(self, request: Request, call_next):
        # request.state is a plain object shared by reference between the middleware
        # frame and the handler — mutations from the handler ARE visible here after
        # call_next returns. ContextVars are NOT: call_next runs in a copy_context()
        # so handler writes never propagate back to the middleware frame.
        request.state.audit_entity_id = None
        response = await call_next(request)

        if request.method in self.METHOD_TO_ACTION and request.url.path not in self.EXCLUDED:
            sub = self._extract_sub(request)
            db = AuditSessionLocal()
            try:
                action = self.METHOD_TO_ACTION[request.method]
                with db.begin():
                    raw_id = _resolve_identity_id(db, sub) if sub else None
                    actor_id = None
                    if raw_id is not None:
                        import uuid as _uuid
                        actor_id = _uuid.UUID(raw_id) if isinstance(raw_id, str) else raw_id
                    write_event_log(
                        entity_type=request.url.path,
                        entity_id=request.state.audit_entity_id,
                        action=action,
                        actor_id=actor_id,
                        payload=None,
                        db=db,
                    )
            except Exception:
                logger.error("audit write failed", exc_info=True)
            finally:
                db.close()

        return response


# IMPORTANT: add_middleware wraps in reverse order — last added = outermost = runs first.
# AuditMiddleware must be added AFTER all include_router calls so it runs after auth has
# populated the current_user ContextVar.
app.add_middleware(AuditMiddleware)
