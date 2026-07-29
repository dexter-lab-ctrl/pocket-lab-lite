from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, prepare_sqlite_test_database


@pytest.fixture(autouse=True)
def _runtime_path_and_clean_caches():
    ensure_runtime_path()
    from api_fastapi.services import lite_app_runtime

    for cache in (
        lite_app_runtime._CACHE,
        lite_app_runtime._LAST_VALID,
        lite_app_runtime._PM2_CACHE,
        lite_app_runtime._PM2_LAST_VALID,
    ):
        cache.clear()
    lite_app_runtime._PM2_INFLIGHT.clear()
    yield


def _pm2_row(*, name: str = "pocketlab-app-demo", status: str = "online", pid: int = 123, restart_time: int = 2):
    return {"name": name, "pid": pid, "pm2_env": {"status": status, "restart_time": restart_time}}


def _completed(rows, *, returncode: int = 0):
    return subprocess.CompletedProcess(["pm2", "jlist"], returncode, stdout=json.dumps(rows).encode(), stderr=b"")


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([_pm2_row()], {"signal": "present", "status": "online", "running": True, "pid_valid": True}),
        ([_pm2_row(status="stopped", pid=0)], {"signal": "present", "status": "stopped", "running": False, "pid_valid": False}),
        ([_pm2_row(status="errored", pid=0)], {"signal": "present", "status": "errored", "running": False, "pid_valid": False}),
        ([], {"signal": "absent", "status": "missing", "running": False, "pid_valid": False}),
        ([_pm2_row(pid=0)], {"signal": "present", "status": "online", "running": False, "pid_valid": False}),
    ],
)
def test_pm2_structured_states_are_deterministic(monkeypatch, rows, expected):
    from api_fastapi.services import lite_app_runtime

    monkeypatch.setattr(lite_app_runtime, "_pm2_binary", lambda _env: "/safe/pm2")
    monkeypatch.setattr(lite_app_runtime, "_run_pm2_jlist", lambda *_args, **_kwargs: (0, json.dumps(rows).encode()))

    result = lite_app_runtime._collect_pm2_process("pocketlab-app-demo")

    for key, value in expected.items():
        assert result[key] == value
    assert result["sanitized"] is True
    assert "HOME" not in result
    assert "PM2_HOME" not in result


@pytest.mark.parametrize(
    ("mode", "error_type"),
    [
        ("timeout", "pm2_timeout"),
        ("invalid_json", "pm2_invalid_json"),
        ("missing", "pm2_binary_missing"),
        ("duplicate", "pm2_duplicate_process_name"),
        ("schema", "pm2_unexpected_schema"),
        ("daemon", "pm2_daemon_error"),
    ],
)
def test_pm2_failures_are_unknown_not_absent(monkeypatch, mode, error_type):
    from api_fastapi.services import lite_app_runtime

    monkeypatch.setattr(lite_app_runtime, "_pm2_binary", lambda _env: None if mode == "missing" else "/safe/pm2")

    def run(*args, **kwargs):
        if mode == "timeout":
            raise subprocess.TimeoutExpired(["pm2", "jlist"], 2)
        if mode == "invalid_json":
            return 0, b"not-json"
        if mode == "duplicate":
            return 0, json.dumps([_pm2_row(), _pm2_row(pid=456)]).encode()
        if mode == "schema":
            return 0, json.dumps([{"name": "pocketlab-app-demo", "pid": 123}]).encode()
        if mode == "daemon":
            return 1, b""
        raise AssertionError(mode)

    monkeypatch.setattr(lite_app_runtime, "_run_pm2_jlist", run)
    result = lite_app_runtime._collect_pm2_process("pocketlab-app-demo")

    assert result["signal"] == "unknown"
    assert result["registered"] is None
    assert result["error_type"] == error_type


def test_pm2_last_valid_result_is_retained_during_temporary_failure(monkeypatch):
    from api_fastapi.services import lite_app_runtime

    monkeypatch.setattr(lite_app_runtime, "_collect_pm2_process", lambda _name: {
        "signal": "present", "registered": True, "running": True, "status": "online",
        "pid_present": True, "pid_valid": True, "restart_count": 0,
        "error_type": "", "last_valid_used": False, "sanitized": True,
    })
    first = lite_app_runtime._pm2_process("pocketlab-app-demo", force=True)
    monkeypatch.setattr(lite_app_runtime, "_collect_pm2_process", lambda _name: lite_app_runtime._unknown_pm2("pm2_daemon_error"))
    second = lite_app_runtime._pm2_process("pocketlab-app-demo", force=True)

    assert first["running"] is True
    assert second["running"] is True
    assert second["last_valid_used"] is True
    assert second["current_probe_error_type"] == "pm2_daemon_error"


