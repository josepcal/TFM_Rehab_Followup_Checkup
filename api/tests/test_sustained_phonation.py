import math

from app.analysis.functions.voice import sustained_phonation
from app.analysis.registry import InsufficientSignalError
from pathlib import Path
from unittest.mock import patch


FIXTURES = Path(__file__).parent / "fixtures" / "audio"
CLEAR_FIXTURE_PATH = FIXTURES / "clear_vowel_12s.wav"


def test_clear_fixture_returns_five_finite_metrics():
    result = sustained_phonation(str(CLEAR_FIXTURE_PATH), {})

    expected_keys = {
        "phonation_duration_sec",
        "jitter_local_pct",
        "shimmer_local_pct",
        "hnr_db",
        "volume_std_db",
    }

    assert set(result.keys()) == expected_keys

    for value in result.values():
        assert value is not None
        assert not math.isnan(value)

    # Loose range assertions
    assert 10.0 <= result["phonation_duration_sec"] <= 13.0
    assert result["jitter_local_pct"] >= 0.0
    assert result["shimmer_local_pct"] >= 0.0
    assert result["hnr_db"] > 0.0
    assert result["volume_std_db"] >= 0.0



SILENCE_FIXTURE_PATH = FIXTURES / "silence_3s.wav"


def test_silence_fixture_raises_insufficient_signal_nan_path():
    try:
        sustained_phonation(str(SILENCE_FIXTURE_PATH), {})
        assert False, "Expected InsufficientSignalError"
    except InsufficientSignalError as exc:
        message = str(exc).lower()

    assert "nan" in message or "non-voiced" in message or "silence" in message
    assert "too short" not in message


BELOW_FLOOR_FIXTURE_PATH = FIXTURES / "below_floor_03s.wav"


def test_below_floor_fixture_raises_duration_floor_path():
    try:
        sustained_phonation(str(BELOW_FLOOR_FIXTURE_PATH), {})
        assert False, "Expected InsufficientSignalError"
    except InsufficientSignalError as exc:
        message = str(exc).lower()

    assert "too short" in message or "minimum" in message
    assert "nan" not in message
    assert "silence" not in message


NOISY_FIXTURE_PATH = FIXTURES / "noisy_background.wav"


def test_noisy_recording_returns_result_with_worse_quality_than_clean():
    clean = sustained_phonation(str(CLEAR_FIXTURE_PATH), {})
    noisy = sustained_phonation(str(NOISY_FIXTURE_PATH), {})

    assert clean is not None
    assert noisy is not None

    assert noisy["jitter_local_pct"] > clean["jitter_local_pct"]
    assert noisy["shimmer_local_pct"] > clean["shimmer_local_pct"]
    assert noisy["hnr_db"] < clean["hnr_db"]


def test_sustained_phonation_is_deterministic():
    first = sustained_phonation(str(CLEAR_FIXTURE_PATH), {})
    second = sustained_phonation(str(CLEAR_FIXTURE_PATH), {})

    assert first == second


@patch("app.analysis.vendor.dysarthria_analysis.shutil.which", return_value=None)
def test_ffmpeg_unavailable_fallback_still_returns_result(mock_which):
    result = sustained_phonation(str(CLEAR_FIXTURE_PATH), {})

    expected_keys = {
        "phonation_duration_sec",
        "jitter_local_pct",
        "shimmer_local_pct",
        "hnr_db",
        "volume_std_db",
    }

    assert set(result.keys()) == expected_keys
