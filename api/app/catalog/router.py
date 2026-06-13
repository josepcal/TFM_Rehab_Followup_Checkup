from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.analysis.registry import list_functions
from app.auth import require_role
from app.catalog.models import RehabExercise
from app.db import get_db

router = APIRouter(tags=["catalog"])


@router.get("/exercises")
def list_exercises(_=Depends(require_role("medical", "technician", "patient")),
                   db=Depends(get_db)):
    rows = db.scalars(select(RehabExercise)).all()
    return [{"id": str(e.id), "nombre": e.nombre, "tipo": e.tipo} for e in rows]


@router.get("/analysis-functions")
def analysis_functions(_=Depends(require_role("medical", "technician"))):
    # nombres registrados en el backend (agnostico)
    return {"functions": list_functions()}
