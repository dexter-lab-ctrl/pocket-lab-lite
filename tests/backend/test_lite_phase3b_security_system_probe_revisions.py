from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(target))
    from api_fastapi.db.connection import reset_sqlite_path_cache

    reset_sqlite_path_cache()
    return target


def test_phase3b_migration_creates_bounded_current_state_and_indexes(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.db.migrations import apply_migrations, current_schema_version

    assert apply_migrations() == list(range(1, 17))
    assert current_schema_version() == 16
    with read_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        domains = {
            row[0]
            for row in conn.execute(
                "SELECT domain FROM domain_revisions WHERE domain LIKE 'system.%' OR domain LIKE 'security.%'"
            )
        }
    assert {"phase3b_current_state", "phase3b_revision_events"}.issubset(tables)
    assert {
        "idx_phase3b_current_state_status",
        "idx_phase3b_current_state_revision",
        "idx_phase3b_revision_events_replay",
        "idx_phase3b_revision_events_retention",
    }.issubset(indexes)
    assert {
        "security.progress",
        "security.summary",
        "system.status",
        "system.health",
        "system.processes",
        "system.agent",
        "system.supervisor",
        "system.remote_access",
        "system.nats_remote",
        "system.fleet_probe",
    }.issubset(domains)


def test_phase3b_semantic_revision_ignores_volatile_probe_noise():
    ensure_runtime_path()
    from api_fastapi.services.lite_phase3b_projections import semantic_revision

    first = {
        "status": "healthy",
        "checked_at": "2026-07-25T12:00:00Z",
        "collector_duration_ms": 12.4,
        "items": [
            {"name": "pocket-api", "status": "online", "pid": 101, "cpu": 3.2},
            {"name": "pocket-worker", "status": "online", "memory": 5000},
        ],
    }
    second = {
        "status": "healthy",
        "checked_at": "2026-07-25T12:10:00Z",
        "collector_duration_ms": 99.9,
        "items": [
            {"name": "pocket-worker", "status": "online", "memory": 9000},
            {"name": "pocket-api", "status": "online", "pid": 999, "cpu": 75.0},
        ],
    }
    assert semantic_revision("system.processes", first) == semantic_revision(
        "system.processes", second
    )
    changed = json.loads(json.dumps(second))
    changed["items"][0]["status"] = "stopped"
    assert semantic_revision("system.processes", first) != semantic_revision(
        "system.processes", changed
    )



def test_status_source_revision_ignores_child_projection_envelope_churn(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b

    envelope = {
        "status": "healthy",
        "summary": "Ready",
        "item_count": 1,
        "domain": "system.health",
        "generation": 10,
        "source_revision": 20,
        "projection_revision": 30,
        "collector_duration_ms": 4.2,
        "updated_at": "2026-07-25T00:00:00Z",
        "projection_only": True,
    }
    snapshots = {name: dict(envelope, domain=name) for name in phase3b.SYSTEM_CURRENT_STATE_DOMAINS}
    monkeypatch.setattr(phase3b, "snapshot", lambda domain: dict(snapshots.get(domain) or {}))
    monkeypatch.setattr(phase3b, "_database_instance", lambda: "db")
    monkeypatch.setattr(phase3b, "_bus_material", lambda: {"connected": True})

    first = phase3b.status_source_revision()
    for value in snapshots.values():
        value["generation"] += 1
        value["source_revision"] += 7
        value["projection_revision"] += 1
        value["collector_duration_ms"] = 999.0
        value["updated_at"] = "2026-07-25T01:00:00Z"
    assert phase3b.status_source_revision() == first

    snapshots["system.health"]["status"] = "degraded"
    assert phase3b.status_source_revision() != first

def test_phase3b_projection_is_change_only_and_uses_indexed_lookup(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.services import lite_phase3b_projections as phase3b

    apply_migrations()
    payload = {
        "status": "healthy",
        "items": [{"name": "pocket-api", "status": "online"}],
        "item_count": 1,
        "sanitized": True,
    }
    first = phase3b.project("system.processes", payload)
    second_payload = dict(payload)
    second_payload["collector_duration_ms"] = 987.6
    second_payload["checked_at"] = "2026-07-25T13:00:00Z"
    second = phase3b.project("system.processes", second_payload)
    assert first == 1
    assert second == first
    saved = phase3b.snapshot("system.processes")
    assert saved and saved["projection_revision"] == first
    assert saved["projection_only"] is True
    assert saved["sanitized"] is True

    conn = sqlite3.connect(database)
    try:
        detail = " ".join(
            str(row[-1])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN SELECT payload_json FROM phase3b_current_state WHERE domain=?",
                ("system.processes",),
            )
        ).lower()
    finally:
        conn.close()
    assert "index" in detail or "sqlite_autoindex_phase3b_current_state" in detail


def test_pm2_projection_strips_process_noise_and_secrets(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b

    monkeypatch.setattr(phase3b.shutil, "which", lambda name: "/usr/bin/pm2")
    raw = [
        {
            "name": "pocket-api",
            "pid": 444,
            "monit": {"cpu": 99, "memory": 123456},
            "pm2_env": {
                "status": "online",
                "restart_time": 2,
                "unstable_restarts": 0,
                "pm_uptime": 999999,
                "env": {"TOKEN": "must-not-appear"},
                "args": ["--secret", "must-not-appear"],
            },
        }
    ]
    monkeypatch.setattr(
        phase3b.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(raw)),
    )
    payload = phase3b.collect_process_state()
    encoded = json.dumps(payload, sort_keys=True).lower()
    assert '"pid"' not in encoded
    assert '"cpu"' not in encoded
    assert '"memory"' not in encoded
    assert "must-not-appear" not in encoded
    item = next(row for row in payload["items"] if row["name"] == "pocket-api")
    assert item["status"] == "online"
    assert item["restart_generation"] == 2


def test_phase3b_contracts_reuse_shared_projection_scheduler_guards():
    ensure_runtime_path()
    from api_fastapi.services.lite_semantic_revisions import contract_for

    for domain, key in (
        ("security", "progress"),
        ("security", "summary"),
        ("system", "status"),
        ("system", "health"),
        ("system", "processes"),
        ("system", "agent"),
        ("system", "supervisor"),
        ("system", "remote_access"),
        ("system", "nats_remote"),
        ("system", "fleet_probe"),
    ):
        contract = contract_for(domain, key)
        assert contract is not None
        assert callable(contract.source_revision)
        assert contract.max_probe_seconds <= 300
        assert contract.deadline_seconds <= 10


def test_fleet_probe_reuses_prepared_fleet_projection(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    monkeypatch.setattr(
        CONTROL_PLANE,
        "fleet_projection_snapshot",
        lambda: {
            "source_revision": 7,
            "devices": [
                {
                    "id": "server",
                    "connection": "online",
                    "agent_status": "online",
                    "supervisor_status": "healthy",
                }
            ],
        },
    )
    payload = phase3b.collect_fleet_probe_state()
    assert payload["projection_only"] is True
    assert payload["source_revision"] == 7
    assert payload["summary"] == {"online": 1, "offline": 0, "total": 1}
    assert payload["items"][0]["id"] == "server"


def test_status_request_source_is_prepared_only():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    ).read_text(encoding="utf-8")
    route = source[source.index('@router.get("/status")'):source.index('@router.get("/catalog")')]
    assert "_phase3b_prepared_read" in route
    assert "build_lite_status()" not in route
    assert "lite_remote_access_status" not in route
    assert "fleet_health_snapshot" not in route
    assert "subprocess" not in route


def test_phase3b_runtime_validation_script_is_termux_safe():
    script = Path("scripts/dev/check-lite-phase3b-projections.sh").read_text(
        encoding="utf-8"
    )
    assert "${TMPDIR" not in script
    assert "/tmp/" not in script
    assert "$STATE_DIR/.pocketlab-dev/phase3b" in script
    assert "tailscale-cli" in script
    assert "pm2" in script
    assert "api/lite/diagnostics/runtime" in script
    assert "api/lite/status" in script
    assert "token" not in script.lower()



def test_nats_readiness_tracks_secondary_state_without_exposing_url(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b
    from api_fastapi.services import lite_status

    monkeypatch.setenv("POCKETLAB_NATS_URL", "nats://user:password@example.invalid:4222")
    monkeypatch.setattr(lite_status, "_nats_reachable_on_host", lambda host, port=None: True)
    monkeypatch.setattr(
        phase3b.BUS,
        "status",
        lambda: {
            "connected": True,
            "jetstream_enabled": True,
            "reconnect_pending": False,
            "watchdog_running": True,
            "durable_consumer_health": {
                "worker": {
                    "healthy": True,
                    "generation": 3,
                    "recoveries": 1,
                    "task_alive": True,
                    "subscription_present": True,
                    "callback_inflight": False,
                }
            },
        },
    )
    payload = phase3b.collect_nats_remote_state()
    encoded = json.dumps(payload, sort_keys=True)
    assert payload["secondary_configured"] is True
    assert payload["secondary_reachable"] is True
    assert payload["route_selection"] == "secondary"
    assert "example.invalid" not in encoded
    assert "password" not in encoded.lower()
    assert "nats://" not in encoded

def test_phase3b_frontend_uses_domain_keys_conditional_reads_and_safe_snapshots():
    query = Path("src/lib/liteQueryClient.js").read_text(encoding="utf-8")
    api = Path("src/lib/liteApi.js").read_text(encoding="utf-8")
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text(encoding="utf-8")
    for path in (
        "/api/lite/system/health",
        "/api/lite/system/processes",
        "/api/lite/system/agent",
        "/api/lite/system/supervisor",
        "/api/lite/remote-access/readiness",
        "/api/lite/system/nats-readiness",
    ):
        assert path in query
        assert path in api
        assert path in snapshots
    assert "conditionalGet('/api/lite/system/health')" in api
    assert "conditionalGet('/api/lite/remote-access/readiness')" in api
    assert "['lite', 'system', 'health']" in query
    assert "['lite', 'system', 'remote-access']" in query


def test_fleet_commits_dirty_dependent_phase3b_domains():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py"
    ).read_text(encoding="utf-8")
    project = source[source.index("    def project_fleet("):source.index("    def _upsert_command_row(")]
    assert "fleet_projection_committed" in project
    for domain in (
        '"system.fleet_probe"',
        '"system.agent"',
        '"system.supervisor"',
        '"system.health"',
        '"system.status"',
    ):
        assert domain in project
    assert "current_revision != int(previous_revision)" in project


def test_security_progress_revision_changes_only_for_persisted_semantics(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b
    from api_fastapi.services import lite_security

    state = {
        "revision": 7,
        "progress_revision": 11,
        "progress": {
            "run_id": "security-run-1",
            "status": "running",
            "stage": "Host posture checked",
            "percent": 42,
            "profile": "quick",
            "app_id": None,
            "updated_at": "2026-07-25T12:00:00Z",
        },
    }
    monkeypatch.setattr(lite_security, "freshness_state", lambda: state)
    monkeypatch.setattr(phase3b, "_database_instance", lambda: "db-instance")
    monkeypatch.setattr(phase3b, "_maintenance_material", lambda: [])
    first = phase3b.security_progress_source_revision()
    state["progress"]["updated_at"] = "2026-07-25T12:30:00Z"
    assert phase3b.security_progress_source_revision() == first
    state["progress"]["percent"] = 58
    state["progress_revision"] = 12
    assert phase3b.security_progress_source_revision() != first


def test_agent_and_supervisor_generations_ignore_heartbeat_time_but_track_state(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b

    rows = [
        {
            "device_id": "phone-two",
            "connection_state": "online",
            "agent_status": "online",
            "supervisor_status": "healthy",
            "pm2_status": "online",
            "source_revision": 9,
            "last_seen_at": "2026-07-25T12:00:00Z",
        }
    ]
    monkeypatch.setattr(phase3b, "_fleet_rows", lambda: rows)
    agent_first = phase3b.collect_agent_state()["generation"]
    supervisor_first = phase3b.collect_supervisor_state()["generation"]
    rows[0]["last_seen_at"] = "2026-07-25T12:10:00Z"
    assert phase3b.collect_agent_state()["generation"] == agent_first
    assert phase3b.collect_supervisor_state()["generation"] == supervisor_first
    rows[0]["connection_state"] = "offline"
    rows[0]["agent_status"] = "offline"
    rows[0]["supervisor_status"] = "unavailable"
    rows[0]["pm2_status"] = "stopped"
    assert phase3b.collect_agent_state()["generation"] != agent_first
    assert phase3b.collect_supervisor_state()["generation"] != supervisor_first


def test_remote_access_generation_tracks_readiness_and_tailnet_ip_without_urls(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b
    from api_fastapi.services import lite_status

    remote = {
        "ready": True,
        "running": True,
        "ip": "100.64.0.10",
        "nats_reachable": True,
    }
    monkeypatch.setattr(lite_status, "lite_remote_access_status", lambda: dict(remote))
    monkeypatch.setattr(
        phase3b,
        "collect_nats_remote_state",
        lambda: {"status": "healthy", "connected": True},
    )
    first = phase3b.collect_remote_access_state()
    second = phase3b.collect_remote_access_state()
    assert first["generation"] == second["generation"]
    remote["ip"] = "100.64.0.11"
    changed = phase3b.collect_remote_access_state()
    assert changed["generation"] != first["generation"]
    encoded = json.dumps(changed, sort_keys=True).lower()
    assert "nats://" not in encoded
    assert "password" not in encoded


def test_phase3b_system_read_routes_are_side_effect_free_prepared_reads():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    ).read_text(encoding="utf-8")
    for route_path in (
        "/system/health",
        "/system/processes",
        "/system/agent",
        "/system/supervisor",
        "/remote-access/readiness",
        "/system/nats-readiness",
    ):
        marker = f'@router.get("{route_path}")'
        start = source.index(marker)
        next_route = source.find("\n@router.", start + len(marker))
        block = source[start: next_route if next_route != -1 else len(source)]
        assert "_phase3b_prepared_read" in block
        for forbidden in ("subprocess", "pm2", "tailscale", "BUS.connect", "fleet_health_snapshot"):
            assert forbidden not in block


def test_status_projection_reuses_prepared_dependencies_before_bounded_fallback():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_status.py"
    ).read_text(encoding="utf-8")
    builder = source[
        source.index("def build_lite_status_projection("):
        source.index("async def build_lite_status(")
    ]
    assert "if phase3b.snapshot(domain):" in builder
    assert "prepared_health = phase3b.snapshot(\"system.health\")" in builder
    assert "if prepared_health:" in builder
    assert "else:\n        engine = deps.core.build_health_engine_snapshot()" in builder
    assert "First warm-up only. Request handlers never call this builder." in builder


def test_fleet_heartbeat_invalidation_is_coalesced_by_semantic_revision(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore
    from api_fastapi.services.projection_scheduler import PROJECTION_SCHEDULER

    store = ControlPlaneProjectionStore()
    calls = []
    monkeypatch.setattr(
        PROJECTION_SCHEDULER,
        "mark_registered_prefix_dirty",
        lambda domain: calls.append(domain),
    )

    store.invalidate_domain("fleet", semantic_revision=101)
    store.invalidate_domain("fleet", semantic_revision=101)
    store.invalidate_domain("fleet", semantic_revision=102)

    assert calls == ["fleet", "fleet"]


def test_phase3b_prepared_metadata_names_semantic_projection_and_generation():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    ).read_text(encoding="utf-8")
    response = source[
        source.index("def _control_plane_prepared_response("):
        source.index("def _projection_warming_response(")
    ]
    assert '"semantic_source_revision"' in response
    assert '"stored_projection_revision"' in response
    assert '"scheduler_generation"' in response
    assert 'payload["source_revision"]' in response


def test_phase3b_gate_retries_api_readiness_without_relaxing_idle_gate():
    script = Path("scripts/dev/check-lite-phase3b-projections.sh").read_text(
        encoding="utf-8"
    )
    assert "POCKETLAB_PHASE3B_READY_ATTEMPTS" in script
    assert '--connect-timeout "$READY_CONNECT_TIMEOUT"' in script
    assert '--max-time "$READY_MAX_TIME"' in script
    assert "Pocket API did not become ready" in script
    assert 'if second["refresh_pending"] or second["followup_requested"]:' in script
    assert "scheduler still pending after idle" in script


def test_fleet_dependency_propagation_is_revision_fenced():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py"
    ).read_text(encoding="utf-8")
    project = source[source.index("    def project_fleet("):source.index("    def _upsert_command_row(")]
    assert "_last_propagated_fleet_projection_revision" in project
    assert 'reason="fleet_projection_committed"' in project
    assert 'LIVE_STATUS.request_sample(' in project


def test_nats_readiness_route_has_prepared_snapshot_fail_closed_fallback():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    ).read_text(encoding="utf-8")
    start = source.index('def _nats_readiness_snapshot_fallback(')
    end = source.index('@router.get("/system/telemetry-thresholds")', start)
    block = source[start:end]
    assert 'snapshot("system.nats_remote")' in block
    assert 'X-PocketLab-Fallback' in block
    assert 'prepared-snapshot' in block
    assert 'except Exception as exc' in block
    assert 'BUS.status' not in block
    assert 'collect_nats_remote_state' not in block
    assert 'subprocess' not in block


def test_phase3b_gate_reports_the_exact_failed_endpoint():
    source = Path("scripts/dev/check-lite-phase3b-projections.sh").read_text(encoding="utf-8")
    assert 'Phase 3B endpoint failed: $path returned HTTP $code' in source
    assert "-w '%{http_code}'" in source
    assert "sed -n '1,80p'" in source
