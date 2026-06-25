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

    return result
