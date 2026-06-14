from fastapi import FastAPI

import app.analysis.functions  # noqa: F401  (registra las funciones de audio al arrancar)
from app.analysis.router import router as analysis_router
from app.catalog.router import router as catalog_router
from app.clinical.diagnostic_router import router as diagnostic_router
from app.clinical.program_router import router as program_router
from app.clinical.router import router as clinical_router
from app.config import get_settings
from app.metrics.router import router as metrics_router
from app.recording.router import router as recording_router
from app.reporting.router import router as reporting_router

settings = get_settings()

# root_path="/api": nginx enruta /api/ -> esta app (con trailing slash, ver CHANGES.md)
app = FastAPI(title="FTM API", root_path="/api")


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.app_env, "auth": settings.auth_mode}


for r in (clinical_router, catalog_router, analysis_router, diagnostic_router, program_router,
          recording_router, metrics_router, reporting_router):
    app.include_router(r)
