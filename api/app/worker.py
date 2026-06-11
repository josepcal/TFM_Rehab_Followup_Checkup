"""Worker: consume jobs de la cola, ejecuta la funcion registrada sobre el WAV,
guarda metricas bajo pseudonimo y (opcional) pide insight a la IA. Contexto de sistema."""
import time

from sqlalchemy import text

import app.analysis.functions  # noqa: F401  (registra las funciones)
from app.analysis import registry
from app.db import system_session
from app.jobs import AnalysisJob, claim_one
from app.metrics.models import RecordingMetrics
from app.recording.models import ExerciseRecording
from app.storage import get_storage

POLL_SECONDS = 3


def _pseudonym_for(session, recording_id):
    """Resuelve el pseudonimo del paciente de esa grabacion (zona identificada -> pseudonimo)."""
    row = session.execute(text(
        """
        SELECT pm.pseudonym_id
        FROM recording.exercise_recording r
        JOIN clinical.program_exercise pe ON pe.id = r.program_exercise_id
        JOIN clinical.rehab_program rp     ON rp.id = pe.program_id
        JOIN clinical.diagnostic d         ON d.id = rp.diagnostic_id
        JOIN clinical.pseudonym_map pm     ON pm.patient_id = d.patient_id
        WHERE r.id = :rid
        """
    ), {"rid": str(recording_id)}).first()
    return row[0] if row else None


def process_one() -> bool:
    session = system_session()
    storage = get_storage()
    try:
        job = claim_one(session)
        if job is None:
            session.commit()
            return False
        try:
            rec = session.get(ExerciseRecording, job.recording_id)
            wav_path = storage.download_to_tmp(rec.storage_uri)
            metrics = registry.run(job.function_name, wav_path, {})
            pseudonym = _pseudonym_for(session, job.recording_id)
            session.add(RecordingMetrics(
                recording_id=job.recording_id,
                pseudonym_id=pseudonym,
                function_name=job.function_name,
                metrics=metrics,
            ))
            job.status = "done"
        except Exception as e:
            job.status = "error"
            job.error = str(e)[:500]
        session.commit()
        return True
    finally:
        session.close()


def main():
    print("FTM worker iniciado. Funciones:", registry.list_functions())
    while True:
        try:
            worked = process_one()
        except Exception as e:
            print("error en loop:", e)
            worked = False
        if not worked:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
