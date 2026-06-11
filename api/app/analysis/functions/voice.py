"""Funciones de análisis de audio que escribe el técnico, registradas por nombre.
Implementaciones de referencia con librosa; defensivas (no deben tumbar el worker)."""
import librosa
import numpy as np

from app.analysis.registry import register_analysis


def _load(wav_path: str):
    y, sr = librosa.load(wav_path, sr=16000, mono=True)
    return y, sr


@register_analysis("sustained_phonation_v1")
def sustained_phonation(wav_path: str, params: dict) -> dict:
    """Rehab de voz: tiempo maximo de fonacion (s) y estabilidad de F0."""
    y, sr = _load(wav_path)
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    thr = 0.1 * float(np.max(rms)) if rms.size and np.max(rms) > 0 else 1.0
    phonation_seconds = float(np.sum(rms > thr) * 256 / sr)

    try:
        f0, _, _ = librosa.pyin(y, fmin=70, fmax=400, sr=sr)
        f0v = f0[~np.isnan(f0)]
        f0_stability = float(1.0 - (np.std(f0v) / np.mean(f0v))) if f0v.size else 0.0
    except Exception:
        f0_stability = 0.0

    return {"phonation_seconds": round(phonation_seconds, 2),
            "f0_stability": round(max(0.0, f0_stability), 3)}


@register_analysis("breathing_cadence_v1")
def breathing_cadence(wav_path: str, params: dict) -> dict:
    """Rehab respiratoria: ciclos, ciclos/min y ratio inhalacion/exhalacion (aprox)."""
    y, sr = _load(wav_path)
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    if rms.size == 0:
        return {"cycles": 0, "cycles_per_min": 0.0, "inhale_exhale_ratio": 0.0}
    peaks = librosa.util.peak_pick(rms, pre_max=5, post_max=5, pre_avg=10,
                                   post_avg=10, delta=0.02, wait=10)
    cycles = int(len(peaks))
    duration = len(y) / sr
    cpm = round(cycles / duration * 60, 1) if duration else 0.0
    voiced = float(np.mean(rms > 0.15 * np.max(rms))) if np.max(rms) > 0 else 0.0
    ratio = round(voiced / (1 - voiced), 2) if 0 < voiced < 1 else 0.0
    return {"cycles": cycles, "cycles_per_min": cpm, "inhale_exhale_ratio": ratio}


@register_analysis("ddk_rate_v1")
def ddk_rate(wav_path: str, params: dict) -> dict:
    """Rehab del habla (diadococinesia 'pa-ta-ka'): silabas/s y regularidad ritmica."""
    y, sr = _load(wav_path)
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    duration = len(y) / sr
    syllables_per_sec = round(len(onsets) / duration, 2) if duration else 0.0
    if len(onsets) > 2:
        ioi = np.diff(onsets)
        cv = float(np.std(ioi) / np.mean(ioi)) if np.mean(ioi) else 1.0
        regularity = round(max(0.0, 1.0 - cv), 3)
    else:
        regularity = 0.0
    return {"syllables_per_sec": syllables_per_sec, "rhythm_regularity": regularity}
