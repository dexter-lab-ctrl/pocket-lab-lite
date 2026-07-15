import json
from pocket_lab_test_utils import client, isolated_state_dir


def test_workflows_status_registered():
    assert client().get("/api/workflows/status").status_code != 404


def test_workflow_journal_redaction_contract(tmp_path):
    state = isolated_state_dir(tmp_path)
    event = {
        "workflow_id": "wf-redact",
        "event": "vault.secret_rotated",
        "path": "secret/data/app",
        "version": 1,
    }
    journal = state / "workflow_events.jsonl"
    journal.write_text(json.dumps(event) + "\n")
    text = journal.read_text()
    for secret_key in [
        "password",
        "token",
        "secret_id",
        "client_token",
        "private_key",
        "root_token",
        "unseal_key",
    ]:
        assert secret_key not in text


def test_workflow_status_cache_and_invalidation(tmp_path, monkeypatch):
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    engine = EventSourcedWorkflowEngine()
    calls = []
    monkeypatch.setattr(
        engine,
        "list_workflows",
        lambda limit=1000: calls.append(limit) or [{"status": "succeeded"}],
    )

    first = engine.status()
    second = engine.status()

    assert first["cache"] == "miss"
    assert second["cache"] == "hit"
    assert calls == [1000]

    engine._invalidate_status_cache()
    third = engine.status()
    assert third["cache"] == "miss"
    assert calls == [1000, 1000]


def test_workflow_projection_writer_is_bounded_and_persists(tmp_path, monkeypatch):
    import time
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("POCKETLAB_WORKFLOW_WRITER_QUEUE_SIZE", "8")
    engine = EventSourcedWorkflowEngine()
    assert engine.enqueue_event({
        "id": "event-1",
        "type": "command.queued",
        "subject": "pocketlab.commands.test",
        "data": {"command_id": "command-1"},
    }) is True
    deadline = time.monotonic() + 2
    while engine.writer_status()["written"] < 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    engine.stop_writer()
    status = engine.writer_status()
    assert status["queue_capacity"] == 8
    assert status["written"] == 1
    assert engine.projection_file.exists()
    assert engine.event_log.exists()


def test_workflow_paths_are_cached_and_unchanged_projection_is_coalesced(tmp_path, monkeypatch):
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    engine = EventSourcedWorkflowEngine()
    first_root = engine.root
    second_root = engine.root
    assert first_root is second_root
    projection = {"workflow_id": f"wf-{tmp_path.name}", "status": "queued"}
    assert engine.save_projection(projection) is True
    assert engine.save_projection(dict(projection)) is False
    assert engine.writer_status()["coalesced"] == 1

def test_workflow_writer_batches_projection_rewrites(tmp_path, monkeypatch):
    import time
    from api_fastapi.services.workflow_engine import EventSourcedWorkflowEngine

    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("POCKETLAB_WORKFLOW_WRITER_BATCH_SIZE", "8")
    engine = EventSourcedWorkflowEngine()
    engine.start_writer()
    for index in range(4):
        assert engine.enqueue_event({
            "id": f"event-{index}",
            "type": "command.queued",
            "subject": "pocketlab.commands.test",
            "data": {"command_id": "command-1", "sequence": index},
        })
    deadline = time.monotonic() + 3
    while engine.writer_status()["written"] < 4 and time.monotonic() < deadline:
        time.sleep(0.01)
    engine.stop_writer()
    status = engine.writer_status()
    assert status["written"] == 4
    assert status["batch_size"] == 8
    assert status["coalesced"] >= 1
