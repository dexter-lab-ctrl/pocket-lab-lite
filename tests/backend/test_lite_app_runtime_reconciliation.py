from __future__ import annotations

from pathlib import Path


def test_runtime_evidence_overrides_stale_not_installed_state(monkeypatch, tmp_path):
    from api_fastapi.services import lite_app_runtime

    config = tmp_path / "demo.env"
    config.write_text("SAFE=1\n")
    monkeypatch.setitem(
        lite_app_runtime._APP_SPECS,
        "demo",
        lite_app_runtime.AppRuntimeSpec(
            app_id="demo",
            process_name="pocketlab-app-demo",
            route_path="/apps/demo/",
            local_url="http://127.0.0.1:9999/",
            config_paths=(str(config),),
        ),
    )
    monkeypatch.setattr(
        lite_app_runtime,
        "_pm2_process",
        lambda _name: {"registered": True, "running": True, "status": "online", "pid_present": True, "restart_count": 0},
    )
    monkeypatch.setattr(lite_app_runtime, "_http_reachable", lambda _url: (True, 404))
    lite_app_runtime._CACHE.clear()

    result = lite_app_runtime.reconcile_install_state(
        "demo", {"installed": False, "install_state": "not_installed", "status": "not_installed"}, force=True
    )

    assert result["installed"] is True
    assert result["running"] is True
    assert result["reachable"] is True
    assert result["http_status"] == 404
    assert result["installation_state"] == "installed_running"
    assert result["state_conflict"] is True
    assert result["sanitized"] is True


def test_action_availability_is_normalized_for_install_state():
    from api_fastapi.services.lite_app_runtime import normalize_action_availability

    install = normalize_action_availability(
        "install_app", {"enabled": True}, installed=True, app_name="Demo"
    )
    check = normalize_action_availability(
        "check_app", {"enabled": True}, installed=False, app_name="Demo"
    )

    assert install == {
        "enabled": False,
        "status": "disabled",
        "disabled_reason": "Demo is already installed.",
        "reason": "Demo is already installed.",
    }
    assert check["enabled"] is False
    assert check["status"] == "disabled"
    assert check["disabled_reason"] == "Install Demo first."


def test_projection_store_does_not_persist_action_capabilities_as_history(tmp_path, monkeypatch):
    from pocket_lab_test_utils import ensure_runtime_path, prepare_sqlite_test_database

    ensure_runtime_path()
    prepare_sqlite_test_database(tmp_path / "state" / "pocketlab-lite.sqlite3", monkeypatch)
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    store = ControlPlaneProjectionStore()
    store.project_apps({
        "apps": [{
            "app_id": "demo",
            "name": "Demo",
            "status": "ready",
            "installed": True,
            "actions": {
                "install_app": {"enabled": False, "status": "disabled", "summary": "Already installed"},
                "check_app": {"enabled": True, "status": "ready", "summary": "Ready"},
                "real_operation": {
                    "enabled": False,
                    "status": "succeeded",
                    "operation_id": "demo-op-1",
                    "summary": "Completed",
                    "updated_at": "2026-07-29T12:00:00Z",
                },
            },
        }],
        "updated_at": "2026-07-29T12:00:00Z",
    })

    with read_connection() as conn:
        rows = [dict(row) for row in conn.execute(
            "SELECT operation_id,action_id,status FROM app_action_lifecycle ORDER BY operation_id"
        ).fetchall()]

    assert rows == [{"operation_id": "demo-op-1", "action_id": "real_operation", "status": "succeeded"}]

def test_app_projection_domains_are_worker_registered_and_ui_critical():
    core = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_core_projections.py"
    ).read_text()
    semantic = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_semantic_revisions.py"
    ).read_text()

    # Worker-owned registry must include all App Catalog projection domains.
    assert '"apps.catalog"' in core
    assert '"apps.lifecycle"' in core
    assert '"apps.actions:photoprism"' in core

    # Stable projection keys must remain registered.
    assert 'key="catalog"' in core
    assert 'key="lifecycle"' in core
    assert 'key="actions:photoprism"' in core

    # App projections must remain protected from ordinary background pressure.
    assert "priority=20" in semantic
    assert "priority=25" in semantic
    assert "priority=15" in semantic
    assert semantic.count('work_class="critical"') >= 3
