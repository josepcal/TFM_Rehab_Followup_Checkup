"""Anonymisation boundary: assembles the LLM payload under the ``ftm_ai`` DB role.

Reading the metrics through this service — and only through it — is what makes the
boundary a control rather than a comment. ``ftm_ai`` holds SELECT on
``metrics.v_ai_payload`` and nothing else: it cannot reach ``clinical.pseudonym_map``,
``clinical.patient``, or even the raw ``metrics.metric_result``. If a future change tries
to enrich the payload with identity data, PostgreSQL denies it.

The generic ``ftm_app`` connection must never be used for this: it inherits every role
(0004_runtime_grants), so it *can* read identity. The RLS that protects the boundary only
applies while ``ftm_ai`` is actually assumed — that is what ``ai_session()`` does.

Note the entry point is (pseudonym, exercise), not a ``result_id``. The view deliberately
omits ``result_id`` because that key is what links a metric back to a recording and hence
to a patient; the anonymous side of the boundary must not be able to name it. Callers on
the identified side resolve the pseudonym first, then cross over with it.
"""

from datetime import date
from uuid import UUID

from sqlalchemy import text

from app.ai.service import build_payload
from app.db import ai_session

# result_date is nullable and the worker does not populate it today, so a row with no
# date is the current run and everything dated is history. IS NOT DISTINCT FROM makes the
# NULL case comparable; NULLS FIRST puts the undated (newest) run at the top.
_LATEST_DATE = text(
    """
    SELECT result_date
    FROM metrics.v_ai_payload
    WHERE pseudonym_id = :pseudonym_id AND exercise = :exercise
    ORDER BY result_date DESC NULLS FIRST
    LIMIT 1
    """
)

_METRICS_AT = text(
    """
    SELECT metric_path, value_num
    FROM metrics.v_ai_payload
    WHERE pseudonym_id = :pseudonym_id
      AND exercise = :exercise
      AND result_date IS NOT DISTINCT FROM :result_date
    """
)

_HISTORY = text(
    """
    SELECT result_date, metric_path, value_num
    FROM metrics.v_ai_payload
    WHERE pseudonym_id = :pseudonym_id
      AND exercise = :exercise
      AND result_date IS DISTINCT FROM :result_date
      AND result_date IS NOT NULL
    ORDER BY result_date DESC, metric_path
    LIMIT :limit
    """
)


def load_ai_payload(
    pseudonym_id: UUID,
    exercise: str,
    *,
    criteria: dict | None = None,
    history_limit: int = 20,
) -> dict | None:
    """Build the pseudonymised LLM payload for one pseudonym + exercise, read as ``ftm_ai``.

    Returns ``None`` when the view yields no rows (nothing analysed yet, or every metric
    null), so the caller degrades instead of sending an empty payload.
    """
    session = ai_session()
    try:
        keys = {"pseudonym_id": str(pseudonym_id), "exercise": exercise}
        latest: date | None = session.execute(_LATEST_DATE, keys).scalar_one_or_none()

        current = session.execute(_METRICS_AT, {**keys, "result_date": latest}).all()
        if not current:
            return None

        history_rows = session.execute(
            _HISTORY, {**keys, "result_date": latest, "limit": history_limit}
        ).all()

        history: dict[str, dict[str, float]] = {}
        for row in history_rows:
            history.setdefault(str(row.result_date), {})[row.metric_path] = row.value_num

        return build_payload(
            pseudonym_id=pseudonym_id,
            exercise=exercise,
            criteria=criteria,
            current_metrics={row.metric_path: row.value_num for row in current},
            history=[{"result_date": d, "metrics": m} for d, m in history.items()],
        )
    finally:
        # Read-only boundary: never commit from this session.
        session.rollback()
        session.close()
