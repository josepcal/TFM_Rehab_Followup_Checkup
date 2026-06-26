import time
import uuid
from types import SimpleNamespace

import pytest

from app import worker
from app.analysis import registry


def test_worker_timeout_handling_with_slow_fake_function(monkeypatch):
    monkeypatch.setattr(worker, "ANALYSIS_TIMEOUT_SECONDS", 1)
    monkeypatch.setitem(registry.REGISTRY, "slow_metric_v1", lambda _wav, _params: time.sleep(2) or {})

    with pytest.raises(worker.AnalysisExecutionTimeout):
        worker._run_with_timeout("slow_metric_v1", "/tmp/audio.wav", {})


def test_worker_captures_function_exception_and_marks_job_error(monkeypatch):
    recording_id = uuid.uuid4()
    pseudonym_id = uuid.uuid4()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        recording_id=recording_id,
        function_name="raising_metric_v1",
        status="pending",
        error_detail=None,
        updated_at=None,
    )
    recording = SimpleNamespace(recording_id=recording_id, storage_uri="recordings/audio.wav")
    captured = {}

    class FakeSession:
        def get(self, model, key):
            return recording

        def commit(self):
            captured["committed"] = True

        def rollback(self):  # pragma: no cover - should not be called in this test
            captured["rolled_back"] = True

        def close(self):
            captured["closed"] = True

    class FakeStorage:
        def download_to_tmp(self, storage_uri):
            return "/tmp/audio.wav"

    def raise_error(_name, _wav_path, _params):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker, "system_session", lambda: FakeSession())
    monkeypatch.setattr(worker, "get_storage", lambda: FakeStorage())
    monkeypatch.setattr(worker, "claim_one", lambda session: job)
    monkeypatch.setattr(worker, "_pseudonym_for", lambda session, rid: pseudonym_id)
    monkeypatch.setattr(worker.registry, "run", raise_error)
    monkeypatch.setattr(worker, "_persist_error", lambda session, **kwargs: captured.update(kwargs))
    monkeypatch.setattr(worker, "_persist_success", lambda session, **kwargs: pytest.fail("success must not persist"))

    assert worker.process_one() is True
    assert job.status == "error"
    assert "RuntimeError: boom" in job.error_detail
    assert captured["recording_id"] == recording_id
    assert captured["pseudonym_id"] == pseudonym_id
    assert captured["function_name"] == "raising_metric_v1"
    assert "RuntimeError: boom" in captured["error_detail"]
    assert captured["committed"] is True
    assert captured["closed"] is True


def test_worker_success_flow_persists_raw_json_under_pseudonym(monkeypatch):
    recording_id = uuid.uuid4()
    pseudonym_id = uuid.uuid4()
    raw_json = {"jitter": 0.12, "nested": {"flag": True}}
    job = SimpleNamespace(
        id=uuid.uuid4(),
        recording_id=recording_id,
        function_name="ok_metric_v1",
        status="pending",
        error_detail=None,
        updated_at=None,
    )
    recording = SimpleNamespace(recording_id=recording_id, storage_uri="recordings/audio.wav")
    captured = {}

    class FakeSession:
        def get(self, model, key):
            return recording

        def commit(self):
            captured["committed"] = True

        def rollback(self):  # pragma: no cover - should not be called in this test
            captured["rolled_back"] = True

        def close(self):
            captured["closed"] = True

    class FakeStorage:
        def download_to_tmp(self, storage_uri):
            return "/tmp/audio.wav"

    monkeypatch.setattr(worker, "system_session", lambda: FakeSession())
    monkeypatch.setattr(worker, "get_storage", lambda: FakeStorage())
    monkeypatch.setattr(worker, "claim_one", lambda session: job)
    monkeypatch.setattr(worker, "_pseudonym_for", lambda session, rid: pseudonym_id)
    monkeypatch.setattr(worker, "_run_with_timeout", lambda name, wav_path, params: raw_json)
    monkeypatch.setattr(worker, "_persist_success", lambda session, **kwargs: captured.update(kwargs))
    monkeypatch.setattr(worker, "_persist_error", lambda session, **kwargs: pytest.fail("error must not persist"))

    assert worker.process_one() is True
    assert job.status == "done"
    assert job.error_detail is None
    assert captured["recording_id"] == recording_id
    assert captured["pseudonym_id"] == pseudonym_id
    assert captured["function_name"] == "ok_metric_v1"
    assert captured["raw_json"] == raw_json
    assert captured["committed"] is True
    assert captured["closed"] is True


def test_worker_flatten_metrics_keeps_queryable_paths_without_semantic_interpretation():
    rows = worker._flatten_metrics(
        {
            "summary": {"jitter": 0.12, "valid": True},
            "segments": [{"f0": 120}, {"f0": None}],
        }
    )

    assert rows == [
        ("segments[0].f0", 120),
        ("segments[1].f0", None),
        ("summary.jitter", 0.12),
        ("summary.valid", True),
    ]


def test_worker_rejects_non_dict_analysis_result(monkeypatch):
    monkeypatch.setitem(registry.REGISTRY, "bad_metric_v1", lambda _wav, _params: ["not", "a", "dict"])

    with pytest.raises(TypeError):
        worker._run_with_timeout("bad_metric_v1", "/tmp/audio.wav", {})


def test_reanalysis_overwrite_is_implemented_as_upsert_on_recording_id():
    import inspect

    source = inspect.getsource(worker._persist_success)

    assert "on_conflict_do_update" in source
    assert "MetricResult.recording_id" in source
    assert "delete(RecordingMetric)" in source


def test_worker_maps_metric_paths_to_setup_metric_definition_ids():
    analysis_setup_id = uuid.uuid4()
    raw_metric_id = uuid.uuid4()
    already_aligned_metric_id = uuid.uuid4()
    captured = {}

    class FakeSession:
        def execute(self, _stmt, params):
            captured["params"] = params
            return [
                SimpleNamespace(metric_def_id=raw_metric_id, path="raw.jitter_local_pct"),
                SimpleNamespace(metric_def_id=already_aligned_metric_id, path="domains.voice_stability"),
            ]

    result = worker._metric_definition_ids_for(
        FakeSession(),
        analysis_setup_id,
        ["jitter_local_pct", "domains.voice_stability", "unknown_metric"],
    )

    assert result == {
        "jitter_local_pct": raw_metric_id,
        "domains.voice_stability": already_aligned_metric_id,
        "unknown_metric": None,
    }
    assert captured["params"]["analysis_setup_id"] == str(analysis_setup_id)
    assert "raw.jitter_local_pct" in captured["params"]["paths"]


def test_worker_extracts_metric_result_note_from_recommendations():
    assert worker._metric_result_note(
        {
            "jitter_local_pct": 2.5,
            "recommendations": [
                " Pitch variation is elevated. ",
                "",
                123,
                "Try a steady tone.",
            ],
        }
    ) == "Pitch variation is elevated.\nTry a steady tone."

    assert worker._metric_result_note({"jitter_local_pct": 0.5}) is None


def test_worker_import_loads_setup_fk_metadata():
    from app.db import Base

    assert "setup.analysis_setup" in Base.metadata.tables
    assert "setup.metric_definition" in Base.metadata.tables
