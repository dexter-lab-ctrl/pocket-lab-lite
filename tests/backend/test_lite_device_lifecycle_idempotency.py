from __future__ import annotations

import importlib.util
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_NODE_ID", "pocket-lab-lite-server")
    monkeypatch.setenv("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server")
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    reset_sqlite_path_cache()
    return state


def _events(state: Path) -> list[dict]:
    path = state / "fleet_device_events.json"
    return json.loads(path.read_text()).get("events", []) if path.exists() else []


def test_server_heartbeat_is_transition_based_and_persists_first_seen(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import fleet_registry

    for index in range(100):
        fleet_registry.upsert_agent(
            {
                "node_id": "pocket-lab-lite-server",
                "hostname": "Pocket Lab Lite Server",
                "status": "online",
                "heartbeat_at": f"2026-07-24T08:{index // 60:02d}:{index % 60:02d}Z",
            },
            event_type="fleet.node_heartbeat",
        )

    agents = json.loads((state / "fleet_agents.json").read_text())["agents"]
    assert agents["pocket-lab-lite-server"]["first_heartbeat_at"] == "2026-07-24T08:00:00Z"
    first = [item for item in _events(state) if item.get("event_type") == "first_heartbeat_received"]
    assert len(first) == 1
    assert first[0]["dedupe_key"] == "pocket-lab-lite-server:first_heartbeat_received"


def test_semantic_key_dedupes_replay_with_new_timestamp(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import fleet_registry

    for timestamp in ("2026-07-24T08:00:00Z", "2026-07-24T09:00:00Z"):
        fleet_registry.append_device_lifecycle_event(
            "phone-two",
            "first_heartbeat_received",
            occurred_at=timestamp,
            summary="First valid device heartbeat received.",
            dedupe_key="phone-two:first_heartbeat_received",
        )

    first = [item for item in _events(state) if item.get("event_type") == "first_heartbeat_received"]
    assert len(first) == 1
    assert first[0]["occurred_at"] == "2026-07-24T09:00:00Z"


def test_concurrent_semantic_append_keeps_one_event(tmp_path, monkeypatch):
    state = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import fleet_registry

    def append(index: int):
        fleet_registry.append_device_lifecycle_event(
            "phone-two",
            "first_supervisor_heartbeat",
            occurred_at=f"2026-07-24T08:00:{index:02d}Z",
            dedupe_key="phone-two:first_supervisor_heartbeat",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append, range(20)))

    matches = [item for item in _events(state) if item.get("event_type") == "first_supervisor_heartbeat"]
    assert len(matches) == 1


def test_sqlite_semantic_unique_index_rejects_duplicate_projection(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import connection
    from api_fastapi.db.migrations import apply_migrations

    apply_migrations()
    with connection() as conn:
        conn.execute(
            "INSERT INTO device_current_state(device_id, device_name, role, ui_state, connection_state, agent_status, "
            "supervisor_status, pm2_status, remote_access_ready, protected_server_host, source_revision, last_seen_epoch_ms, "
            "updated_at, updated_at_epoch_ms, summary) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("phone-two", "Phone Two", "compute", "Offline", "offline", "offline", "unknown", "unknown", 0, 0, 1, 0, "2026-07-24T08:00:00Z", 1, "{}"),
        )
        base = ("phone-two", "first_heartbeat_received", "", "recorded", "2026-07-24T08:00:00Z", 1, "first", 1, 0, "phone-two:first_heartbeat_received")
        conn.execute(
            "INSERT INTO device_lifecycle_events(event_id, device_id, event_type, reason_code, status, occurred_at, occurred_at_epoch_ms, summary, sanitized, source_revision, dedupe_key) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("event-one", *base),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO device_lifecycle_events(event_id, device_id, event_type, reason_code, status, occurred_at, occurred_at_epoch_ms, summary, sanitized, source_revision, dedupe_key) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("event-two", *base),
            )


def _load_cleanup_module():
    script = Path(__file__).resolve().parents[2] / "scripts" / "lite" / "device-lifecycle-dedupe.py"
    spec = importlib.util.spec_from_file_location("device_lifecycle_dedupe", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cleanup_dry_run_is_non_mutating_and_apply_keeps_earliest():
    module = _load_cleanup_module()
    events = [
        {"event_id": "later", "node_id": "phone-two", "event_type": "first_heartbeat_received", "occurred_at": "2026-07-24T09:00:00Z"},
        {"event_id": "earlier", "node_id": "phone-two", "event_type": "first_heartbeat_received", "occurred_at": "2026-07-24T08:00:00Z"},
        {"event_id": "return", "node_id": "phone-two", "event_type": "device_returned_online", "occurred_at": "2026-07-24T10:00:00Z"},
    ]
    original = json.loads(json.dumps(events))
    kept, removed = module._dedupe_events(events)

    assert events == original
    assert len(removed) == 1
    first = [item for item in kept if item.get("event_type") == "first_heartbeat_received"]
    assert len(first) == 1
    assert first[0]["event_id"] == "earlier"
    assert first[0]["dedupe_key"] == "phone-two:first_heartbeat_received"
    assert any(item.get("event_type") == "device_returned_online" for item in kept)