def _install_spec(monkeypatch, tmp_path: Path, *, config: bool = False, executable: bool = False):
    from api_fastapi.services import lite_app_runtime

    config_path = tmp_path / "demo.env"
    executable_path = tmp_path / "demo-bin"
    if config:
        config_path.write_text("SAFE=1\n")
    if executable:
        executable_path.write_text("binary")
    monkeypatch.setitem(lite_app_runtime._APP_SPECS, "demo", lite_app_runtime.AppRuntimeSpec(
        app_id="demo", process_name="pocketlab-app-demo", route_path="/apps/demo/",
        local_url="http://127.0.0.1:9999/status", config_paths=(str(config_path),),
        executable_paths=(str(executable_path),),
    ))


@pytest.mark.parametrize(
    ("pm2", "http", "config", "executable", "expected"),
    [
        ({"signal": "present", "registered": True, "running": True, "status": "online", "pid_present": True, "pid_valid": True}, (True, 200), False, False, "installed_running"),
        ({"signal": "unknown", "registered": None, "running": None, "status": "unknown", "pid_present": None, "pid_valid": None}, (True, 404), True, False, "installed_degraded"),
        ({"signal": "present", "registered": True, "running": False, "status": "stopped", "pid_present": False, "pid_valid": False}, (False, None), False, False, "installed_stopped"),
        ({"signal": "absent", "registered": False, "running": False, "status": "missing", "pid_present": False, "pid_valid": False}, (False, None), False, False, "not_installed"),
        ({"signal": "unknown", "registered": None, "running": None, "status": "unknown", "pid_present": None, "pid_valid": None}, (False, None), False, False, "unknown"),
        ({"signal": "present", "registered": True, "running": False, "status": "online", "pid_present": False, "pid_valid": False}, (True, 200), True, False, "state_conflict"),
        ({"signal": "absent", "registered": False, "running": False, "status": "missing", "pid_present": False, "pid_valid": False}, (False, None), True, False, "installed_degraded"),
        ({"signal": "absent", "registered": False, "running": False, "status": "missing", "pid_present": False, "pid_valid": False}, (False, None), False, True, "installed_degraded"),
    ],
)
def test_canonical_runtime_states(monkeypatch, tmp_path, pm2, http, config, executable, expected):
    from api_fastapi.services import lite_app_runtime

    _install_spec(monkeypatch, tmp_path, config=config, executable=executable)
    monkeypatch.setattr(lite_app_runtime, "_pm2_process", lambda *_args, **_kwargs: dict(pm2))
    monkeypatch.setattr(lite_app_runtime, "_http_reachable", lambda _url: http)

    result = lite_app_runtime.probe_app_runtime("demo", force=True)

    assert result["installation_state"] == expected
    assert result["installed"] is (expected in {"installed_running", "installed_degraded", "installed_stopped", "state_conflict"})
    assert result["sanitized"] is True


def test_reconciler_adds_bounded_route_storage_and_history_signals(monkeypatch, tmp_path):
    from api_fastapi.services import lite_app_runtime

    _install_spec(monkeypatch, tmp_path, config=True)
    monkeypatch.setattr(lite_app_runtime, "_pm2_process", lambda *_args, **_kwargs: {
        "signal": "present", "registered": True, "running": True, "status": "online", "pid_present": True, "pid_valid": True,
    })
    monkeypatch.setattr(lite_app_runtime, "_http_reachable", lambda _url: (True, 200))

    result = lite_app_runtime.reconcile_install_state("demo", {
        "access": {"route_ready": True, "open_url": "/apps/demo/"},
        "storage": {"status": "ready", "mapping_count": 1},
        "runtime": {"version": "1.2.3"},
        "last_operation": {"action_id": "install_app", "status": "succeeded"},
    }, force=True)

    assert result["evidence"]["route"] == {"signal": "present", "ready": True}
    assert result["evidence"]["storage"] == {"signal": "present", "mapping_count": 1}
    assert result["evidence"]["version"]["signal"] == "present"
    assert result["evidence"]["install_history"]["signal"] == "present"


