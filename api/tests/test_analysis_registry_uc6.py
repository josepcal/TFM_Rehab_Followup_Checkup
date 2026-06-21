import pytest

from app.analysis import registry


def test_registry_resolves_registered_function_by_name(monkeypatch):
    monkeypatch.setitem(registry.REGISTRY, "fake_metric_v1", lambda wav_path, params: {
        "wav_path": wav_path,
        "threshold": params["threshold"],
    })

    result = registry.run("fake_metric_v1", "/tmp/audio.wav", {"threshold": 0.75})

    assert result == {"wav_path": "/tmp/audio.wav", "threshold": 0.75}


def test_registry_rejects_unknown_function_name():
    with pytest.raises(registry.UnknownAnalysisFunction) as exc_info:
        registry.run("missing_metric_v1", "/tmp/audio.wav", {})

    assert exc_info.value.name == "missing_metric_v1"
    assert "missing_metric_v1" in str(exc_info.value)


def test_register_analysis_decorator_keeps_original_callable(monkeypatch):
    monkeypatch.setattr(registry, "REGISTRY", {})

    @registry.register_analysis("decorated_metric_v1")
    def metric(wav_path, params):
        return {"ok": True}

    assert registry.REGISTRY["decorated_metric_v1"] is metric
    assert registry.run("decorated_metric_v1", "audio.wav", {}) == {"ok": True}
