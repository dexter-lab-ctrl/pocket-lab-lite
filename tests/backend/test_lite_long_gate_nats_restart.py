from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = ROOT / "scripts/dev/check-lite-long-duration-gates-server-phone.sh"
GROUP3 = ROOT / "scripts/dev/lib/long_gate_group3.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_group3_nats_test", GROUP3)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_group3_registry_and_disruptive_opt_in():
    listing = subprocess.run(["bash", str(ORCHESTRATOR), "--list-gates"], cwd=ROOT, text=True, capture_output=True, check=True)
    for gate in ("submission-recovery", "nats-restart", "worker-restart"):
        line = next(item for item in listing.stdout.splitlines() if item.startswith(gate))
        assert "implemented" in line
        assert "yes" in line
    denied = subprocess.run(["bash", str(ORCHESTRATOR), "--gate", "nats-restart", "--scenario", "idle", "--dry-run"], cwd=ROOT, text=True, capture_output=True)
    assert denied.returncode == 22
    assert "requires --allow-disruptive" in denied.stderr
    allowed = subprocess.run(["bash", str(ORCHESTRATOR), "--gate", "nats-restart", "--scenario", "idle", "--allow-disruptive", "--dry-run"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "planned_actions=restart pocket-nats only; scenario=idle" in allowed.stdout
    assert "disruptive=yes" in allowed.stdout


def test_all_excludes_disruption_without_opt_in_and_includes_it_with_opt_in():
    safe = subprocess.run(["bash", str(ORCHESTRATOR), "--all", "--dry-run"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "selected_gates=idle,repeated-scans,progress-soak" in safe.stdout
    disruptive = subprocess.run(["bash", str(ORCHESTRATOR), "--all", "--allow-disruptive", "--dry-run"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "submission-recovery" in disruptive.stdout
    assert "nats-restart" in disruptive.stdout
    assert "worker-restart" in disruptive.stdout


def test_nats_consumer_evidence_is_sanitized_and_duplicate_aware():
    module = load_tool()
    payload = {
        "connected": True,
        "jetstream_enabled": True,
        "servers": ["nats://user:password@host:4222"],
        "durable_consumer_health": {
            "pocketlab_command_worker_v1": {
                "healthy": True,
                "generation": 3,
                "recoveries": 1,
                "callback_inflight": False,
                "credential": "secret",
            }
        },
    }
    view = module.safe_nats_view(payload)
    serialized = str(view)
    assert "password" not in serialized
    assert "credential" not in serialized
    summary = module.consumer_summary(payload)
    assert summary["healthy"] is True
    assert summary["generation"] == 3
    assert summary["duplicate_consumers"] == 0


def test_nats_scenarios_and_precise_pm2_source_contract():
    module = load_tool()
    assert module._scenario_list("both", ("idle", "active")) == ["idle", "active"]
    assert module._scenario_list("active", ("idle", "active")) == ["active"]
    source = GROUP3.read_text(encoding="utf-8")
    assert 'run_pm2_action("pocket-nats", "restart"' in source
    assert "pm2 kill" not in source
    assert "restart all" not in source
    assert "reload all" not in source
    assert "JetStream" not in source or "purge" not in source
