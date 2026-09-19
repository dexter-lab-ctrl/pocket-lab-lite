from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUPERVISORS = ROOT / "pocket-lab-final-structure" / "runtime" / "supervisors"


def _load(name: str):
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


def test_runtime_reconciler_repairs_only_missing_or_stopped_definitions():
    registry = _load("pocketlab_runtime_registry")
    reconciler = _load("pocketlab_runtime_reconciler")
    healthy = {spec.name: "online" for spec in registry.CONTROL_PLANE_SERVICES}
    assert reconciler.repair_reasons(healthy) == []

    drifted = dict(healthy)
    drifted["pocket-worker"] = "stopped"
    drifted["pocket-api"] = "waiting restart"
    reasons = reconciler.repair_reasons(drifted)
    assert "pm2_definition_or_process:pocket-worker:stopped" in reasons
    assert not any("pocket-api" in reason for reason in reasons)


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
