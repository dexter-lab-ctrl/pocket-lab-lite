from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUPERVISORS = ROOT / "pocket-lab-final-structure" / "runtime" / "supervisors"


def _load(name: str):
    if name == "pocketlab_runtime_reconciler":
        _load("pocketlab_runtime_registry")
        _load("pocketlab_runtime_contract")
    path = SUPERVISORS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_lite_registry_excludes_legacy_pocket_lab_services():
    registry = _load("pocketlab_runtime_registry")
    names = set(registry.control_plane_names())
    assert {
        "pocket-nats",
        "pocket-api",
        "pocket-worker",
        "pocket-opa",
        "pocket-node-agent",
        "caddy-proxy",
        "pocketlab-core-supervisor",
    } <= names
    assert names.isdisjoint(registry.LEGACY_LITE_SERVICES)


def test_runtime_reconciler_repairs_only_missing_definitions():
    registry = _load("pocketlab_runtime_registry")
    reconciler = _load("pocketlab_runtime_reconciler")
    healthy = {spec.name: "online" for spec in registry.CONTROL_PLANE_SERVICES}
    assert reconciler.repair_reasons(healthy) == []

    drifted = dict(healthy)
    drifted["pocket-worker"] = "stopped"
    drifted["pocket-api"] = "waiting restart"
    reasons = reconciler.repair_reasons(drifted)
    assert reasons == []
    drifted["pocket-worker"] = "missing"
    reasons = reconciler.repair_reasons(drifted)
    assert "pm2_definition_or_process:pocket-worker:missing" in reasons


def test_runtime_reconcile_outer_lock_cannot_leak_into_pm2_children():
    source = (
        ROOT
        / "pocket-lab-final-structure"
        / "pocket-lab-bootstrap-production-scripts-patched"
        / "scripts"
        / "lib"
        / "common.sh"
    ).read_text(encoding="utf-8")
    assert 'if [[ "$name" == "reconcile-runtime.sh" ]]' in source
    assert 'ACTIVE_LOCK_DIR="$lockfile"' in source
    assert 'write_lock_metadata "$lockfile/metadata" "$name"' in source


def test_lite_bootstrap_skips_legacy_runtime_stages():
    bootstrap = (
        ROOT
        / "pocket-lab-final-structure"
        / "pocket-lab-bootstrap-production-scripts-patched"
        / "scripts"
        / "bootstrap.sh"
    ).read_text()
    assert "init_vault|init_mariadb|start_gitea|seed_gitops_repo" in bootstrap
    packages = (
        ROOT
        / "pocket-lab-final-structure"
        / "pocket-lab-bootstrap-production-scripts-patched"
        / "scripts"
        / "install-termux-packages.sh"
    ).read_text()
    assert "packages+=(mariadb gitea)" in packages
    assert "if ! is_lite_profile; then" in packages



def test_remote_access_loss_does_not_restart_control_plane():
    _load("pocketlab_runtime_registry")
    reconciler = _load("pocketlab_runtime_reconciler")

    # Network loss: daemon remains running but Tailnet IPv4 is temporarily absent.
    assert reconciler.remote_reconcile_reasons(
        {"installed": True, "daemon_running": True, "ipv4_ready": False},
        {"installed": True, "daemon_running": True, "ipv4_ready": True},
    ) == []

    assert reconciler.remote_reconcile_reasons(
        {"installed": True, "daemon_running": False, "ipv4_ready": False},
        {"installed": True, "daemon_running": True, "ipv4_ready": True},
    ) == ["tailscaled_missing"]

    assert reconciler.remote_reconcile_reasons(
        {"installed": True, "daemon_running": True, "ipv4_ready": True},
        {"installed": True, "daemon_running": True, "ipv4_ready": False},
    ) == ["tailscale_ready_transition"]



def test_pm2_version_projection_drift_is_repairable():
    _load("pocketlab_runtime_registry")
    reconciler = _load("pocketlab_runtime_reconciler")

    healthy = [{
        "name": "pocket-api",
        "pm2_env": {
            "status": "online",
            "version": "1.0.0+sha.123456789abc",
            "POCKETLAB_SERVICE_VERSION": "1.0.0+sha.123456789abc",
        },
    }]
    versions, reasons = reconciler.pm2_version_projection(healthy)
    assert versions["pocket-api"] == "1.0.0+sha.123456789abc"
    assert reasons == []

    missing = [{
        "name": "pocket-api",
        "pm2_env": {
            "status": "online",
            "version": "N/A",
        },
    }]
    _, reasons = reconciler.pm2_version_projection(missing)
    assert reasons == ["pm2_version_projection:pocket-api"]

    mismatch = [{
        "name": "pocket-api",
        "pm2_env": {
            "status": "online",
            "version": "1.0.0+sha.old",
            "POCKETLAB_SERVICE_VERSION": "1.0.0+sha.new",
        },
    }]
    _, reasons = reconciler.pm2_version_projection(mismatch)
    assert reasons == ["pm2_version_projection:pocket-api"]


def test_runtime_reconciler_strips_own_pm2_version_metadata_from_child_env():
    source = (SUPERVISORS / "pocketlab_runtime_reconciler.py").read_text(encoding="utf-8")
    repair = source[source.index("    def _repair("):source.index("    def tick(", source.index("    def _repair("))]
    assert 'env.pop("POCKETLAB_SERVICE_VERSION", None)' in repair
    assert 'env.pop("POCKETLAB_PM2_SERVICE_VERSION", None)' in repair