def _canonical_app_payload():
    return {
        "apps": [{
            "app_id": "photoprism", "id": "photoprism", "name": "PhotoPrism",
            "status": "ready", "installed": True, "install_state": "installed_running",
            "runtime": {
                "installation_state": "installed_running", "process_status": "online",
                "reachable": True, "running": True, "health": "healthy",
                "state_conflict": False, "evidence_quality": "authoritative",
                "process": {"name": "pocketlab-app-photoprism", "signal": "present", "status": "online", "pid_valid": True},
            },
            "access": {"https_ready": True, "route_ready": True, "open_url": "/apps/photoprism/", "message": "Secure access is ready."},
            "storage": {"status": "ready", "summary": "Phone storage", "mapping_count": 1, "mappings": [{"mapping_id": "phone"}]},
            "device_relationships": {"runs_on": "Pocket Lab Lite Server", "media_from": "Phone storage"},
            "actions": {"open": True},
            "lifecycle": {
                "actions": {
                    "preview_restore": {"enabled": False, "status": "not_ready", "label": "Preview restore", "disabled_reason": "No verified app backup yet"},
                    "import_photos": {"enabled": True, "status": "ready", "label": "Import photos", "progress": {"steps": [None, {"id": "ready", "status": "ready"}]}},
                },
                "media": {"status": "ready", "summary": "Phone storage", "mapping_count": 1},
                "security": {"status": "protected", "summary": "Protected app"},
                "backup": {"status": "ready", "summary": "Backup ready"},
                "recovery": {"preview_available": False},
                "operations": {}, "update": {}, "backup_targets": {},
            },
        }],
    }


