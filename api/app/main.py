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
from app.db import AuditSessionLocal, _resolve_identity_id
from app.iam.audit_service import write_event_log
from app.iam.router import router as iam_router
from app.metrics.router import router as metrics_router
from app.recording.router import router as recording_router
from app.followup.router import router as followup_router
from app.norms.router import router as norms_router
from app.reporting.router import router as reporting_router

logger = logging.getLogger(__name__)

settings = get_settings()

# root_path="/api": nginx enruta /api/ -> esta app (con trailing slash, ver CHANGES.md).
# nginx proxies ALL of /api/ to the app, so /api/docs and /api/openapi.json would be
# reachable in prod — disable the interactive docs and the OpenAPI schema there. The
# schema is an attack map for a clinical API; hiding the UI alone is not enough.
_docs_enabled = settings.app_env != "prod"
app = FastAPI(
    title="FTM API",
    root_path="/api",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)


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

    async def dispatch(self, request: Request, call_next):
        # request.state is a plain object shared by reference between the middleware
        # frame and the handler — mutations from the handler ARE visible here after
        # call_next returns. ContextVars are NOT: call_next runs in a copy_context()
        # so handler writes never propagate back to the middleware frame.
        request.state.audit_entity_id = None
        request.state.auth_sub = None
        request.state.audit_read = False
        response = await call_next(request)

        # Audit two kinds of request, and NOTHING else:
        #   - 2xx           → outcome='success' (the action was carried out / read served)
        #   - 401 / 403     → outcome='denied'  (rejected access — recorded for
        #                     intrusion detection: repeated BOLA/BFLA probing, A09)
        # Other statuses (400 validation, 404, 5xx) are neither an action nor an
        # authorization decision, so they are not audited. For a denied request the
        # sub is only trustworthy when it was validated (403 after a valid token);
        # a 401 leaves auth_sub None and the attempt is recorded with actor NULL.
        #
        # A mutation qualifies by method. A read qualifies only if the endpoint opted
        # in via Depends(audit_read) — this keeps catalogue/reference GETs out of the
        # trail while capturing reads of personal/clinical data (clinical snooping).
        status = response.status_code
        excluded = request.url.path in self.EXCLUDED
        is_mutation = request.method in self.METHOD_TO_ACTION and not excluded
        is_read = (
            request.method == "GET"
            and not excluded
            and getattr(request.state, "audit_read", False)
        )
        action = None
        if is_mutation:
            action = self.METHOD_TO_ACTION[request.method]
        elif is_read:
            action = "read"

        # A denied read is the clinical-snooping signal, but object-level guards
        # answer 404 (not 403) to avoid confirming a resource exists. So on a
        # marked read we also treat 404 as 'denied': a doctor probing another
        # patient's ids leaves a trail. The cost is that a genuinely stale id also
        # records a denied read — acceptable, and on the safe side for A09.
        denied_statuses = (401, 403, 404) if is_read else (401, 403)
        outcome = None
        if action is not None and 200 <= status < 300:
            outcome = "success"
        elif action is not None and status in denied_statuses:
            outcome = "denied"

        if outcome is not None:
            sub = getattr(request.state, "auth_sub", None)
            db = AuditSessionLocal()
            try:
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
                        outcome=outcome,
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