def test_runtime_reconciler_strips_stale_runtime_path_overrides_from_child_env():
    source = (SUPERVISORS / "pocketlab_runtime_reconciler.py").read_text(encoding="utf-8")
    repair = source[source.index("    def _repair("):source.index("    def tick(", source.index("    def _repair("))]

    for key in (
        "POCKETLAB_BASE_DIR",
        "POCKETLAB_STATE_DIR",
        "POCKETLAB_LITE_DB_PATH",
        "POCKETLAB_OPA_ACTIVE_POLICY_DIR",
    ):
        assert f'"{key}"' in repair

    assert "for key in (" in repair
    assert "env.pop(key, None)" in repair


def test_runtime_reconciler_detects_canonical_pm2_policy_drift():
    registry = _load("pocketlab_runtime_registry")
    reconciler = _load("pocketlab_runtime_reconciler")
    policy = registry.policy_for("pocket-api")
    process = {
        "name": "pocket-api",
        "pm2_env": {
            "status": "online",
            "min_uptime": policy.min_uptime_seconds * 1000,
            "max_restarts": policy.max_restarts,
            "kill_timeout": policy.kill_timeout_ms + 1,
            "max_memory_restart": policy.max_memory_restart_mb * 1024 * 1024,
            "restart_delay": policy.restart_delay_ms or 0,
            "exp_backoff_restart_delay": policy.exp_backoff_restart_delay_ms or 0,
            "autorestart": True,
            "POCKETLAB_PM2_POLICY_FINGERPRINT": registry.policy_fingerprint("pocket-api"),
        },
    }
    reasons = reconciler.pm2_policy_reasons([process])
    assert reasons
    assert reasons[0].startswith("pm2_policy:pocket-api:")
    assert "kill_timeout_ms" in reasons[0]


def test_runtime_reconciler_accepts_matching_canonical_pm2_policy():
    registry = _load("pocketlab_runtime_registry")
    reconciler = _load("pocketlab_runtime_reconciler")
    policy = registry.policy_for("pocket-api")
    process = {
        "name": "pocket-api",
        "pm2_env": {
            "status": "online",
            "min_uptime": policy.min_uptime_seconds * 1000,
            "max_restarts": policy.max_restarts,
            "kill_timeout": policy.kill_timeout_ms,
            "max_memory_restart": policy.max_memory_restart_mb * 1024 * 1024,
            "restart_delay": policy.restart_delay_ms or 0,
            "exp_backoff_restart_delay": policy.exp_backoff_restart_delay_ms or 0,
            "autorestart": True,
            "POCKETLAB_PM2_POLICY_FINGERPRINT": registry.policy_fingerprint("pocket-api"),
        },
    }
    assert reconciler.pm2_policy_reasons([process]) == []


def test_runtime_reconciler_repairs_missing_and_drifted_desired_process_spec_hashes(tmp_path):
    registry = _load("pocketlab_runtime_registry")
    reconciler = _load("pocketlab_runtime_reconciler")
    process = {
        "name": "pocket-api",
        "pm2_env": {
            "POCKETLAB_PROCESS_SPEC_HASH": "a" * 64,
            "pm_exec_path": "/opt/pocketlab/pocket-api/exec",
            "exec_interpreter": "python3",
        },
    }
    state_root = tmp_path / "state"
    assert reconciler.pm2_desired_spec_reasons([process], state_root=state_root) == [
        "pm2_desired_specs_unavailable"
    ]
    evidence = state_root / "runtime" / "desired-process-specs.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(json.dumps({
        "schema": "pocketlab.pm2-desired-process-specs/v1",
        "schema_version": 1,
        "processes": {"pocket-api": "a" * 64},
        "launches": {
            "pocket-api": registry.launch_fingerprint(
                process["pm2_env"]["pm_exec_path"], process["pm2_env"]["exec_interpreter"]
            )
        },
        "sanitized": True,
    }), encoding="utf-8")
    assert reconciler.pm2_desired_spec_reasons([process], state_root=state_root) == []
    process["pm2_env"]["POCKETLAB_PROCESS_SPEC_HASH"] = "b" * 64
    assert reconciler.pm2_desired_spec_reasons([process], state_root=state_root) == [
        "pm2_desired_spec_mismatch:pocket-api"
    ]
    process["pm2_env"]["POCKETLAB_PROCESS_SPEC_HASH"] = "a" * 64
    process["pm2_env"]["pm_exec_path"] = "/opt/pocketlab/pocketlab-runtime-reconciler/exec"
    assert reconciler.pm2_desired_spec_reasons([process], state_root=state_root) == [
        "pm2_desired_launch_mismatch:pocket-api"
    ]


def test_runtime_reconciler_environment_overrides_are_bounded_and_fail_safely(tmp_path, monkeypatch):
    reconciler_module = _load("pocketlab_runtime_reconciler")
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("POCKETLAB_RUNTIME_RECONCILE_SECONDS", "bad")
    monkeypatch.setenv("POCKETLAB_RUNTIME_RECONCILE_COOLDOWN_SECONDS", "999999999")
    monkeypatch.setenv("POCKETLAB_RUNTIME_RECONCILE_WINDOW_SECONDS", "1")
    monkeypatch.setenv("POCKETLAB_RUNTIME_RECONCILE_MAX_REPAIRS", "-7")
    reconciler = reconciler_module.RuntimeReconciler()
    assert reconciler.interval == reconciler_module.DEFAULT_INTERVAL_SECONDS
    assert reconciler.cooldown == reconciler_module.MAX_COOLDOWN_SECONDS
    assert reconciler.window == 300
    assert reconciler.max_repairs == 1
