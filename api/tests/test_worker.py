
import uuid
import os
from types import SimpleNamespace

from app import worker


def test_worker_processes_real_sustained_phonation_function(monkeypatch):
    recording_id = uuid.uuid4()
    pseudonym_id = uuid.uuid4()

    job = SimpleNamespace(
        id=uuid.uuid4(),
        recording_id=recording_id,
        function_name="dysarthria_analysis_v1",
        status="pending",
        error_detail=None,
        updated_at=None,
    )

    recording = SimpleNamespace(
        recording_id=recording_id,
        storage_uri="tests/fixtures/audio/clear_vowel_12s.wav",
    )

    captured = {}

    class FakeSession:
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass
        def get(self, model, id):
            return recording

    class FakeStorage:
        def download_to_tmp(self, uri):
            # Return absolute path to fixture file
            fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", "audio")
            return os.path.join(fixture_dir, "clear_vowel_12s.wav")

    monkeypatch.setattr(worker, "system_session", lambda: FakeSession(), raising=False)
    monkeypatch.setattr(worker, "get_storage", lambda: FakeStorage(), raising=False)
    monkeypatch.setattr(worker, "claim_one", lambda session: job, raising=False)
    monkeypatch.setattr(worker, "_pseudonym_for", lambda session, rid: pseudonym_id, raising=False)
    monkeypatch.setattr(
        worker,
        "_persist_success",
        lambda session, **kwargs: captured.update(kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        worker,
        "_persist_error",
        lambda session, **kwargs: None,
        raising=False,
    )

    worker.process_one()

    assert captured["function_name"] == "dysarthria_analysis_v1"
    assert set(captured["raw_json"].keys()) == {
        "phonation_duration_sec",
        "jitter_local_pct",
        "shimmer_local_pct",
        "hnr_db",
        "volume_std_db",
    }
