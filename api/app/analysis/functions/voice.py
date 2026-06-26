from app.analysis.registry import register_analysis, InsufficientSignalError
from app.analysis.vendor.dysarthria_analysis import (
    analyze_sustained_vowel,
    ensure_pcm_wav,
)

import math
import parselmouth

FUNCTION_VERSION = "v1"

# Engineering default — pending clinical validation
MIN_VOICED_SECONDS = 1.0

# Function colocada aqui para aislar de Vendor analysis dystrhasia_analysis.py (calculo acustico puro)
def build_recommendations(result: dict) -> list[str]:
    """Build clinical recommendations for the sustained-phonation result.

    This mirrors the previous ExerciseAnalysisModal thresholds, but keeps the
    recommendation text with the analysis output so the worker can persist it in
    metrics.metric_result.note.
    """
    recommendations: list[str] = []
    duration = result.get("phonation_duration_sec")
    jitter = result.get("jitter_local_pct")
    shimmer = result.get("shimmer_local_pct")
    hnr = result.get("hnr_db")
    volume_std = result.get("volume_std_db")

    if duration is not None and duration < 5:
        recommendations.append(
            "Try to sustain the vowel for longer. Aim for at least 10 seconds."
        )
    if jitter is not None and jitter > 2:
        recommendations.append(
            "Pitch variation (jitter) is elevated. Focus on maintaining a steady tone."
        )
    if shimmer is not None and shimmer > 5:
        recommendations.append(
            "Amplitude variation (shimmer) is elevated. Try to keep a consistent volume."
        )
    if hnr is not None and hnr < 10:
        recommendations.append(
            "Noise in the voice signal is high. Reduce background noise and try again in a quieter environment."
        )
    if volume_std is not None and volume_std > 5:
        recommendations.append(
            "Volume is unstable during the recording. Try to maintain even breath support."
        )

    if not recommendations:
        recommendations.append(
            "Great performance! All acoustic metrics are within acceptable ranges. Keep up the work."
        )

    return recommendations


@register_analysis("dysarthria_analysis_v1")
def sustained_phonation(wav_path: str, params: dict) -> dict:
    params = params or {}

    normalized_path = ensure_pcm_wav(wav_path)

    # Defensive path: malformed/corrupt audio
    try:
        result = analyze_sustained_vowel(
            normalized_path,
            f0min=params.get("f0min", 75),
            f0max=params.get("f0max", 400),
        )
    except parselmouth.PraatError as exc:
        raise InsufficientSignalError(
            "Audio could not be processed by Praat (possible corruption or unsupported format)"
        ) from exc

    duration = result.get("phonation_duration_sec")

    # NaN / None detection
    has_invalid = any(
        v is None or (isinstance(v, float) and math.isnan(v))
        for v in result.values()
    )

    # Guard 1: Silence / no voiced signal
    if has_invalid:
        raise InsufficientSignalError(
            "Silence-only or non-voiced recording (NaN metrics detected)"
        )

    # Guard 2: Duration threshold (param-driven)
    min_duration = params.get("min_duration_sec", MIN_VOICED_SECONDS)

    if duration is None or duration < min_duration:
        raise InsufficientSignalError(
            f"Voiced signal too short ({duration:.2f}s < {min_duration}s minimum)"
        )

    return {
        **result,
        "recommendations": build_recommendations(result),
    }