def test_sqlite_preserves_canonical_catalog_and_independent_lifecycle(tmp_path, monkeypatch):
    prepare_sqlite_test_database(tmp_path / "state" / "pocketlab-lite.sqlite3", monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    first_revision = store.project_app_catalog(_canonical_app_payload())
    second_revision = store.project_app_catalog(_canonical_app_payload())
    catalog = store.app_catalog_projection_snapshot()
    lifecycle = store.app_lifecycle_projection_snapshot()
    actions = store.app_actions_projection_snapshot("photoprism")

    assert first_revision > 0
    assert second_revision == first_revision
    app = catalog["apps"][0]
    assert app["runtime"]["process_status"] == "online"
    assert app["access"]["open_url"] == "/apps/photoprism/"
    assert app["storage"]["mapping_count"] == 1
    assert app["device_relationships"]["media_from"] == "Phone storage"
    assert lifecycle["apps"][0]["actions"]["preview_restore"]["enabled"] is False
    assert actions["actions"]["import_photos"]["progress"]["steps"] == [{"id": "ready", "status": "ready"}]
    assert catalog["stored_projection_revision"] > 0
    assert catalog["projection_schema_version"] >= 3
    assert catalog["canonical_hash"]
    assert "password" not in json.dumps(catalog).lower()


def test_newer_sqlite_projection_replaces_older_process_memory(tmp_path, monkeypatch):
    prepare_sqlite_test_database(tmp_path / "state" / "pocketlab-lite.sqlite3", monkeypatch)
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore, _PreparedItem, _database_instance

    store = ControlPlaneProjectionStore()
    store.project_app_catalog(_canonical_app_payload())
    store._prepared["apps:catalog"] = _PreparedItem(
        payload={"apps": [{"id": "photoprism", "installed": False}], "updated_at": "2020-01-01T00:00:00Z"},
        revision=0, prepared_at=0.0, database_instance=_database_instance(), canonical_hash="old", projection_schema_version=1,
    )

    prepared = store.prepared_only_read(
        domain="apps", key="catalog", snapshot_builder=store.app_catalog_projection_snapshot,
        builder=lambda: (_ for _ in ()).throw(AssertionError("hot GET must not collect")),
        projector=lambda _payload: 0, stale_after_ms=10**12, max_stale_ms=10**12,
    )

    assert prepared.payload["apps"][0]["installed"] is True
    assert prepared.payload["stored_projection_revision"] > 0
    assert prepared.payload["semantic_source_revision"] > 0
    assert prepared.payload["scheduler_generation"] >= prepared.payload["committed_generation"]
    assert prepared.refresh_pending is False


def test_frontend_canonical_selector_is_executable_and_truthful():
    script = r'''
      import { selectCanonicalAppState } from './src/lib/liteViewModels.js';
      const states = {
        running: selectCanonicalAppState({ installed: true, runtime: { installation_state: 'installed_running', running: true, reachable: true }, access: { route_ready: true, open_url: '/apps/photoprism/' }, actions: { open: true } }),
        degraded: selectCanonicalAppState({ installed: true, runtime: { installation_state: 'installed_degraded', reachable: false } }),
        stopped: selectCanonicalAppState({ installed: true, runtime: { installation_state: 'installed_stopped' } }),
        unknown: selectCanonicalAppState({}),
        absent: selectCanonicalAppState({ installed: false, install_state: 'not_installed' }),
        disagreement: selectCanonicalAppState({ installed: true, runtime: { installation_state: 'installed_running' }, access: { route_ready: true, open_url: '/apps/photoprism/' }, actions: { open: false } }),
        media: selectCanonicalAppState({ installed: true, runtime: { installation_state: 'installed_running' }, storage: { status: 'ready', mapping_count: 1, summary: 'Phone storage' }, device_relationships: { media_from: 'Phone storage' } }),
      };
      console.log(JSON.stringify(states));
    '''
    result = subprocess.run(["node", "--input-type=module", "-e", script], check=True, capture_output=True, text=True)
    states = json.loads(result.stdout)

    assert states["running"]["statusLabel"] == "Running"
    assert states["running"]["openReady"] is True
    assert states["degraded"]["statusLabel"] == "Needs attention"
    assert states["stopped"]["statusLabel"] == "App stopped"
    assert states["unknown"]["statusLabel"] == "Checking"
    assert states["absent"]["statusLabel"] == "Not installed"
    assert states["disagreement"]["routeLabel"] == "Checking access"
    assert states["media"]["mediaLabel"] == "Phone storage connected"


def test_action_normalizer_removes_null_only_checks_and_progress_steps():
    from api_fastapi.services import lite_app_actions

    action = lite_app_actions._normalize_action("check_app", {
        "enabled": True,
        "status": "ready",
        "label": "Check app",
        "progress": {"steps": [None, {}, {"id": None, "status": None}, {"id": "route", "status": "ready"}]},
        "details": {"status_checks": [None, {}, {"id": None, "status": None}, {"id": "route", "status": "ready"}]},
    })

    assert action["progress"]["steps"] == [{"id": "route", "status": "ready"}]
    assert action["details"]["status_checks"] == [{
        "id": "route", "label": "Check", "status": "ready", "summary": "Check status is available."
    }]
    assert action["result"] == {}


def test_historical_import_result_disables_repeat_import():
    from api_fastapi.services import lite_app_actions

    actions = {"import_photos": {"enabled": True, "status": "ready", "summary": "Import connected photos."}}
    lite_app_actions._apply_import_photos_truth(actions, {
        "mapping_count": 1,
        "last_imported_at": "2026-07-29T10:00:00Z",
        "last_import": {"status": "completed", "completed_at": "2026-07-29T10:00:00Z"},
    })

    assert actions["import_photos"]["enabled"] is False
    assert actions["import_photos"]["status"] == "imported"
    assert actions["import_photos"]["historical_result"]["status"] == "imported"
    assert "PhotoPrism will handle new photos" in actions["import_photos"]["disabled_reason"]


def test_app_projection_schema_reconciliation_is_idempotent(tmp_path, monkeypatch):
    prepare_sqlite_test_database(tmp_path / "state" / "pocketlab-lite.sqlite3", monkeypatch)
    from api_fastapi.services import lite_core_projections
    from api_fastapi.services.lite_control_plane_store import CONTROL_PLANE

    missing = lite_core_projections.reconcile_app_projection_schema()
    CONTROL_PLANE.project_app_catalog(_canonical_app_payload())
    current = lite_core_projections.reconcile_app_projection_schema()

    assert missing["rebuild_required"] is True
    assert current["rebuild_required"] is False
    assert current["schema_version"] == 3
    assert current["history_preserved"] is True
    assert current["database_wiped"] is False
    assert lite_core_projections.APP_CATALOG_DOMAIN != lite_core_projections.APP_LIFECYCLE_DOMAIN
    assert lite_core_projections.APP_CATALOG_CACHE_KEY != lite_core_projections.APP_LIFECYCLE_CACHE_KEY
