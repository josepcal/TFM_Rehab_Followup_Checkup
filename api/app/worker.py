"""UC-06 worker: dequeue audio-analysis jobs and persist pseudonymised metrics.

The worker is intentionally metric-agnostic. It resolves a deployed function by
name, executes it with a bounded timeout, stores the raw result verbatim, and
adds flattened key/value rows for downstream querying.
"""

from __future__ import annotations

import signal
import json
import os
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

import app.analysis.functions  # noqa: F401  (registers deploy-time analysis functions)
from app.analysis import registry
from app.db import system_session
from app.jobs import AnalysisJob, claim_one
from app.metrics.models import MetricResult, RecordingMetric
import app.analysis.models  # noqa: F401  (loads setup.* tables for SQLAlchemy FK metadata)
from app.recording.models import ExerciseRecording
from app.storage import get_storage

POLL_SECONDS = int(os.getenv("WORKER_POLL_SECONDS", "3"))
ANALYSIS_TIMEOUT_SECONDS = int(os.getenv("ANALYSIS_TIMEOUT_SECONDS", "30"))
DEFAULT_FUNCTION_VERSION = os.getenv("ANALYSIS_FUNCTION_VERSION", "dev")
CODE_SHA = os.getenv("CODE_SHA", os.getenv("GIT_SHA", "unknown"))


class AnalysisExecutionTimeout(TimeoutError):
    """Raised when an analysis function exceeds the configured timeout."""


def _pseudonym_for(session: Session, recording_id):
    """Resolve the patient's pseudonym for a recording using the worker role."""
    row = session.execute(
        text(
            """
            SELECT pm.pseudonym_id
            FROM recording.exercise_recording r
            JOIN clinical.program_exercise pe ON pe.program_exercise_id = r.program_exercise_id
            JOIN clinical.rehab_program rp     ON rp.rehab_program_id = pe.rehab_program_id
            JOIN clinical.diagnostic d         ON d.diagnostic_id = rp.diagnostic_id
            JOIN clinical.pseudonym_map pm     ON pm.patient_id = d.patient_id
            WHERE r.recording_id = :rid
            """
        ),
        {"rid": str(recording_id)},
    ).first()
    return row[0] if row else None


def _run_with_timeout(function_name: str, wav_path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Execute the registered function and bound runtime for the MVP worker.

    The worker runs on Linux in its own process/container, so SIGALRM gives us a
    real interruption boundary for CPU/Python code without moving execution into
    the public API request path.
    """

    def _raise_timeout(_signum, _frame):
        raise AnalysisExecutionTimeout(
            f"analysis function exceeded {ANALYSIS_TIMEOUT_SECONDS}s timeout"
        )

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, ANALYSIS_TIMEOUT_SECONDS)
    try:
        result = registry.run(function_name, wav_path, params)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)

    if not isinstance(result, dict):
        raise TypeError("analysis function must return a dict")
    return result


def _json_scalar(value: Any) -> str | float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _flatten_metrics(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten nested dict/list JSON into stable metric paths.

    The worker does not interpret semantics; it only creates query-friendly
    rows preserving primitive values at deterministic paths.
    """
    if isinstance(value, Mapping):
        rows: list[tuple[str, Any]] = []
        for key in sorted(value.keys(), key=str):
            child = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_metrics(value[key], child))
        return rows
    if isinstance(value, list):
        rows = []
        for idx, item in enumerate(value):
            child = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            rows.extend(_flatten_metrics(item, child))
        return rows
    return [(prefix or "$", value)]


def _function_version(function_name: str) -> str:
    fn = registry.REGISTRY.get(function_name)
    if fn is None:
        return DEFAULT_FUNCTION_VERSION
    return str(getattr(fn, "analysis_version", DEFAULT_FUNCTION_VERSION))


def _analysis_setup_id_for(session: Session, recording_id, function_name: str):
    """Resolve the setup row that configured this recording/function pair."""
    row = session.execute(
        text(
            """
            SELECT s.analysis_setup_id
            FROM recording.exercise_recording r
            JOIN setup.analysis_setup s
              ON s.program_exercise_id = r.program_exercise_id
            WHERE r.recording_id = :recording_id
              AND s.metric_api_endpoint = :function_name
            ORDER BY s.version DESC, s.updated_at DESC
            LIMIT 1
            """
        ),
        {"recording_id": str(recording_id), "function_name": function_name},
    ).first()
    return row[0] if row else None


def _metric_definition_path_candidates(metric_path: str) -> list[str]:
    """Return candidate metric_definition paths for a flattened worker path.

    Analysis functions return raw metric keys such as ``jitter_local_pct``, while
    the SQL-first setup definitions are commonly stored as ``raw.jitter_local_pct``.
    Keep the original first for functions that already return setup-aligned paths.
    """
    candidates = [metric_path]
    if (
        metric_path
        and metric_path != "$"
        and not metric_path.startswith("[")
        and not metric_path.startswith(("raw.", "domains."))
    ):
        candidates.append(f"raw.{metric_path}")
    return candidates


def _metric_definition_ids_for(
    session: Session,
    analysis_setup_id,
    metric_paths: list[str],
) -> dict[str, Any]:
    """Map flattened metric paths to setup.metric_definition IDs when declared."""
    if analysis_setup_id is None or not metric_paths:
        return {}

    candidate_paths = sorted(
        {
            candidate
            for metric_path in metric_paths
            for candidate in _metric_definition_path_candidates(metric_path)
        }
    )
    result = session.execute(
        text(
            """
            SELECT metric_def_id, path
            FROM setup.metric_definition
            WHERE analysis_setup_id = :analysis_setup_id
              AND path = ANY(:paths)
            """
        ),
        {"analysis_setup_id": str(analysis_setup_id), "paths": candidate_paths},
    )
    rows = result.all() if hasattr(result, "all") else result
    by_path = {row.path: row.metric_def_id for row in rows}
    return {
        metric_path: next(
            (
                by_path[candidate]
                for candidate in _metric_definition_path_candidates(metric_path)
                if candidate in by_path
            ),
            None,
        )
        for metric_path in metric_paths
    }


