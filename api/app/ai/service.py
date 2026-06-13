"""Frontera de anonimizacion: al LLM solo le llega el vector de metricas + contexto
del ejercicio bajo pseudonimo. Nunca identidad ni audio crudo (FR-04)."""
import json

import httpx

from app.config import get_settings

settings = get_settings()


def build_payload(pseudonym_id, exercise, criteria, current_metrics, history) -> dict:
    return {
        "pseudonym_id": str(pseudonym_id),
        "exercise": exercise,
        "criteria": criteria,
        "current_metrics": current_metrics,
        "history": history or [],
    }


def generate_insight(payload: dict) -> dict:
    """Llama al LLM con SOLO metricas anonimizadas y pide salida JSON estructurada."""
    if not settings.llm_api_key:
        return {"progress": "unknown", "summary": "LLM no configurado (insight omitido)"}

    prompt = (
        "Eres un asistente clinico. A partir de estas metricas anonimizadas de un "
        "ejercicio de rehabilitacion, evalua el progreso. Responde SOLO con JSON: "
        '{"progress": "...", "delta_pct": 0, "flags": [], "summary": "..."}\n\n'
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.llm_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        r.raise_for_status()
        text_out = "".join(b.get("text", "") for b in r.json().get("content", []))
        return json.loads(text_out)
    except Exception as e:  # nunca tumbar el pipeline por la IA (flujo A2)
        return {"progress": "unknown", "summary": f"insight no disponible: {e}"}