def _persist_success(
    session: Session,
    *,
    recording_id,
    pseudonym_id,
    function_name: str,
    raw_json: dict[str, Any],
) -> None:
    """Upsert one current MetricResult and replace flattened rows."""
    analysis_setup_id = _analysis_setup_id_for(session, recording_id, function_name)
    metric_rows = _flatten_metrics(raw_json)
    metric_def_ids = _metric_definition_ids_for(
        session,
        analysis_setup_id,
        [path for path, _value in metric_rows],
    )
    values = {
        "recording_id": recording_id,
        "pseudonym_id": pseudonym_id,
        "analysis_setup_id": analysis_setup_id,
        "function_name": function_name,
        "function_version": _function_version(function_name),
        "code_sha": CODE_SHA,
        "status": "success",
        "error_detail": None,
        "raw_json": raw_json,
        "extracted_at": datetime.now(UTC)
    }

    print(f"_persist_success : insert MetricResult values {values}")

    stmt = insert(MetricResult).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[MetricResult.recording_id],
        set_=values,
    ).returning(MetricResult.result_id)
    result_id = session.execute(stmt).scalar_one()

    print("_persist_success : MetricResult values inserted")



    session.execute(delete(RecordingMetric).where(RecordingMetric.result_id == result_id))
    for path, value in metric_rows:
        scalar = _json_scalar(value)
        print(" inserting RecordingMetric: result_id:", result_id, "metric_def_id:", metric_def_ids.get(path), "metric_path:", path, "value_num:", scalar if isinstance(scalar, float) else None, "value_text:", scalar if isinstance(scalar, str) else None, "is_null:", value is None)
        session.add(
            RecordingMetric(
                result_id=result_id,
                metric_def_id=metric_def_ids.get(path),
                metric_path=path,
                value_num=scalar if isinstance(scalar, float) else None,
                value_text=scalar if isinstance(scalar, str) else None,
                is_null=value is None,
            )
        )


def _persist_error(
    session: Session,
    *,
    recording_id,
    pseudonym_id,
    function_name: str,
    error_detail: str,
) -> None:
    """Upsert the current MetricResult as error and clear stale metric rows."""
    analysis_setup_id = _analysis_setup_id_for(session, recording_id, function_name)
    values = {
        "recording_id": recording_id,
        "pseudonym_id": pseudonym_id,
        "analysis_setup_id": analysis_setup_id,
        "function_name": function_name,
        "function_version": _function_version(function_name),
        "code_sha": CODE_SHA,
        "status": "error",
        "error_detail": error_detail[:1000],
        "raw_json": None,
        "extracted_at": datetime.now(UTC),
    }
    stmt = insert(MetricResult).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[MetricResult.recording_id],
        set_=values,
    ).returning(MetricResult.result_id)
    result_id = session.execute(stmt).scalar_one()
    session.execute(delete(RecordingMetric).where(RecordingMetric.result_id == result_id))


def _mark_done(job: AnalysisJob) -> None:
    job.status = "done"
    job.error_detail = None
    job.updated_at = datetime.now(UTC)


def _mark_error(job: AnalysisJob, error_detail: str) -> None:
    job.status = "error"
    job.error_detail = error_detail[:1000]
    job.updated_at = datetime.now(UTC)


def process_one() -> bool:
    """Process at most one job. Return True when a job was claimed."""
    session = system_session()
    storage = get_storage()
    try:
        job = claim_one(session)
        if job is None:
            session.commit()
            return False

        pseudonym_id = _pseudonym_for(session, job.recording_id)
        try:
            recording = session.get(ExerciseRecording, job.recording_id)
            if recording is None:
                raise LookupError(f"recording not found: {job.recording_id}")
            if not recording.storage_uri:
                raise ValueError(f"recording has no media URI: {job.recording_id}")
            if pseudonym_id is None:
                raise LookupError(f"pseudonym not found for recording: {job.recording_id}")

            print(f"found recording {job.id} for recording {job.recording_id} function {job.function_name}")

            wav_path = storage.download_to_tmp(recording.storage_uri)
            raw_json = _run_with_timeout(job.function_name, wav_path, {})
            print(f"obtained raw_json for recording {job.id} for recording {job.recording_id} function {job.function_name}: {raw_json}")
            _persist_success(
                session,
                recording_id=job.recording_id,
                pseudonym_id=pseudonym_id,
                function_name=job.function_name,
                raw_json=raw_json,
            )
            _mark_done(job)
        except Exception as exc:  # noqa: BLE001 - worker must isolate job failures
            detail = f"{exc.__class__.__name__}: {exc}"
            if pseudonym_id is not None:
                _persist_error(
                    session,
                    recording_id=job.recording_id,
                    pseudonym_id=pseudonym_id,
                    function_name=job.function_name,
                    error_detail=detail,
                )
            _mark_error(job, detail)

        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    print("FTM worker iniciado. Funciones:", registry.list_functions())
    while True:
        try:
            worked = process_one()
        except Exception as exc:  # noqa: BLE001 - keep polling despite infrastructure errors
            print("error en loop:", exc)
            worked = False
        if not worked:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
